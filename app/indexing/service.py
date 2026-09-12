"""Local-project code intelligence used by the existing FastAPI routes.

The index deliberately stays local and in memory: connecting a project never
uploads its files and does not write Sentinel metadata into the user's repo.
Tree-sitter is used when its optional language pack is installed; the
deterministic extractors below remain available for every supported language.
"""

from __future__ import annotations

import ast
import hashlib
import os
import re
from collections import defaultdict, deque
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Iterable

from app.indexing.languages import detect_language, is_binary_file
from app.config import settings
from app.models.common import EvidenceSnippet
from app.models.requests import ChangeDetail, ImpactAnalysisInput, ImpactedComponent

IGNORED_DIRECTORIES = {
    ".git", "node_modules", "venv", ".venv", "__pycache__", "dist", "build",
    "target", "coverage", ".cache", ".next", ".nuxt", ".idea", ".vscode",
}
SECRET_NAMES = {".env", ".env.local", ".env.production", ".env.development"}
MAX_FILE_BYTES = 1_000_000
SOURCE_LANGUAGES = {
    "python", "javascript", "typescript", "java", "c", "cpp", "csharp", "go",
    "rust", "ruby", "php", "html", "css", "sql", "markdown", "json", "yaml",
}
SYMBOL_RE = re.compile(
    r"(?m)^\s*(?:export\s+|public\s+|private\s+|protected\s+|async\s+|static\s+)*"
    r"(?:class|interface|struct|enum|trait|fn|func|function|def|module)\s+([A-Za-z_$][\w$]*)"
)
IMPORT_RE = re.compile(
    r"(?m)^\s*(?:from\s+([\w./-]+)\s+import|import\s+([\w./-]+)|use\s+([\w:]+)|"
    r"require\s*\(\s*['\"]([^'\"]+)['\"]\s*\)|#include\s*[<\"]([^>\"]+))"
)
CALL_RE = re.compile(r"\b([A-Za-z_$][\w$]*)\s*\(")
SECRET_ASSIGNMENT_RE = re.compile(
    r"(?im)^(\s*(?:[A-Z][A-Z0-9_]*?(?:API[_-]?KEY|TOKEN|PASSWORD|SECRET|PRIVATE[_-]?KEY)[A-Z0-9_]*|"
    r"(?:api[_-]?key|token|password|secret|private[_-]?key))\s*[:=]\s*)[^\r\n]+"
)
PEM_RE = re.compile(r"-----BEGIN [^-]*PRIVATE KEY-----.*?-----END [^-]*PRIVATE KEY-----", re.S)


def redact_secrets(content: str) -> str:
    """Remove credential values before context can leave the local agent."""
    content = PEM_RE.sub("[REDACTED PRIVATE KEY]", content)
    return SECRET_ASSIGNMENT_RE.sub(r"\1[REDACTED]", content)


@dataclass
class IndexedChunk:
    chunk_id: str
    file_path: str
    language: str
    symbol: str | None
    symbol_type: str
    parent_symbol: str | None
    start_line: int
    end_line: int
    content: str
    imports: list[str] = field(default_factory=list)
    references: list[str] = field(default_factory=list)

    def public(self, include_content: bool = True) -> dict:
        data = asdict(self)
        if not include_content:
            data.pop("content")
        return data


class ProjectIndex:
    """A safe, incrementally-maintained local repository index."""

    def __init__(self) -> None:
        self.root: Path | None = None
        self.chunks_by_file: dict[str, list[IndexedChunk]] = {}
        self.imports_by_file: dict[str, set[str]] = defaultdict(set)
        self.references_by_file: dict[str, set[str]] = defaultdict(set)
        self.files_by_symbol: dict[str, set[str]] = defaultdict(set)
        self.reverse_dependencies: dict[str, set[str]] = defaultdict(set)
        self.file_hashes: dict[str, str] = {}
        self.tree_sitter_files = 0
        self.retriever = None
        self.vector_status = "disabled"
        self.status = "idle"
        self.last_error: str | None = None

    @property
    def connected(self) -> bool:
        return self.root is not None

    def connect(self, path: str) -> dict:
        root = Path(path).expanduser().resolve()
        if not root.is_dir():
            raise ValueError("Project path must be an existing directory.")
        self.root = root
        self.chunks_by_file.clear()
        self.imports_by_file.clear()
        self.references_by_file.clear()
        self.files_by_symbol.clear()
        self.reverse_dependencies.clear()
        self.file_hashes.clear()
        self.tree_sitter_files = 0
        self.retriever = self._new_retriever()
        self.status = "indexing"
        for file_path in self.scan_files():
            self.update_file(file_path)
        self.status = "ready"
        return self.index_status()

    def _new_retriever(self):
        """Reuse Person 2's vector layer only when explicitly configured."""
        if not settings.VECTOR_RETRIEVAL_ENABLED:
            self.vector_status = "disabled"
            return None
        try:
            from retrieval_storage_2.retrieval import CodebaseRetriever
            self.vector_status = "building"
            return CodebaseRetriever()
        except Exception as exc:
            self.vector_status = f"unavailable: {type(exc).__name__}"
            self.last_error = f"Vector retrieval unavailable: {exc}"
            return None

    def _sync_vector_file(self, relative: str, chunks: list[IndexedChunk]) -> None:
        if not self.retriever:
            return
        try:
            from retrieval_storage_2.retrieval import CodeChunk
            # Incrementally replace only the changed file; no whole-project
            # re-embedding occurs during watcher updates.
            self.retriever.chunks = [chunk for chunk in self.retriever.chunks if chunk.file_path != relative]
            self.retriever.add_chunks([CodeChunk(
                chunk_id=chunk.chunk_id, file_path=chunk.file_path, start_line=chunk.start_line,
                end_line=chunk.end_line, text=chunk.content,
                metadata={"symbol": chunk.symbol, "language": chunk.language},
            ) for chunk in chunks])
            self.vector_status = "ready"
        except Exception as exc:
            self.vector_status = f"fallback: {type(exc).__name__}"
            self.last_error = f"Vector update failed: {exc}"
            self.retriever = None

    def _relative(self, path: Path) -> str:
        if not self.root:
            raise ValueError("No project connected.")
        resolved = path.resolve()
        try:
            return resolved.relative_to(self.root).as_posix()
        except ValueError as exc:
            raise ValueError("Path is outside the connected project.") from exc

    def resolve(self, relative_path: str) -> Path:
        if not self.root:
            raise ValueError("No project connected.")
        return_path = (self.root / relative_path).resolve()
        self._relative(return_path)
        return return_path

    def is_indexable(self, path: Path) -> bool:
        if path.name.lower() in SECRET_NAMES or any(part in IGNORED_DIRECTORIES for part in path.parts):
            return False
        try:
            if not path.is_file() or path.stat().st_size > MAX_FILE_BYTES:
                return False
            with path.open("rb") as handle:
                return not is_binary_file(handle.read(8192))
        except OSError:
            return False

    def scan_files(self) -> Iterable[Path]:
        if not self.root:
            return []
        result: list[Path] = []
        for directory, directories, filenames in os.walk(self.root):
            directories[:] = [name for name in directories if name not in IGNORED_DIRECTORIES]
            for name in filenames:
                candidate = Path(directory) / name
                if self.is_indexable(candidate) and detect_language(str(candidate)) in SOURCE_LANGUAGES:
                    result.append(candidate)
        return result

    def tree(self, relative_directory: str = "") -> list[dict]:
        target = self.resolve(relative_directory) if relative_directory else self.root
        if not target or not target.is_dir():
            raise ValueError("Invalid project directory.")
        entries = []
        for entry in target.iterdir():
            if entry.name in IGNORED_DIRECTORIES or entry.name.startswith("."):
                continue
            if entry.is_file() and not self.is_indexable(entry):
                continue
            entries.append({
                "name": entry.name, "path": self._relative(entry),
                "type": "dir" if entry.is_dir() else "file",
                "language": None if entry.is_dir() else detect_language(str(entry)),
            })
        return sorted(entries, key=lambda item: (item["type"] == "file", item["name"].lower()))

    def _tree_sitter_parseable(self, source: str, language: str) -> bool:
        """Run the installed grammar, without making indexing depend on it."""
        try:
            from tree_sitter_language_pack import get_parser  # type: ignore
            parser = get_parser(language)
            return parser.parse(source.encode("utf-8")).root_node is not None
        except Exception:
            return False

    def _python_symbols(self, source: str) -> list[tuple[str, str, int, int, str | None]]:
        try:
            tree = ast.parse(source)
        except SyntaxError:
            return []
        symbols = []
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                parent = None
                # A compact parent calculation avoids an AST dependency in consumers.
                for owner in ast.walk(tree):
                    if isinstance(owner, ast.ClassDef) and node in owner.body:
                        parent = owner.name
                        break
                symbols.append((node.name, "class" if isinstance(node, ast.ClassDef) else "function",
                                node.lineno, getattr(node, "end_lineno", node.lineno), parent))
        return symbols

    def _generic_symbols(self, source: str, lines: list[str]) -> list[tuple[str, str, int, int, str | None]]:
        matches = list(SYMBOL_RE.finditer(source))
        symbols = []
        for index, match in enumerate(matches):
            start = source.count("\n", 0, match.start()) + 1
            end = source.count("\n", 0, matches[index + 1].start()) if index + 1 < len(matches) else len(lines)
            keyword = match.group(0).strip().split()[-2] if len(match.group(0).strip().split()) > 1 else "symbol"
            kind = {"class": "class", "interface": "interface", "struct": "struct"}.get(keyword, "function")
            symbols.append((match.group(1), kind, start, max(start, end), None))
        return symbols

    def _extract_chunks(self, relative_path: str, source: str) -> list[IndexedChunk]:
        language = detect_language(relative_path, source[:1000])
        lines = source.splitlines()
        imports = [next(item for item in match.groups() if item) for match in IMPORT_RE.finditer(source)]
        references = sorted(set(CALL_RE.findall(source)))
        parsed = self._tree_sitter_parseable(source, language)
        if parsed:
            self.tree_sitter_files += 1
        symbols = self._python_symbols(source) if language == "python" else self._generic_symbols(source, lines)
        if not symbols:
            symbols = [(Path(relative_path).name, "file", 1, max(1, len(lines)), None)]
        chunks = []
        for symbol, kind, start, end, parent in symbols:
            content = "\n".join(lines[start - 1:end])
            if not content.strip():
                continue
            identity = f"{relative_path}:{symbol}:{start}:{end}"
            chunks.append(IndexedChunk(
                chunk_id=hashlib.sha1(identity.encode()).hexdigest()[:16], file_path=relative_path,
                language=language, symbol=symbol, symbol_type=kind, parent_symbol=parent,
                start_line=start, end_line=end, content=content, imports=imports,
                references=[name for name in references if name != symbol],
            ))
        return chunks

    def _rebuild_relationships(self) -> None:
        self.files_by_symbol.clear()
        self.reverse_dependencies.clear()
        known = set(self.chunks_by_file)
        for file_path, chunks in self.chunks_by_file.items():
            for chunk in chunks:
                if chunk.symbol:
                    self.files_by_symbol[chunk.symbol].add(file_path)
            for imported in self.imports_by_file[file_path]:
                targets = self._resolve_import(imported, file_path, known)
                for target in targets:
                    self.reverse_dependencies[target].add(file_path)
            for reference in self.references_by_file[file_path]:
                for target in self.files_by_symbol.get(reference, set()):
                    if target != file_path:
                        self.reverse_dependencies[target].add(file_path)

    @staticmethod
    def _resolve_import(imported: str, source_file: str, known: set[str]) -> set[str]:
        base = imported.replace(".", "/").replace(":", "/").lstrip("/")
        candidates = {base, f"{base}.py", f"{base}.js", f"{base}.ts", f"{base}/index.js", f"{base}/__init__.py"}
        if imported.startswith("."):
            # Python relative imports use dots as package traversal, not a
            # literal filename such as `.payment`.
            parent = Path(source_file).parent
            levels = len(imported) - len(imported.lstrip("."))
            for _ in range(max(0, levels - 1)):
                parent = parent.parent
            prefix = str(parent / imported.lstrip(".")).replace("\\", "/")
            candidates |= {prefix, f"{prefix}.py", f"{prefix}.js", f"{prefix}.ts"}
        return {path for path in known if path in candidates or path.rsplit(".", 1)[0] in candidates}

    def update_file(self, file_path: Path) -> dict:
        relative = self._relative(file_path)
        if not file_path.exists() or not self.is_indexable(file_path):
            self.remove_file(relative)
            return {"action": "removed", "file": relative}
        raw = file_path.read_bytes()
        digest = hashlib.sha256(raw).hexdigest()
        if self.file_hashes.get(relative) == digest:
            return {"action": "unchanged", "file": relative}
        source = raw.decode("utf-8", errors="replace")
        chunks = self._extract_chunks(relative, source)
        self.chunks_by_file[relative] = chunks
        self.imports_by_file[relative] = set(imported for chunk in chunks for imported in chunk.imports)
        self.references_by_file[relative] = set(reference for chunk in chunks for reference in chunk.references)
        self.file_hashes[relative] = digest
        self._sync_vector_file(relative, chunks)
        self._rebuild_relationships()
        return {"action": "indexed", "file": relative, "chunks": len(chunks)}

    def remove_file(self, relative: str) -> None:
        self.chunks_by_file.pop(relative, None)
        self.imports_by_file.pop(relative, None)
        self.references_by_file.pop(relative, None)
        self.file_hashes.pop(relative, None)
        if self.retriever:
            self.retriever.chunks = [chunk for chunk in self.retriever.chunks if chunk.file_path != relative]
        self._rebuild_relationships()

    def search(self, query: str, limit: int = 8) -> list[dict]:
        if self.retriever:
            try:
                vector_results = self.retriever.search(query, top_k=limit)
                by_id = {chunk.chunk_id: chunk for chunks in self.chunks_by_file.values() for chunk in chunks}
                results = []
                for result in vector_results:
                    chunk = by_id.get(str(result.chunk_id))
                    if chunk:
                        item = chunk.public()
                        item["score"] = result.similarity_score
                        item["retrieval"] = "vector"
                        results.append(item)
                if results:
                    return results
            except Exception as exc:
                self.vector_status = f"fallback: {type(exc).__name__}"
                self.last_error = f"Vector search failed: {exc}"
        terms = {term.lower() for term in re.findall(r"[A-Za-z_$][\w$]*", query)}
        scored = []
        for chunks in self.chunks_by_file.values():
            for chunk in chunks:
                haystack = f"{chunk.file_path} {chunk.symbol or ''} {chunk.content}".lower()
                score = sum(haystack.count(term) for term in terms)
                if score:
                    item = chunk.public()
                    item["score"] = score / max(1, len(terms))
                    item["retrieval"] = "deterministic"
                    scored.append(item)
        return sorted(scored, key=lambda item: (-item["score"], item["file_path"], item["start_line"]))[:limit]

    def evidence_for_query(self, query: str, limit: int = 8) -> list[EvidenceSnippet]:
        return [EvidenceSnippet(file=item["file_path"], start_line=item["start_line"], end_line=item["end_line"],
                                content=redact_secrets(item["content"]), symbol=item.get("symbol")) for item in self.search(query, limit)]

    def dependencies(self, path_or_symbol: str) -> dict:
        files = {path_or_symbol} if path_or_symbol in self.chunks_by_file else self.files_by_symbol.get(path_or_symbol, set())
        downstream = sorted({dep for file in files for dep in self.reverse_dependencies.get(file, set())})
        return {"target": path_or_symbol, "files": sorted(files), "imports": {file: sorted(self.imports_by_file.get(file, set())) for file in files},
                "affected_files": downstream}

    def impact(self, file_path: str, symbol: str | None = None, change_type: str = "UNKNOWN") -> ImpactAnalysisInput:
        chunks = self.chunks_by_file.get(file_path, [])
        selected = next((chunk for chunk in chunks if symbol and chunk.symbol == symbol), chunks[0] if chunks else None)
        if not selected:
            raise ValueError("The file or symbol is not indexed.")
        affected: list[ImpactedComponent] = []
        evidence = [EvidenceSnippet(file=selected.file_path, start_line=selected.start_line, end_line=selected.end_line,
                                    content=redact_secrets(selected.content), symbol=selected.symbol)]
        queue, seen, chain = deque([(file_path, [f"{file_path}:{selected.symbol or 'file'}"])]), {file_path}, []
        while queue and len(affected) < 20:
            current, current_chain = queue.popleft()
            for dependent in sorted(self.reverse_dependencies.get(current, set())):
                if dependent in seen:
                    continue
                seen.add(dependent)
                dependent_chunk = self.chunks_by_file[dependent][0]
                affected.append(ImpactedComponent(file=dependent, start_line=dependent_chunk.start_line,
                    end_line=dependent_chunk.end_line, symbol=dependent_chunk.symbol, relationship="imports_or_references"))
                evidence.append(EvidenceSnippet(file=dependent, start_line=dependent_chunk.start_line,
                    end_line=dependent_chunk.end_line, content=redact_secrets(dependent_chunk.content), symbol=dependent_chunk.symbol))
                next_chain = current_chain + [f"{dependent}:{dependent_chunk.symbol or 'file'}"]
                chain.append(" -> ".join(next_chain))
                queue.append((dependent, next_chain))
        return ImpactAnalysisInput(project_id=self.root.name if self.root else "local-project",
            change=ChangeDetail(file=file_path, start_line=selected.start_line, end_line=selected.end_line,
                                symbol=selected.symbol, change_type=change_type),
            impacted_components=affected, impact_chain=chain or [f"{file_path}:{selected.symbol or 'file'}"], evidence=evidence)

    def index_status(self) -> dict:
        return {"status": self.status, "project": str(self.root) if self.root else None,
                "file_count": len(self.chunks_by_file), "chunk_count": sum(map(len, self.chunks_by_file.values())),
                "tree_sitter_files": self.tree_sitter_files, "embedding_status": self.vector_status,
                "last_error": self.last_error}


project_index = ProjectIndex()
