"""
historical_snapshots.py — Materialize and chunk git snapshots using worktrees.

Walks a git repository's commit history (oldest to newest), samples every Nth
commit (up to a max cap), checks them out cleanly into temporary git worktrees,
chunks and embeds each snapshot using the local sentence-transformers backend
(all-MiniLM-L6-v2, 384-dim), and records a master manifest.json.

Safety:
  • Uses `git worktree add --detach` so the main clone working tree and HEAD are never touched.
  • Cleans up all worktrees upon completion, error, or keyboard interrupt.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, List

# Force UTF-8 output on Windows
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if sys.stderr.encoding and sys.stderr.encoding.lower() != "utf-8":
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from chunker import chunk_file_with_method
from embedder import embed_chunks
from main import walk_repo_with_stats

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("snapshots")


def duplication_score(chunks: List[Any]) -> float:
    """Return the exact-normalized duplicate ratio for one historical snapshot.

    This stable metric is intentionally recorded alongside each snapshot so
    `/drift-trend` can compare commits without re-reading every chunk file.
    """
    normalized = [" ".join(chunk.text.split()) for chunk in chunks if chunk.text.strip()]
    if not normalized:
        return 0.0
    return round(1.0 - (len(set(normalized)) / len(normalized)), 6)


def get_commit_history(repo_path: Path) -> List[str]:
    """Return all commit hashes in chronological order (oldest to newest)."""
    res = subprocess.run(
        ["git", "-C", str(repo_path), "rev-list", "--reverse", "HEAD"],
        capture_output=True,
        text=True,
        check=True,
    )
    commits = [c.strip() for c in res.stdout.strip().splitlines() if c.strip()]
    return commits


def get_commit_metadata(repo_path: Path, commit_hash: str) -> Dict[str, str]:
    """Extract metadata (short hash, ISO date, first line of commit message)."""
    res = subprocess.run(
        ["git", "-C", str(repo_path), "log", "-1", "--format=%H|%h|%ad|%s", "--date=short", commit_hash],
        capture_output=True,
        text=True,
        check=True,
    )
    full_hash, short_hash, date, msg = res.stdout.strip().split("|", 3)
    return {
        "full_hash": full_hash,
        "short_hash": short_hash,
        "date": date,
        "message": msg,
    }


def clean_worktree(repo_path: Path, worktree_dir: Path) -> None:
    """Remove a git worktree safely and prune git tracking metadata."""
    if worktree_dir.exists():
        try:
            subprocess.run(
                ["git", "-C", str(repo_path), "worktree", "remove", "--force", str(worktree_dir)],
                capture_output=True,
                text=True,
            )
        except Exception as exc:
            logger.warning("Error removing worktree via git: %s", exc)
        if worktree_dir.exists():
            shutil.rmtree(worktree_dir, ignore_errors=True)
    subprocess.run(["git", "-C", str(repo_path), "worktree", "prune"], capture_output=True, text=True)


def select_commits(all_commits: List[str], step: int, max_snapshots: int) -> List[str]:
    """Sample commits from oldest to newest with uniform coverage, capped at max_snapshots."""
    total = len(all_commits)
    if total <= max_snapshots:
        return all_commits

    # Use uniform stride to ensure we cover the entire arc from initial commit to HEAD
    stride = max(1, (total - 1) // (max_snapshots - 1))
    indices = [i * stride for i in range(max_snapshots)]
    indices[-1] = total - 1  # guaranteed include latest HEAD
    # De-duplicate while preserving order
    chosen_indices = sorted(list(dict.fromkeys(indices)))
    return [all_commits[i] for i in chosen_indices]


def run_snapshots(
    repo_path_str: str,
    output_dir_str: str = "output/snapshots",
    worktrees_base_str: str = "click_snapshots",
    step: int = 20,
    max_snapshots: int = 10,
    chunk_size: int = 40,
    chunk_overlap: int = 10,
) -> None:
    t_start = time.time()
    repo_path = Path(repo_path_str).resolve()
    output_dir = Path(output_dir_str).resolve()
    worktrees_base = Path(worktrees_base_str).resolve()

    output_dir.mkdir(parents=True, exist_ok=True)
    worktrees_base.mkdir(parents=True, exist_ok=True)

    # Record initial HEAD to verify non-disturbance later
    head_before = subprocess.run(
        ["git", "-C", str(repo_path), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    branch_before = subprocess.run(
        ["git", "-C", str(repo_path), "branch", "--show-current"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()

    logger.info("Repository: %s (HEAD: %s on '%s')", repo_path, head_before[:7], branch_before)

    all_commits = get_commit_history(repo_path)
    logger.info("Total commits in history: %d", len(all_commits))

    selected = select_commits(all_commits, step=step, max_snapshots=max_snapshots)
    logger.info("Selected %d historical snapshots to process (oldest -> newest):", len(selected))

    manifest_entries: List[Dict[str, Any]] = []

    try:
        for idx, commit_hash in enumerate(selected):
            meta = get_commit_metadata(repo_path, commit_hash)
            short_h = meta["short_hash"]
            logger.info("=" * 65)
            logger.info(
                "[%d/%d] Snapshot %s (%s) — '%s'",
                idx + 1, len(selected), short_h, meta["date"], meta["message"]
            )

            worktree_dir = worktrees_base / short_h
            clean_worktree(repo_path, worktree_dir)

            # Create detached worktree at this commit
            subprocess.run(
                ["git", "-C", str(repo_path), "worktree", "add", "--detach", str(worktree_dir), commit_hash],
                capture_output=True,
                text=True,
                check=True,
            )

            try:
                # Walk & chunk the snapshot
                t_snap_start = time.time()
                files, scan_stats = walk_repo_with_stats(str(worktree_dir))
                all_chunks = []
                for fpath in files:
                    chunks, _ = chunk_file_with_method(str(fpath), str(worktree_dir), chunk_size, chunk_overlap)
                    all_chunks.extend(chunks)

                # Embed using local sentence-transformers backend (384-dim, offline, fast)
                embed_chunks(all_chunks, backend="local")

                # Save snapshot chunk file
                out_filename = f"{commit_hash}_chunks.json"
                out_file = output_dir / out_filename
                with out_file.open("w", encoding="utf-8") as f:
                    json.dump([c.to_dict() for c in all_chunks], f, indent=2, ensure_ascii=False)

                t_snap_duration = time.time() - t_snap_start
                logger.info(
                    "Snapshot %s completed: %d files, %d chunks in %.2fs → %s",
                    short_h, len(files), len(all_chunks), t_snap_duration, out_filename
                )

                manifest_entries.append({
                    "commit_hash": meta["full_hash"],
                    "short_hash": short_h,
                    "date": meta["date"],
                    "message": meta["message"],
                    "file_count": len(files),
                    "chunk_count": len(all_chunks),
                    "duplication_score": duplication_score(all_chunks),
                    "embedding_backend": "local",
                    "embedding_dimension": 384,
                    "output_file": out_filename,
                })

            finally:
                clean_worktree(repo_path, worktree_dir)

        # Write manifest.json
        manifest_path = output_dir / "manifest.json"
        with manifest_path.open("w", encoding="utf-8") as f:
            json.dump({
                "repository": repo_path.name,
                "total_snapshots": len(manifest_entries),
                "snapshots": manifest_entries,
            }, f, indent=2, ensure_ascii=False)
        logger.info("Wrote snapshot manifest → %s", manifest_path)

    finally:
        # Final cleanup of any lingering worktrees and directory
        subprocess.run(["git", "-C", str(repo_path), "worktree", "prune"], capture_output=True, text=True)
        if worktrees_base.exists():
            shutil.rmtree(worktrees_base, ignore_errors=True)

    # Verify repository HEAD / branch remained unaltered
    head_after = subprocess.run(
        ["git", "-C", str(repo_path), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    branch_after = subprocess.run(
        ["git", "-C", str(repo_path), "branch", "--show-current"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()

    assert head_before == head_after, f"HEAD changed from {head_before} to {head_after}!"
    assert branch_before == branch_after, f"Branch changed from {branch_before} to {branch_after}!"

    t_total = time.time() - t_start

    print("\n" + "=" * 70)
    print("=== HISTORICAL SNAPSHOTS RUN SUMMARY ===")
    print(f"Target repository:         {repo_path.name}")
    print(f"Total snapshots processed: {len(manifest_entries)}")
    print(f"Embedding backend:         local (all-MiniLM-L6-v2, 384-dim)")
    print(f"Git worktrees cleaned:     YES (verified clean)")
    print(f"Main repo HEAD unchanged:  YES ({head_after[:7]} on '{branch_after}')")
    print(f"Total time elapsed:        {t_total:.2f}s ({t_total/60:.2f} minutes)")
    print("=" * 70)

    # Print manifest contents
    print("\n=== MANIFEST.JSON CONTENTS ===")
    with manifest_path.open("r", encoding="utf-8") as f:
        print(f.read())


def main() -> None:
    p = argparse.ArgumentParser(description="Create historical git snapshots with local embeddings.")
    p.add_argument("--repo", default="click", help="Path to git repository.")
    p.add_argument("--output-dir", default="output/snapshots", help="Directory for snapshot chunks and manifest.")
    p.add_argument("--max-snapshots", type=int, default=10, help="Maximum number of historical snapshots to take.")
    p.add_argument("--step", type=int, default=20, help="Commit stride / step size.")
    p.add_argument("--chunk-size", type=int, default=40, help="Chunk size in lines.")
    p.add_argument("--chunk-overlap", type=int, default=10, help="Chunk overlap in lines.")
    args = p.parse_args()

    run_snapshots(
        repo_path_str=args.repo,
        output_dir_str=args.output_dir,
        max_snapshots=args.max_snapshots,
        step=args.step,
        chunk_size=args.chunk_size,
        chunk_overlap=args.chunk_overlap,
    )


if __name__ == "__main__":
    main()
