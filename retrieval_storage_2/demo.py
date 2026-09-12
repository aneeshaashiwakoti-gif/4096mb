"""
Person 2: Interactive CLI Demo & Integration Tester
---------------------------------------------------
Demonstrates Person 2's retrieval and cosine similarity search against stored chunks.

Usage:
    python demo.py
    python demo.py --query "where is auth handled?"
"""

import argparse
import os
import sys

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PARENT_DIR = os.path.dirname(CURRENT_DIR)

for path in (CURRENT_DIR, PARENT_DIR):
    if path not in sys.path:
        sys.path.insert(0, path)

try:
    from retrieval import CodebaseRetriever, init_retriever, search
except ImportError:
    from person2_retrieval.retrieval import CodebaseRetriever, init_retriever, search


def run_demo(query: str = None):
    data_path = os.path.join(CURRENT_DIR, "mock_chunks.json")
    print("=" * 70)
    print(" PERSON 2: CODEBASE INTELLIGENCE RETRIEVAL DEMO")
    print(" Track 3: Developer Tooling — Codebase Intelligence & Navigation")
    print("=" * 70)

    print(f"\n[1] Loading code chunks from: {os.path.basename(data_path)}")
    retriever = init_retriever(data_path)
    print(f"    Loaded {len(retriever.chunks)} code chunks into vector index.")

    sample_queries = [
        "where is auth and token verification handled?",
        "what connects to the sqlite database?",
        "how does user registration work?",
        "how is billing or payment processed with stripe?",
        "where are the main API routes defined?"
    ]

    queries_to_run = [query] if query else sample_queries

    for q_idx, q in enumerate(queries_to_run, 1):
        print("\n" + "-" * 70)
        print(f" Query #{q_idx}: \"{q}\"")
        print("-" * 70)

        results = search(q, top_k=3)
        if not results:
            print("  No matching chunks found.")
            continue

        for rank, res in enumerate(results, 1):
            print(f"\n  Match #{rank} (Cosine Similarity: {res['similarity_score']:.4f})")
            print(f"  File:  {res['file_path']}:{res['start_line']}-{res['end_line']}")
            print(f"  Chunk ID: {res['chunk_id']}")
            print("  Code snippet:")
            lines = res['text'].strip().split("\n")
            preview = lines[:4]
            for line in preview:
                print(f"    | {line}")
            if len(lines) > 4:
                print(f"    | ... ({len(lines) - 4} more lines)")

    print("\n" + "=" * 70)
    print(" Demo complete! Output is fully ready for Person 3 (/ask LLM endpoint).")
    print("=" * 70)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Person 2 Retrieval Demo")
    parser.add_argument("--query", "-q", type=str, default=None, help="Custom query to search")
    args = parser.parse_args()
    run_demo(args.query)
