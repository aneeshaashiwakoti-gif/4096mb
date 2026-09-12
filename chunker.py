"""
chunker.py — Turn source files into structured, syntax-aware chunks.

Primary:  llama-index CodeSplitter  (tree-sitter, function/class boundaries)
Fallback: langchain RecursiveCharacterTextSplitter.from_language()
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

logger = logging.getLogger(__name__)

# ── Data model ────────────────────────────────────────────────────────────────

@dataclass
class Chunk:
    """A single embeddable unit of source code."""
    text: str
    file_path: str          # relative to repo root
    start_line: int
    end_line: int
    embedding: Optional[List[float]] = field(default=None, repr=False)

    def to_dict(self) -> dict:
        return {
            "text":       self.text,
            "file_path":  self.file_path,
            "start_line": self.start_line,
            "end_line":   self.end_line,
            "embedding":  self.embedding,
        }


# ── Language mapping ──────────────────────────────────────────────────────────

# Maps file extension → (llama-index language str, langchain Language enum name)
_EXT_MAP: dict[str, tuple[str, str]] = {
    ".py":   ("python",     "PYTHON"),
    ".js":   ("javascript", "JS"),
    ".jsx":  ("javascript", "JS"),
    ".ts":   ("typescript", "TS"),
    ".tsx":  ("typescript", "TS"),
    ".java": ("java",       "JAVA"),
    ".go":   ("go",         "GO"),
    ".rs":   ("rust",       "RUST"),
    ".cpp":  ("cpp",        "CPP"),
    ".cc":   ("cpp",        "CPP"),
    ".c":    ("c",          "C"),
    ".rb":   ("ruby",       "RUBY"),
    ".cs":   ("csharp",     "CSHARP"),
    ".php":  ("php",        "PHP"),
    ".html": ("html",       "HTML"),
    ".md":   ("markdown",   "MARKDOWN"),
}

# ── Helpers ───────────────────────────────────────────────────────────────────

def _detect_language(file_path: str) -> Optional[tuple[str, str]]:
    """Return (llama_lang, langchain_lang) for a file, or None if unknown."""
    ext = Path(file_path).suffix.lower()
    return _EXT_MAP.get(ext)


def _line_offsets(text: str) -> list[int]:
    """Return the character offset of the start of each line (0-indexed)."""
    offsets = [0]
    for i, ch in enumerate(text):
        if ch == "\n":
            offsets.append(i + 1)
    return offsets


def _char_to_line(char_idx: int, offsets: list[int]) -> int:
    """Convert a character offset to a 1-based line number."""
    lo, hi = 0, len(offsets) - 1
    while lo < hi:
        mid = (lo + hi + 1) // 2
        if offsets[mid] <= char_idx:
            lo = mid
        else:
            hi = mid - 1
    return lo + 1  # 1-based


def _chunks_from_nodes(nodes, source: str, rel_path: str) -> List[Chunk]:
    """Convert llama-index TextNodes to Chunk objects with real line numbers."""
    offsets = _line_offsets(source)
    chunks: List[Chunk] = []
    for node in nodes:
        text = node.get_content()
        if not text.strip():
            continue

        # Try to use metadata inserted by CodeSplitter; fall back to search.
        start_char = node.start_char_idx
        end_char   = node.end_char_idx

        if start_char is None or end_char is None:
            # Locate text in source as a best-effort fallback
            start_char = source.find(text)
            end_char   = start_char + len(text) if start_char != -1 else 0

        start_line = _char_to_line(start_char, offsets)
        end_line   = _char_to_line(max(0, end_char - 1), offsets)

        chunks.append(Chunk(
            text=text,
            file_path=rel_path,
            start_line=start_line,
            end_line=end_line,
        ))
    return chunks


# ── Primary splitter: llama-index CodeSplitter ────────────────────────────────

def _try_codesplitter(
    source: str,
    rel_path: str,
    llama_lang: str,
    chunk_size: int,
    chunk_overlap: int,
) -> Optional[List[Chunk]]:
    """
    Attempt to split using llama-index CodeSplitter.
    Returns None if the library / tree-sitter binding is unavailable.
    """
    try:
        from llama_index.core.node_parser import CodeSplitter
        from llama_index.core import Document

        splitter = CodeSplitter(
            language=llama_lang,
            chunk_lines=chunk_size,          # lines per chunk (not tokens here)
            chunk_lines_overlap=chunk_overlap,
            max_chars=chunk_size * 80,       # generous char cap
        )
        doc = Document(text=source, metadata={"file_path": rel_path})
        nodes = splitter.get_nodes_from_documents([doc])
        return _chunks_from_nodes(nodes, source, rel_path)

    except ImportError as err:
        logger.warning("llama-index CodeSplitter import failed for %s: %s — will use fallback.", rel_path, err)
        return None
    except Exception as exc:                 # tree-sitter parse errors, etc.
        logger.warning("CodeSplitter failed for %s: %s (%s) — will use fallback.", rel_path, type(exc).__name__, exc)
        return None


# ── Fallback splitter: langchain RecursiveCharacterTextSplitter ───────────────

def _fallback_splitter(
    source: str,
    rel_path: str,
    langchain_lang: str,
    chunk_size: int,
    chunk_overlap: int,
) -> List[Chunk]:
    """
    Split using langchain's language-aware splitter.
    Falls back to plain character splitting if the language is unknown.
    """
    from langchain_text_splitters import RecursiveCharacterTextSplitter, Language

    try:
        lang_enum = Language[langchain_lang]
        splitter = RecursiveCharacterTextSplitter.from_language(
            language=lang_enum,
            chunk_size=chunk_size * 4,  # approx chars (~4 chars/token)
            chunk_overlap=chunk_overlap * 4,
        )
    except (KeyError, ValueError):
        logger.warning(
            "Unknown langchain language %r for %s; using plain splitter.",
            langchain_lang, rel_path,
        )
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size * 4,
            chunk_overlap=chunk_overlap * 4,
        )

    texts_and_meta = splitter.create_documents([source])
    offsets = _line_offsets(source)
    chunks: List[Chunk] = []

    for doc in texts_and_meta:
        text = doc.page_content
        if not text.strip():
            continue
        start_char = source.find(text)
        if start_char == -1:
            # chunk not found verbatim (shouldn't happen, but be safe)
            start_line = end_line = 0
        else:
            end_char   = start_char + len(text) - 1
            start_line = _char_to_line(start_char, offsets)
            end_line   = _char_to_line(end_char, offsets)

        chunks.append(Chunk(
            text=text,
            file_path=rel_path,
            start_line=start_line,
            end_line=end_line,
        ))
    return chunks


# ── Public API ────────────────────────────────────────────────────────────────

def chunk_file_with_method(
    file_path: str,
    repo_root: str,
    chunk_size: int = 512,
    chunk_overlap: int = 64,
) -> tuple[List[Chunk], str]:
    """
    Read *file_path*, split into syntax-aware chunks, and return (chunks, splitter_method).
    Splitter method is either 'codesplitter' or 'langchain_fallback'.
    """
    abs_path = Path(file_path).resolve()
    rel_path = str(abs_path.relative_to(Path(repo_root).resolve())).replace("\\", "/")

    try:
        source = abs_path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        logger.error("Cannot read %s: %s", file_path, exc)
        return [], "error"

    if not source.strip():
        return [], "empty"

    lang_info = _detect_language(str(abs_path))

    if lang_info is None:
        # Unknown language — plain line-based splitting
        logger.debug("No language detected for %s; using plain splitter.", rel_path)
        return _fallback_splitter(source, rel_path, "__unknown__", chunk_size, chunk_overlap), "langchain_fallback"

    llama_lang, langchain_lang = lang_info

    # Try primary (CodeSplitter), fall back automatically
    chunks = _try_codesplitter(source, rel_path, llama_lang, chunk_size, chunk_overlap)
    if chunks is not None:
        logger.debug("CodeSplitter produced %d chunks for %s", len(chunks), rel_path)
        return chunks, "codesplitter"

    chunks = _fallback_splitter(source, rel_path, langchain_lang, chunk_size, chunk_overlap)
    logger.debug("Fallback splitter produced %d chunks for %s", len(chunks), rel_path)
    return chunks, "langchain_fallback"


def chunk_file(
    file_path: str,
    repo_root: str,
    chunk_size: int = 512,
    chunk_overlap: int = 64,
) -> List[Chunk]:
    """
    Read *file_path*, split it into syntax-aware chunks, and return them.

    Args:
        file_path:    Absolute or relative path to the source file.
        repo_root:    Root of the repository (used to compute relative paths).
        chunk_size:   Target chunk size in lines (CodeSplitter) or ~tokens.
        chunk_overlap: Overlap between adjacent chunks.

    Returns:
        List of Chunk objects (embedding field is None — filled by embedder.py).
    """
    chunks, _ = chunk_file_with_method(file_path, repo_root, chunk_size, chunk_overlap)
    return chunks

