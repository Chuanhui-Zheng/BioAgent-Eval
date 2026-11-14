from __future__ import annotations

import argparse
import asyncio
import html
import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from bioagent.model import ModelDecision, Usage
from bioagent.runtime import AgentRuntime, RuntimeConfig
from bioagent.tools import Tool, ToolExecutor, ToolRegistry
from bioagent.evaluation import summarize_traces


class EvidenceArgs(BaseModel):
    query: str = Field(min_length=1)
    top_k: int = Field(default=5, ge=1, le=20)


class DemoModel:
    """Deterministic offline adapter for the CLI smoke demo.

    It exercises the same tool-calling loop without claiming to be a scientific LLM.
    """

    model = "offline-demo"

    def decide(self, task: str, messages: list[dict[str, Any]], tools: list[dict[str, Any]]) -> ModelDecision:
        if not any(message.get("role") == "tool" for message in messages):
            return ModelDecision("tool", tool_name="retrieve_evidence",
                                 tool_arguments={"query": task, "top_k": 5},
                                 usage=Usage(estimated=True), model=self.model)
        evidence = messages[-1].get("content", {})
        if isinstance(evidence, dict):
            passages = evidence.get("passages", [])
            if not passages:
                return ModelDecision("final", "No approved evidence was retrieved for this task.",
                                     usage=Usage(estimated=True), model=self.model)
            lines = [f"Retrieved {len(passages)} approved evidence passage(s):"]
            for item in passages[:3]:
                lines.append(f"- {item['title']} [{item['chunk_id']}]: {item['content'][:240]}")
            return ModelDecision("final", "\n".join(lines), usage=Usage(estimated=True), model=self.model)
        return ModelDecision("final", str(evidence), usage=Usage(estimated=True), model=self.model)


def _rag_tool():
    from augmentation.builder import ContextBuilder
    from retrieval.config import load_retrieval_config
    from retrieval.corpus import load_corpus_from_config
    from retrieval.factory import build_search_backend
    from retrieval.service import RetrievalRequest, RetrieverService
    from pathlib import Path

    root = Path(__file__).resolve().parents[2]
    config = load_retrieval_config(root)
    corpus = load_corpus_from_config(config)
    bundle = build_search_backend(config, corpus)
    service = RetrieverService(bundle.backend, bundle.method)
    builder = ContextBuilder()

    def retrieve_evidence(query: str, top_k: int = 5) -> dict[str, Any]:
        retrieval = service.retrieve(RetrievalRequest(query, top_k=top_k))
        context = builder.build(retrieval)
        return {
            "evidence_status": context.evidence_status,
            "limitations": context.limitations,
            "passages": [passage.to_dict() for passage in context.passages],
            "retrieval_method": retrieval.method,
        }

    return retrieve_evidence


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m bioagent", description="BioAgent-Eval Scientific Agent Harness")
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("run", help="Run the offline harness demo against the scientific corpus")
    run.add_argument("--query", required=True)
    run.add_argument("--trace-path")
    run.add_argument("--checkpoint-dir")
    run.add_argument("--hosted", action="store_true", help="Use the configured OpenAI-compatible provider")
    run.add_argument("--llm-provider", default=None)
    run.add_argument("--model", default=None)
    run.add_argument("--base-url", default=None)
    trace = sub.add_parser("trace", help="Inspect a JSONL execution trace")
    trace.add_argument("--trace-path", required=True, type=Path)
    trace.add_argument("--run-id")
    evaluate = sub.add_parser("evaluate", help="Run the existing annotated RAG Evaluation Harness")
    evaluate.add_argument("--dataset", required=True, type=Path)
    evaluate.add_argument("--output", required=True, type=Path)
    report = sub.add_parser("report", help="Render a static HTML report from JSON or JSONL output")
    report.add_argument("--input", required=True, type=Path)
    report.add_argument("--output", required=True, type=Path)
    fault = sub.add_parser("fault-test", help="Run a controlled tool failure scenario")
    fault.add_argument("--scenario", choices=["tool_timeout", "invalid_arguments"], required=True)
    compare = sub.add_parser("compare", help="Compare two runtime configuration files")
    compare.add_argument("--baseline", required=True, type=Path)
    compare.add_argument("--candidate", required=True, type=Path)
    return parser


def _trace_command(path: Path, run_id: str | None) -> int:
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    if run_id:
        rows = [row for row in rows if row.get("run_id") == run_id]
    print(json.dumps(rows, ensure_ascii=False, indent=2))
    return 0 if rows else 1


def _evaluate_command(dataset: Path, output: Path) -> int:
    from analysis.evaluation import evaluate_annotated
    from server import get_pipeline

    report = evaluate_annotated(get_pipeline(), dataset.read_text(encoding="utf-8"))
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: value for key, value in report.items() if key != "results"}, ensure_ascii=False, indent=2))
    return 0


def _report_command(input_path: Path, output_path: Path) -> int:
    raw = input_path.read_text(encoding="utf-8")
    payload = [json.loads(line) for line in raw.splitlines() if line.strip()] if input_path.suffix == ".jsonl" else json.loads(raw)
    summary = summarize_traces(payload) if input_path.suffix == ".jsonl" and isinstance(payload, list) else None
    body = html.escape(json.dumps(payload, ensure_ascii=False, indent=2))
    summary_html = "" if summary is None else f"<h2>Execution metrics</h2><pre>{html.escape(json.dumps(summary, ensure_ascii=False, indent=2))}</pre>"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        "<!doctype html><meta charset='utf-8'><title>BioAgent-Eval Report</title>"
        "<style>body{font:14px system-ui;margin:2rem}pre{white-space:pre-wrap;background:#f5f5f5;padding:1rem}</style>"
        f"<h1>BioAgent-Eval Report</h1>{summary_html}<pre>{body}</pre>", encoding="utf-8"
    )
    print(f"Wrote static report -> {output_path}")
    return 0


def _fault_test(scenario: str) -> int:
    class EmptyArgs(BaseModel):
        pass

    async def slow_tool():
        await asyncio.sleep(0.2)
        return "finished"

    registry = ToolRegistry()
    if scenario == "tool_timeout":
        registry.register(Tool("slow", "A deliberately slow tool", EmptyArgs, slow_tool))
        executor = ToolExecutor(registry, timeout_s=0.01)
        result = asyncio.run(executor.execute("slow", {}))
    else:
        registry.register(Tool("strict", "A tool requiring a field", EvidenceArgs, lambda **kwargs: kwargs))
        executor = ToolExecutor(registry)
        result = asyncio.run(executor.execute("strict", {"top_k": 1}))
    print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
    return 0 if result.status == "error" else 1


def _compare_command(baseline: Path, candidate: Path) -> int:
    try:
        import yaml
    except ModuleNotFoundError:
        print("PyYAML is required for compare; install requirements/api.txt", flush=True)
        return 2
    base = yaml.safe_load(baseline.read_text(encoding="utf-8")) or {}
    cand = yaml.safe_load(candidate.read_text(encoding="utf-8")) or {}
    keys = sorted(set(base) | set(cand))
    differences = {key: {"baseline": base.get(key), "candidate": cand.get(key)}
                   for key in keys if base.get(key) != cand.get(key)}
    print(json.dumps({"baseline": str(baseline), "candidate": str(candidate),
                      "differences": differences,
                      "note": "Configuration diff only; run a benchmark before claiming performance changes."},
                     ensure_ascii=False, indent=2))
    return 0


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "run":
        registry = ToolRegistry()
        registry.register(Tool("retrieve_evidence", "Retrieve approved scientific evidence.", EvidenceArgs,
                               _rag_tool(), cache_ttl_s=60.0))
        model: Any = DemoModel()
        if args.hosted:
            try:
                try:
                    from dotenv import load_dotenv
                    load_dotenv()
                except ModuleNotFoundError:
                    pass
                from generation.llm_provider import build_llm_generator
                from bioagent.llm_adapter import StructuredToolModelAdapter

                provider = build_llm_generator(provider=args.llm_provider, model=args.model,
                                               base_url=args.base_url)
                model = StructuredToolModelAdapter(provider)
            except (ValueError, TypeError) as exc:
                print(f"Hosted model configuration error: {exc}. Set LLM_PROVIDER and LLM_API_KEY.", flush=True)
                return 2
        runtime = AgentRuntime(model, ToolExecutor(registry), RuntimeConfig(
            trace_path=args.trace_path, checkpoint_dir=args.checkpoint_dir))
        result = asyncio.run(runtime.run(args.query))
        print(json.dumps({"run_id": result.run_id, "status": result.status,
                          "answer": result.answer, "trace": result.trace}, ensure_ascii=False, indent=2))
        return 0 if result.status == "completed" else 1
    if args.command == "trace":
        return _trace_command(args.trace_path, args.run_id)
    if args.command == "evaluate":
        return _evaluate_command(args.dataset, args.output)
    if args.command == "report":
        return _report_command(args.input, args.output)
    if args.command == "fault-test":
        return _fault_test(args.scenario)
    if args.command == "compare":
        return _compare_command(args.baseline, args.candidate)
    return 2
