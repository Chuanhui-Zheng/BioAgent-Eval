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
from retrieval.dense_retriever import load_dense_index, load_encoder_from_config
from retrieval.hybrid_retriever import HybridRetriever
from retrieval.router import route_query


def parse_args():
    parser = argparse.ArgumentParser(
        description="Interactive hybrid RRF search. Type a query, get top-k chunk_id values."
    )
    parser.add_argument("--config", type=Path, default=None)
    parser.add_argument("--top-k", type=int, default=None)
    parser.add_argument("--no-router", action="store_true")
    return parser.parse_args()


def print_results(top_k: int, collections: list[str], matched_rules: list[str], results) -> None:
    print(f"top_k={top_k}  collections={collections}  rules={matched_rules}")
    if not results:
        print("(no results)")
        return
    for item in results:
        bm25_rank = item.component_scores.get("bm25_rank")
        dense_rank = item.component_scores.get("dense_rank")
        print(
            f"{item.rank:>2}. {item.chunk_id}\t{item.collection}\t"
            f"rrf={item.score:.4f}\tbm25_rank={bm25_rank}\tdense_rank={dense_rank}"
        )


def main() -> int:
    args = parse_args()
    config = load_retrieval_config(PROJECT_ROOT, args.config)
    top_k = args.top_k or config.top_k
    bm25_dir = config.index_dir
    dense_dir = config.dense_index_dir
    if not (bm25_dir / "index_meta.json").exists():
        raise FileNotFoundError(f"BM25 index not found at {bm25_dir}")
    if not (dense_dir / "index_meta.json").exists():
        raise FileNotFoundError(
            f"Dense index not found at {dense_dir}. Run: python scripts/build_dense_index.py"
        )

    print("Loading corpus, BM25, encoder, and FAISS...")
    corpus = load_corpus_from_config(config)
    bm25_index = load_bm25_index(bm25_dir, corpus.records)
    encoder = load_encoder_from_config(config)
    dense_index = load_dense_index(dense_dir, corpus.records, encoder)
    retriever = HybridRetriever(
        bm25=bm25_index,
        dense=dense_index,
        candidate_k=config.hybrid_candidate_k,
        rrf_k=config.hybrid_rrf_k,
        weight_bm25=config.hybrid_weight_bm25,
        weight_dense=config.hybrid_weight_dense,
    )
    print(
        f"Ready. {len(corpus.records)} chunks. Default top_k={top_k} "
        f"candidate_k={retriever.candidate_k}."
    )
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
        results = retriever.search(raw, top_k=top_k, collections=collections)
        print_results(top_k, collections or [], matched_rules, results)
        print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
