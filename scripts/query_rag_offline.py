from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from augmentation.builder import ContextBuilder
from generation.offline import OfflineEvidenceGenerator
from rag.pipeline import RAGPipeline
from retrieval.bm25_retriever import load_bm25_index
from retrieval.config import load_retrieval_config
from retrieval.corpus import load_corpus_from_config
from retrieval.router import ALL_COLLECTIONS
from retrieval.service import RetrievalRequest, RetrieverService


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run one question through the offline evidence-grounded RAG pipeline."
    )
    parser.add_argument("question", help="Scientific question to answer from the approved corpus.")
    parser.add_argument("--top-k", type=int, default=10)
    parser.add_argument(
        "--collection",
        action="append",
        choices=ALL_COLLECTIONS,
        dest="collections",
        help="Authorized collection; repeat to authorize more than one. Defaults to all.",
    )
    parser.add_argument("--json", action="store_true", help="Print the complete run as JSON.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    config = load_retrieval_config(PROJECT_ROOT)
    corpus = load_corpus_from_config(config)
    backend = load_bm25_index(config.index_dir, corpus.records)
    pipeline = RAGPipeline(
        RetrieverService(backend, "bm25"),
        ContextBuilder(),
        OfflineEvidenceGenerator(),
    )
    run = pipeline.run(
        RetrievalRequest(
            args.question,
            authorized_collections=tuple(args.collections or ALL_COLLECTIONS),
            top_k=args.top_k,
        )
    )
    if args.json:
        print(json.dumps(asdict(run), ensure_ascii=False, indent=2))
        return 0

    print(f"status: {run.answer.status}")
    print(f"answer: {run.answer.answer}")
    print("citations:")
    if run.answer.citations:
        for citation in run.answer.citations:
            print(
                f"  - {citation.get('chunk_id')}: "
                f"{citation.get('source_name')} ({citation.get('source_url')})"
            )
    else:
        print("  - none")
    if run.answer.limitations:
        print("limitations:")
        for limitation in run.answer.limitations:
            print(f"  - {limitation}")
    print(f"validation: {'pass' if run.validation.valid else 'fail'}")
    print(f"latency_s: {run.latency_s['total']:.6f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
