from pathlib import Path
import argparse
import json
import sys
import os

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))
from analysis.evaluation import evaluate_annotated
from server import get_pipeline


def main():
    parser = argparse.ArgumentParser(
        description="Evaluate offline RAG against independently supplied gold labels and export a human-review rubric."
    )
    parser.add_argument("--hosted", action="store_true")
    parser.add_argument("--model", default="gpt-4o-mini")
    parser.add_argument("benchmark", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    active = get_pipeline()
    if args.hosted:
        from generation.aihubmix import AIHubMixGenerator
        from generation.offline import OfflineEvidenceGenerator
        from generation.fallback import FallbackGenerator
        from rag.pipeline import RAGPipeline

        key = os.environ.get("AIHUBMIX_API_KEY", "")
        if not key:
            parser.error("--hosted requires AIHUBMIX_API_KEY in the environment")
        active = RAGPipeline(
            active.retriever,
            active.context_builder,
            FallbackGenerator(
                AIHubMixGenerator(api_key=key, model=args.model),
                OfflineEvidenceGenerator(),
            ),
        )
    report = evaluate_annotated(active, args.benchmark.read_text())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False))
    print(json.dumps({k: v for k, v in report.items() if k != "results"}, indent=2))


if __name__ == "__main__":
    main()
