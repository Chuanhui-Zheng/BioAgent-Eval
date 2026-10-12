from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from retrieval.bm25_retriever import load_bm25_index
from retrieval.config import load_retrieval_config
from retrieval.corpus import load_corpus_from_config
from retrieval.router import route_query


def parse_args():
    parser = argparse.ArgumentParser(
        description="Interactive BM25 search. Type a query, get top-k chunk_id values."
    )
    parser.add_argument("--config", type=Path, default=None)
    parser.add_argument("--index-dir", type=Path, default=None)
    parser.add_argument("--top-k", type=int, default=None)
    parser.add_argument("--no-router", action="store_true")
    return parser.parse_args()


def print_results(query: str, top_k: int, collections: list[str], matched_rules: list[str], results) -> None:
    print(f"top_k={top_k}  collections={collections}  rules={matched_rules}")
    if not results:
        print("(no results)")
        return
    for item in results:
        print(f"{item.rank:>2}. {item.chunk_id}\t{item.collection}\t{item.score:.4f}")


def main() -> int:
    args = parse_args()
    config = load_retrieval_config(PROJECT_ROOT, args.config)
    top_k = args.top_k or config.top_k
    index_dir = args.index_dir or config.index_dir

    print("Loading corpus and BM25 index...")
    corpus = load_corpus_from_config(config)
    index = load_bm25_index(index_dir, corpus.records)
    print(f"Ready. {len(corpus.records)} chunks. Default top_k={top_k}.")
    print("Enter a query. Commands: k=5  (change top_k),  q  (quit).")

    while True:
        try:
            raw = input("query> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return 0
        if not raw:
            continue
        lowered = raw.lower()
        if lowered in {"q", "quit", "exit"}:
            return 0
        if lowered.startswith("k="):
            try:
                top_k = int(raw.split("=", 1)[1].strip())
                if top_k <= 0:
                    raise ValueError
                print(f"top_k set to {top_k}")
            except ValueError:
                print("Usage: k=5")
            continue

        matched_rules: list[str] = []
        collections = None
        if not args.no_router:
            decision = route_query(raw, available_collections=[s.collection for s in config.chunk_sources])
            collections = decision.collections
            matched_rules = decision.matched_rules
        results = index.search(raw, top_k=top_k, collections=collections)
        print_results(raw, top_k, collections or [], matched_rules, results)
        print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
