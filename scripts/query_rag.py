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
from generation.llm_provider import PROVIDER_PRESETS, build_llm_generator
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
    parser.add_argument("--provider", choices=("offline", "llm"), default="offline",
                        help="offline, or llm for a hosted OpenAI-compatible provider")
    parser.add_argument("--llm-provider", choices=sorted(PROVIDER_PRESETS), default=None,
                        help="Preset; defaults to LLM_PROVIDER from the environment")
    parser.add_argument("--model", default=None)
    parser.add_argument("--base-url", default=None)
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


def generator_for(args: argparse.Namespace):
    offline = OfflineEvidenceGenerator()
    if args.provider == "offline":
        return offline
    try:
        primary = build_llm_generator(provider=args.llm_provider, model=args.model, base_url=args.base_url)
    except ValueError as exc:
        raise SystemExit(f"{exc}. Copy .env.example to .env and set LLM_PROVIDER/LLM_API_KEY.") from exc
    return FallbackGenerator(primary=primary, fallback=offline)


def main() -> int:
    args = parse_args()
    load_environment()
    config = load_retrieval_config(PROJECT_ROOT)
    corpus = load_corpus_from_config(config)
    backend = load_bm25_index(config.index_dir, corpus.records, expected_chunk_hashes=corpus.chunk_hashes)
    pipeline = RAGPipeline(
        RetrieverService(backend, "bm25"),
        ContextBuilder(),
        generator_for(args),
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
