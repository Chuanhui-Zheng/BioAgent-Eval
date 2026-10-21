"""Run the frozen blind benchmark end to end and export a human-review sheet.

Examples
  # offline generator, configured retrieval method
  python scripts/evaluate_blind.py --label offline
  # hosted generator (any OpenAI-compatible preset) on a 25-question sample, judged by a second model
  python scripts/evaluate_blind.py --label deepseek --llm-provider deepseek --limit 25 \\
      --judge-provider openai --judge-model gpt-4o-mini

API keys are read from the environment or .env (LLM_API_KEY / JUDGE_API_KEY);
they are never written to reports. The benchmark's SHA-256 must match its
manifest, so an edited blind file cannot be reported as v1.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

DEFAULT_BENCHMARK = ROOT / "data/evaluation/blind/blind_e2e_v1.jsonl"
RUBRIC = ROOT / "reports/blind_v1/HUMAN_REVIEW_RUBRIC.md"


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--benchmark", type=Path, default=DEFAULT_BENCHMARK)
    parser.add_argument("--label", required=True, help="Run name, e.g. offline or openai-gpt4o-mini")
    parser.add_argument("--retrieval-method", default=None, help="Override pipeline.default_method")
    parser.add_argument("--llm-provider", default=None, help="Hosted generator preset; omit for offline")
    parser.add_argument("--model", default=None)
    parser.add_argument("--base-url", default=None)
    parser.add_argument("--judge-provider", default=None, help="Optional LLM support judge preset")
    parser.add_argument("--judge-model", default=None)
    parser.add_argument("--judge-base-url", default=None)
    parser.add_argument("--limit", type=int, default=None,
                        help="Deterministic stratified sample size (e.g. 25 for hosted runs)")
    parser.add_argument("--output-root", type=Path, default=ROOT / "reports/blind_v1")
    return parser.parse_args()


def verify_frozen(path: Path) -> str:
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    manifest = path.with_name(path.name.replace(".jsonl", ".manifest.json"))
    if manifest.exists():
        expected = json.loads(manifest.read_text())["sha256"]
        if expected != digest:
            raise SystemExit(f"{path} does not match its frozen manifest ({digest[:12]} != {expected[:12]})")
    return digest


def stratified(lines: list[str], limit: int | None) -> list[str]:
    """Round-robin over query types so a small hosted sample still covers every type."""
    if not limit or limit >= len(lines):
        return lines
    groups: dict[str, list[str]] = {}
    for line in lines:
        groups.setdefault(json.loads(line).get("query_type", "?"), []).append(line)
    picked: list[str] = []
    while len(picked) < limit:
        for name in sorted(groups):
            if groups[name] and len(picked) < limit:
                picked.append(groups[name].pop(0))
    return picked


def main() -> int:
    args = parse_args()
    try:
        from dotenv import load_dotenv

        load_dotenv(ROOT / ".env", override=False)
    except ModuleNotFoundError:
        pass
    if args.retrieval_method:
        os.environ["RAG_RETRIEVAL_METHOD"] = args.retrieval_method
    digest = verify_frozen(args.benchmark)
    lines = [line for line in args.benchmark.read_text(encoding="utf-8").splitlines() if line.strip()]
    lines = stratified(lines, args.limit)

    import server
    from analysis.evaluation import evaluate_annotated
    from analysis.support_judge import LLMSupportJudge
    from generation.fallback import FallbackGenerator
    from generation.llm_provider import build_llm_generator
    from generation.offline import OfflineEvidenceGenerator
    from rag.pipeline import RAGPipeline

    pipeline = server.get_pipeline()
    if args.llm_provider:
        pipeline = RAGPipeline(pipeline.retriever, pipeline.context_builder, FallbackGenerator(
            build_llm_generator(provider=args.llm_provider, model=args.model, base_url=args.base_url),
            OfflineEvidenceGenerator()))
    judge = None
    if args.judge_provider:
        judge = LLMSupportJudge(build_llm_generator(
            provider=args.judge_provider, model=args.judge_model, base_url=args.judge_base_url,
            api_key=os.environ.get("JUDGE_API_KEY") or None, max_tokens=200))

    report = evaluate_annotated(pipeline, "\n".join(lines) + "\n", judge=judge)
    report.update({
        "label": args.label,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "frozen_benchmark_sha256": digest,
        "sample": {"questions": len(lines), "limit": args.limit, "strategy": "round-robin by query_type"},
        "retrieval_status": server._RETRIEVAL_STATUS,
        "generator": (pipeline.generator.primary.describe() if args.llm_provider else {"provider": "offline_evidence"}),
    })
    out = args.output_root / args.label
    out.mkdir(parents=True, exist_ok=True)
    (out / "report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False, default=str) + "\n")
    with (out / "human_review_sheet.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["query_id", "query_type", "question", "status", "answer", "citations", "auto_flags",
                         "correctness_1to5", "relevance_1to5", "completeness_1to5", "citation_support_1to5",
                         "clarity_1to5", "harmful_or_overclaiming(Y/N)", "notes", "reviewer"])
        for row in report["results"]:
            flags = [*(f"missing fact: {f}" for f in row["missing_required_facts"]),
                     *(f"number: {f}" for f in row["missing_or_wrong_numbers"]),
                     *(f"forbidden: {f}" for f in row["prohibited_phrases"]),
                     *(f"ungrounded claim: {u['claim'][:60]}" for u in row["support"]["ungrounded"])]
            writer.writerow([row["query_id"], row["query_type"], row["question"], row["status"],
                             row["answer"]["answer"], " ".join(c for claim in row["answer"]["claims"]
                                                                for c in claim["citations"]),
                             " | ".join(flags), "", "", "", "", "", "", "", ""])
    headline = {k: report[k] for k in ("questions", "status_accuracy", "gold_retrieval_hit_rate",
                                       "gold_citation_precision", "gold_citation_recall", "numeric_policy_pass_rate",
                                       "fact_policy_pass_rate", "claim_grounding_rate", "fallback_rate",
                                       "mean_latency_s", "cost", "llm_judge", "retrieval_method")}
    (out / "summary.json").write_text(json.dumps(headline, indent=2, ensure_ascii=False, default=str) + "\n")
    print(json.dumps(headline, indent=2, ensure_ascii=False, default=str))
    print(f"Report: {out}/report.json  Review sheet: {out}/human_review_sheet.csv  Rubric: {RUBRIC}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
