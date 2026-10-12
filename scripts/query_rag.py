from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import asdict
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from augmentation.builder import ContextBuilder
from generation.aihubmix import AIHubMixGenerator
from generation.fallback import FallbackGenerator
from generation.offline import OfflineEvidenceGenerator
from rag.pipeline import RAGPipeline
from retrieval.bm25_retriever import load_bm25_index
from retrieval.config import load_retrieval_config
from retrieval.corpus import load_corpus_from_config
from retrieval.router import ALL_COLLECTIONS
from retrieval.service import RetrievalRequest, RetrieverService


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Query the evidence-grounded RAG pipeline.")
    parser.add_argument("question")
    parser.add_argument("--provider", choices=("offline", "aihubmix"), default="offline")
    parser.add_argument("--top-k", type=int, default=10)
    parser.add_argument(
        "--collection",
        action="append",
        choices=ALL_COLLECTIONS,
        dest="collections",
        help="Authorized collection; repeat for more than one. Defaults to all.",
    )
    parser.add_argument("--json", action="store_true")
    return parser.parse_args()


def load_environment() -> None:
    try:
        from dotenv import load_dotenv
    except ModuleNotFoundError:
        return
    load_dotenv(PROJECT_ROOT / ".env", override=False)


def generator_for(provider: str):
    offline = OfflineEvidenceGenerator()
    if provider == "offline":
        return offline
    api_key = os.environ.get("AIHUBMIX_API_KEY", "").strip()
    if not api_key:
        raise SystemExit(
            "AIHUBMIX_API_KEY is missing. Copy .env.example to .env and add a new key."
        )
    primary = AIHubMixGenerator(
        api_key=api_key,
        base_url=os.environ.get("AIHUBMIX_BASE_URL", "https://aihubmix.com/v1"),
        model=os.environ.get("AIHUBMIX_MODEL", "nemotron-3-ultra-550b-a55b-free"),
    )
    return FallbackGenerator(primary=primary, fallback=offline)


def main() -> int:
    args = parse_args()
    load_environment()
    config = load_retrieval_config(PROJECT_ROOT)
    corpus = load_corpus_from_config(config)
    backend = load_bm25_index(config.index_dir, corpus.records)
    pipeline = RAGPipeline(
        RetrieverService(backend, "bm25"),
        ContextBuilder(),
        generator_for(args.provider),
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
    print(f"provider: {run.answer.provider}")
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
    if run.answer.diagnostics.get("fallback_from"):
        print(f"fallback_from: {run.answer.diagnostics['fallback_from']}")
    print(f"latency_s: {run.latency_s['total']:.6f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
