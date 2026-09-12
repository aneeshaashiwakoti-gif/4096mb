"""
main.py — Orchestrator: repo walk → chunk → embed → save chunks.json

Usage:
    python main.py --repo <path-to-repo>            # full run
    python main.py --repo test_repo --single-file test_repo/sample.py  # one-file smoke test
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import List

# Force UTF-8 output on Windows (avoids cp1252 UnicodeEncodeError for source previews)
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if sys.stderr.encoding and sys.stderr.encoding.lower() != "utf-8":
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from dotenv import load_dotenv
from tqdm import tqdm

from chunker import Chunk, chunk_file
from embedder import embed_chunks

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

# ── File-walk config ──────────────────────────────────────────────────────────

# Directories to skip entirely
_SKIP_DIRS: set[str] = {
    ".git", ".hg", ".svn",
    "node_modules", "__pycache__", ".mypy_cache", ".pytest_cache",
    "venv", ".venv", "env", ".env",
    "dist", "build", ".next", ".nuxt",
    "target",   # Rust/Java
    "vendor",   # Go
    ".idea", ".vscode",
    "output",   # our own output dir
}

# Extensions to include (add more as needed)
_INCLUDE_EXTS: set[str] = {
    ".py", ".js", ".jsx", ".ts", ".tsx",
    ".java", ".go", ".rs", ".cpp", ".cc", ".c", ".h", ".hpp",
    ".rb", ".cs", ".php", ".swift", ".kt", ".kts",
    ".sh", ".bash",
    ".html", ".css", ".scss",
    ".md", ".markdown",
    ".yaml", ".yml", ".toml", ".json",
    ".sql",
}

# Binary / irrelevant suffixes to skip (belt-and-suspenders)
_SKIP_EXTS: set[str] = {
    ".png", ".jpg", ".jpeg", ".gif", ".svg", ".ico", ".webp",
    ".pdf", ".docx", ".xlsx",
    ".zip", ".tar", ".gz", ".bz2", ".xz", ".7z",
    ".exe", ".dll", ".so", ".dylib", ".wasm",
    ".pyc", ".pyo", ".pyd",
    ".lock",
    ".DS_Store",
}

MAX_FILE_BYTES = 512 * 1024  # skip files larger than 512 KB


def _is_binary(file_path: Path) -> bool:
    """Quick binary-sniff: check first 8 KB for null bytes."""
    try:
        chunk = file_path.read_bytes()[:8192]
        return b"\x00" in chunk
    except OSError:
        return True


@dataclass
class ScanStats:
    total_files_scanned: int = 0
    total_files_processed: int = 0
    skipped_pruned_dir: int = 0
    skipped_binary: int = 0
    skipped_extension: int = 0
    skipped_oversized: int = 0
    skipped_error: int = 0
    skipped_empty: int = 0
    chunks_codesplitter: int = 0
    chunks_langchain: int = 0
    skip_details: list[tuple[str, str]] = field(default_factory=list)
    processed_details: list[tuple[str, str, int]] = field(default_factory=list)


def walk_repo_with_stats(repo_root: str) -> tuple[List[Path], ScanStats]:
    """
    Recursively collect source files from *repo_root*.
    Skips binaries, oversized files, and ignored dirs/extensions while recording statistics.
    """
    root = Path(repo_root).resolve()
    collected: List[Path] = []
    stats = ScanStats()

    for dirpath, dirnames, filenames in os.walk(root):
        # Prune skip dirs in-place so os.walk doesn't descend into them
        original_dirs = list(dirnames)
        dirnames[:] = [d for d in dirnames if d not in _SKIP_DIRS and not d.startswith(".")]
        pruned = [d for d in original_dirs if d not in dirnames]
        for d in pruned:
            stats.skipped_pruned_dir += 1
            rel_dir = str((Path(dirpath) / d).relative_to(root)).replace("\\", "/")
            stats.skip_details.append((rel_dir, "pruned directory"))

        for fname in filenames:
            stats.total_files_scanned += 1
            fpath = Path(dirpath) / fname
            rel_path = str(fpath.relative_to(root)).replace("\\", "/")
            ext = fpath.suffix.lower()

            if ext in _SKIP_EXTS:
                stats.skipped_extension += 1
                stats.skip_details.append((rel_path, f"skip extension ({ext})"))
                continue
            if _INCLUDE_EXTS and ext not in _INCLUDE_EXTS:
                stats.skipped_extension += 1
                stats.skip_details.append((rel_path, f"unsupported extension ({ext or 'no ext'})"))
                continue
            try:
                if fpath.stat().st_size > MAX_FILE_BYTES:
                    stats.skipped_oversized += 1
                    stats.skip_details.append((rel_path, f"oversized (> {MAX_FILE_BYTES} bytes)"))
                    continue
            except OSError as exc:
                stats.skipped_error += 1
                stats.skip_details.append((rel_path, f"stat error: {exc}"))
                continue

            if _is_binary(fpath):
                stats.skipped_binary += 1
                stats.skip_details.append((rel_path, "binary file (null bytes detected)"))
                continue

            collected.append(fpath)

    stats.total_files_processed = len(collected)
    logger.info("Found %d source files in %s (scanned %d files total)", len(collected), repo_root, stats.total_files_scanned)
    return collected, stats


def walk_repo(repo_root: str) -> List[Path]:
    files, _ = walk_repo_with_stats(repo_root)
    return files


# ── Save ──────────────────────────────────────────────────────────────────────

def save_chunks(chunks: List[Chunk], output_path: str) -> None:
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as f:
        json.dump([c.to_dict() for c in chunks], f, indent=2, ensure_ascii=False)
    logger.info("Saved %d chunks → %s", len(chunks), output_path)


# ── Single-file smoke test ────────────────────────────────────────────────────

def run_single_file(
    file_path: str,
    repo_root: str,
    chunk_size: int,
    chunk_overlap: int,
    backend: str,
    output_path: str,
    no_embed: bool = False,
) -> None:
    """End-to-end on one file; great for a quick sanity check."""
    logger.info("=== Single-file mode: %s ===", file_path)

    from chunker import chunk_file_with_method
    chunks, method = chunk_file_with_method(file_path, repo_root, chunk_size, chunk_overlap)
    if not chunks:
        logger.error("No chunks produced for %s — check the file.", file_path)
        sys.exit(1)

    cs_count = len(chunks) if method == "codesplitter" else 0
    lc_count = len(chunks) if method == "langchain_fallback" else 0

    print("\n" + "=" * 60)
    print("=== SUMMARY REPORT (Single File) ===")
    print(f"File processed: {file_path}")
    print(f"Splitter used:  {method}")
    print(f"Total chunks:   {len(chunks)} (CodeSplitter: {cs_count}, Langchain: {lc_count})")
    print("=" * 60 + "\n")

    logger.info("Produced %d chunks — first chunk preview:", len(chunks))
    c0 = chunks[0]
    print(f"\n{'-'*60}")
    print(f"  file:  {c0.file_path}")
    print(f"  lines: {c0.start_line}-{c0.end_line}")
    print(f"  text preview:\n{c0.text[:300]}{'...' if len(c0.text) > 300 else ''}")
    print(f"{'-'*60}\n")

    if no_embed:
        logger.info("--no-embed: skipping embedding. All chunk boundaries:")
        for i, c in enumerate(chunks):
            print(f"  [{i:>2}] lines {c.start_line:>4}-{c.end_line:<4}  ({len(c.text):>5} chars)")
    else:
        logger.info("Embedding %d chunks via '%s' backend…", len(chunks), backend)
        embed_chunks(chunks, backend=backend)
        sample_emb = next((c.embedding for c in chunks if c.embedding), None)
        if sample_emb:
            logger.info("Embedding dimension: %d", len(sample_emb))
        else:
            logger.warning("No embedding returned — check your API key / backend.")

    save_chunks(chunks, output_path)


# ── Full repo run ─────────────────────────────────────────────────────────────

def run_full(
    repo_root: str,
    chunk_size: int,
    chunk_overlap: int,
    backend: str,
    output_path: str,
    no_embed: bool = False,
) -> None:
    from chunker import chunk_file_with_method

    t0 = time.time()
    files, stats = walk_repo_with_stats(repo_root)
    if not files:
        logger.error("No source files found in %s", repo_root)
        sys.exit(1)

    t_chunk_start = time.time()
    all_chunks: List[Chunk] = []
    for fpath in tqdm(files, desc="Chunking", unit="file"):
        rel_fpath = str(fpath.relative_to(Path(repo_root).resolve())).replace("\\", "/")
        chunks, method = chunk_file_with_method(str(fpath), repo_root, chunk_size, chunk_overlap)
        if method == "empty":
            stats.skipped_empty += 1
            stats.skip_details.append((rel_fpath, "empty or whitespace-only file (0 chunks produced)"))
        elif method == "error":
            stats.skipped_error += 1
            stats.skip_details.append((rel_fpath, "read/decode error"))
        elif method == "codesplitter":
            stats.chunks_codesplitter += len(chunks)
            stats.processed_details.append((rel_fpath, "CodeSplitter", len(chunks)))
        else:
            stats.chunks_langchain += len(chunks)
            stats.processed_details.append((rel_fpath, "Langchain fallback", len(chunks)))
        all_chunks.extend(chunks)

    t_chunk_end = time.time()
    chunk_time = t_chunk_end - t_chunk_start

    t_embed_start = time.time()
    if not no_embed:
        logger.info("Embedding via '%s' backend…", backend)
        embed_chunks(all_chunks, backend=backend)
    else:
        logger.info("--no-embed set: skipping embedding step.")
    t_embed_end = time.time()
    embed_time = t_embed_end - t_embed_start
    total_time = t_embed_end - t0

    save_chunks(all_chunks, output_path)

    # Print requested comprehensive summary report
    print("\n" + "=" * 65)
    print("=== REPO SCAN & CHUNKING SUMMARY ===")
    print(f"Repository target:         {repo_root}")
    print(f"Total files scanned:       {stats.total_files_scanned}")
    total_skipped = (stats.skipped_binary + stats.skipped_extension +
                     stats.skipped_oversized + stats.skipped_error + stats.skipped_empty)
    active_processed = stats.total_files_processed - stats.skipped_empty
    print(f"Files processed (chunks > 0): {active_processed}")
    print(f"Files skipped / 0-chunks:  {total_skipped}")
    print(f"  - Binary (null-byte):    {stats.skipped_binary}")
    print(f"  - Empty / whitespace:    {stats.skipped_empty}")
    print(f"  - Extension / non-code:  {stats.skipped_extension}")
    print(f"  - Oversized (>512KB):    {stats.skipped_oversized}")
    print(f"  - Read/stat errors:      {stats.skipped_error}")
    print(f"Pruned directories:        {stats.skipped_pruned_dir}")
    print(f"Total chunks produced:     {len(all_chunks)}")
    print(f"  - From CodeSplitter:     {stats.chunks_codesplitter}")
    print(f"  - From Langchain fallback: {stats.chunks_langchain}")
    print("-" * 65)
    print("=== PIPELINE TIMING BREAKDOWN ===")
    print(f"  • Chunking duration:     {chunk_time:.2f}s")
    print(f"  • Embedding duration:    {embed_time:.2f}s")
    print(f"  • Total end-to-end time: {total_time:.2f}s ({total_time/60:.2f} min)")
    print("=" * 65)

    if stats.processed_details:
        print("\n--- Processed Files Breakdown ---")
        for f, meth, count in stats.processed_details:
            print(f"  ✓ {f} -> {count} chunk(s) via [{meth}]")

    if stats.skip_details:
        print("\n--- Skipped Items Details ---")
        for item, reason in stats.skip_details:
            print(f"  • {item} -> [{reason}]")
        print("-" * 65 + "\n")


# ── CLI ───────────────────────────────────────────────────────────────────────

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Chunk a code repo and embed each chunk.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("--repo",        required=True,  help="Path to the repo (or test_repo/) to process.")
    p.add_argument("--single-file", default=None,   help="Run only on this file (smoke-test mode).")
    p.add_argument("--backend",     default=None,   help="Override EMBEDDING_BACKEND ('gemini' or 'local').")
    p.add_argument("--chunk-size",  type=int, default=None, help="Override CHUNK_SIZE.")
    p.add_argument("--chunk-overlap", type=int, default=None, help="Override CHUNK_OVERLAP.")
    p.add_argument("--output",      default=None,   help="Override output file path.")
    p.add_argument("--no-embed",    action="store_true", help="Skip embedding (chunking smoke-test only).")
    return p.parse_args()


def main() -> None:
    load_dotenv()  # load .env if present

    args = parse_args()

    # Resolve config with env-var defaults
    backend      = args.backend      or os.getenv("EMBEDDING_BACKEND", "gemini")
    chunk_size   = args.chunk_size   or int(os.getenv("CHUNK_SIZE",   "40"))
    chunk_overlap= args.chunk_overlap or int(os.getenv("CHUNK_OVERLAP", "10"))
    output_dir   = os.getenv("OUTPUT_DIR",  "output")
    output_file  = os.getenv("OUTPUT_FILE", "chunks.json")
    output_path  = args.output or str(Path(output_dir) / output_file)

    logger.info("Config → backend=%s  chunk_size=%d  overlap=%d  output=%s",
                backend, chunk_size, chunk_overlap, output_path)

    if args.single_file:
        run_single_file(
            file_path=args.single_file,
            repo_root=args.repo,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            backend=backend,
            output_path=output_path,
            no_embed=args.no_embed,
        )
    else:
        run_full(
            repo_root=args.repo,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            backend=backend,
            output_path=output_path,
            no_embed=args.no_embed,
        )


if __name__ == "__main__":
    main()
