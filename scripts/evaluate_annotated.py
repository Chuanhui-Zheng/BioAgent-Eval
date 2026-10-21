from pathlib import Path
import argparse
import json
import sys
import os

try:
    from dotenv import load_dotenv
except ModuleNotFoundError:  # optional
    load_dotenv = None

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))
from analysis.evaluation import evaluate_annotated
from server import get_pipeline


def main():
    parser = argparse.ArgumentParser(
        description="Evaluate offline RAG against independently supplied gold labels and export a human-review rubric."
    )
    parser.add_argument("--hosted", action="store_true", help="Use a hosted OpenAI-compatible LLM")
    parser.add_argument("--llm-provider", default=None, help="Preset; defaults to LLM_PROVIDER")
    parser.add_argument("--model", default=None)
    parser.add_argument("--base-url", default=None)
    parser.add_argument("benchmark", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if load_dotenv:
        load_dotenv(ROOT / ".env", override=False)
    active = get_pipeline()
    if args.hosted:
        from generation.fallback import FallbackGenerator
        from generation.llm_provider import build_llm_generator
        from generation.offline import OfflineEvidenceGenerator
        from rag.pipeline import RAGPipeline

        try:
            primary = build_llm_generator(provider=args.llm_provider, model=args.model, base_url=args.base_url)
        except ValueError as exc:
            parser.error(f"--hosted: {exc} (set LLM_PROVIDER/LLM_API_KEY in the environment or .env)")
        active = RAGPipeline(active.retriever, active.context_builder,
                             FallbackGenerator(primary, OfflineEvidenceGenerator()))
    report = evaluate_annotated(active, args.benchmark.read_text())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False))
    print(json.dumps({k: v for k, v in report.items() if k != "results"}, indent=2))


if __name__ == "__main__":
    main()
