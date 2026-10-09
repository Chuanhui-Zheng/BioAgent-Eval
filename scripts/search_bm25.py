from __future__ import annotations

import argparse
import json
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
    parser = argparse.ArgumentParser(description="Query the CS-46 BM25 index.")
    parser.add_argument("query", type=str)
    parser.add_argument("--config", type=Path, default=None)
    parser.add_argument("--index-dir", type=Path, default=None)
    parser.add_argument("--top-k", type=int, default=None)
    parser.add_argument("--no-router", action="store_true")
    parser.add_argument("--collections", nargs="*", default=None)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    config = load_retrieval_config(PROJECT_ROOT, args.config)
    top_k = args.top_k or config.top_k
    index_dir = args.index_dir or config.index_dir
    corpus = load_corpus_from_config(config)
    index = load_bm25_index(index_dir, corpus.records)

    collections = args.collections
    matched_rules: list[str] = []
    if collections is None and not args.no_router:
        decision = route_query(args.query, available_collections=[s.collection for s in config.chunk_sources])
        collections = decision.collections
        matched_rules = decision.matched_rules

    results = index.search(args.query, top_k=top_k, collections=collections)
    payload = {
        "query": args.query,
        "top_k": top_k,
        "collections": collections,
        "matched_rules": matched_rules,
        "results": [
            {
                "rank": item.rank,
                "chunk_id": item.chunk_id,
                "collection": item.collection,
                "score": item.score,
                "title": item.chunk.get("title"),
            }
            for item in results
        ],
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
