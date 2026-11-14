"""Run a reproducible Agent Harness efficiency benchmark.

This benchmark measures execution infrastructure, not hosted-model scientific
quality. It uses the repository's 100-question RAG dataset, a deterministic
keyword evidence tool over the supplied chunks, and a deterministic model
policy so that baseline/candidate differences are attributable to Harness
configuration rather than network or provider variance.
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import json
import re
import sys
import time
from pathlib import Path
from statistics import mean, median
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from bioagent.model import ModelDecision, Usage
from bioagent.runtime import AgentRuntime, RuntimeConfig
from bioagent.tools import Tool, ToolError, ToolExecutor, ToolRegistry
from pydantic import BaseModel, Field


class EvidenceArgs(BaseModel):
    query: str = Field(min_length=1)
    top_k: int = Field(default=3, ge=1, le=5)


class BenchmarkModel:
    model = "deterministic-harness-benchmark"

    def __init__(self, duplicate_call: bool = True) -> None:
        self.duplicate_call = duplicate_call
        self.decisions = 0

    def decide(self, task: str, messages: list[dict[str, Any]], tools: list[dict[str, Any]]) -> ModelDecision:
        self.decisions += 1
        if self.decisions == 1:
            action = "tool"
            decision = {"query": task, "top_k": 3}
        elif self.duplicate_call and self.decisions == 2:
            action = "tool"
            decision = {"query": task, "top_k": 3}
        else:
            action = "final"
            decision = {}
        encoded = json.dumps(messages, ensure_ascii=False, default=str)
        usage = Usage(max(1, len(encoded) // 4), 20 if action == "tool" else 60, estimated=True)
        return ModelDecision(action, content="Evidence-backed deterministic result.",
                             tool_name="retrieve_evidence" if action == "tool" else None,
                             tool_arguments=decision, usage=usage, model=self.model)


class KeywordEvidence:
    def __init__(self, chunk_path: Path, *, transient_failure: bool = False) -> None:
        self.records = []
        for line in chunk_path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                record = json.loads(line)
                self.records.append(record)
        self.transient_failure = transient_failure
        self.calls = 0
        self.failed_once = False

    def __call__(self, query: str, top_k: int = 3) -> dict[str, Any]:
        self.calls += 1
        if self.transient_failure and not self.failed_once:
            self.failed_once = True
            raise ToolError("network", "controlled transient network failure", retryable=True)
        terms = {term.lower() for term in re.findall(r"[A-Za-z0-9_]+", query) if len(term) > 2}
        scored = []
        for record in self.records:
            haystack = f"{record.get('title', '')} {record.get('content', '')}".lower()
            score = sum(haystack.count(term) for term in terms)
            if score:
                scored.append((score, record))
        scored.sort(key=lambda item: (-item[0], item[1].get("chunk_id", "")))
        return {
            "passages": [
                {"chunk_id": record.get("chunk_id"), "title": record.get("title"),
                 "content": str(record.get("content", ""))[:1200]}
                for _, record in scored[:top_k]
            ],
            "result_count": min(top_k, len(scored)),
        }


def load_questions(path: Path) -> list[str]:
    return [json.loads(line)["query"] for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


async def run_config(questions: list[str], chunks: Path, *, cache: bool,
                     max_context_tokens: int, duplicate_call: bool = True,
                     transient_failure: bool = False) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    tool = KeywordEvidence(chunks, transient_failure=transient_failure)
    registry = ToolRegistry()
    registry.register(Tool("retrieve_evidence", "Retrieve approved evidence", EvidenceArgs, tool,
                           cache_ttl_s=60 if cache else None))
    rows = []
    for query in questions:
        # Each benchmark task gets a fresh deterministic model state.
        runtime = AgentRuntime(BenchmarkModel(duplicate_call=duplicate_call), ToolExecutor(registry),
                               RuntimeConfig(max_context_tokens=max_context_tokens, execution_timeout_s=30))
        started = time.perf_counter()
        result = await runtime.run(query)
        elapsed = time.perf_counter() - started
        calls = result.tool_calls
        rows.append({
            "run_id": result.run_id,
            "status": result.status,
            "latency_s": elapsed,
            "tool_calls": len(calls),
            "external_tool_calls": sum(not call["cache_hit"] for call in calls),
            "cache_hits": sum(call["cache_hit"] for call in calls),
            "duplicate_calls": sum(call["duplicate"] for call in calls),
            "tool_errors": sum(call["status"] == "error" for call in calls),
            "steps": result.steps,
            "input_tokens": result.trace["usage"].get("input_tokens"),
            "output_tokens": result.trace["usage"].get("output_tokens"),
            "total_tokens": result.trace["usage"].get("total_tokens"),
            "estimated_tokens": result.trace["usage"].get("estimated", True),
        })
    return aggregate(rows, cache=cache, max_context_tokens=max_context_tokens), rows


def aggregate(rows: list[dict[str, Any]], *, cache: bool, max_context_tokens: int) -> dict[str, Any]:
    latencies = [row["latency_s"] for row in rows]
    tool_calls = sum(row["tool_calls"] for row in rows)
    errors = sum(row["tool_errors"] for row in rows)
    recovered = sum(row["tool_errors"] > 0 and row["status"] == "completed" for row in rows)
    return {
        "runs": len(rows),
        "completed_rate": sum(row["status"] == "completed" for row in rows) / len(rows),
        "mean_steps": mean(row["steps"] for row in rows),
        "tool_calls_per_task": tool_calls / len(rows),
        "external_tool_calls_per_task": sum(row["external_tool_calls"] for row in rows) / len(rows),
        "duplicate_tool_call_rate": sum(row["duplicate_calls"] for row in rows) / max(1, tool_calls),
        "cache_hit_rate": sum(row["cache_hits"] for row in rows) / max(1, tool_calls),
        "tool_failure_rate": errors / max(1, tool_calls),
        "recovery_success_rate": recovered / max(1, sum(row["tool_errors"] > 0 for row in rows)),
        "tokens_per_task": {
            "input": mean(row["input_tokens"] for row in rows),
            "output": mean(row["output_tokens"] for row in rows),
            "total": mean(row["total_tokens"] for row in rows),
        },
        "latency_s": {
            "mean": mean(latencies),
            "median": median(latencies),
            "p95": sorted(latencies)[max(0, int(len(latencies) * 0.95) - 1)],
        },
        "configuration": {"cache": cache, "max_context_tokens": max_context_tokens},
        "measurement_note": "Deterministic offline Harness benchmark over the repository's RAG question set; token values are estimates from the fixture model.",
    }


def write_report(output: Path, baseline: dict[str, Any], optimized: dict[str, Any], fault: dict[str, Any], rows: list[dict[str, Any]]) -> None:
    output.mkdir(parents=True, exist_ok=True)
    payload = {"benchmark": "agent_harness_v1", "dataset": "data/evaluation/rag_e2e.jsonl",
               "baseline": baseline, "optimized": optimized, "fault_injection": fault}
    (output / "metrics.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    with (output / "per_query.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=sorted(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    def pct(value: float | None) -> str:
        return "—" if value is None else f"{value * 100:.2f}%"
    lines = ["# BioAgent-Eval Agent Harness Benchmark", "", "Deterministic offline infrastructure benchmark; not hosted-model scientific quality.", "", "| Metric | Baseline | Optimized |", "|---|---:|---:|"]
    metrics = [("Completed rate", "completed_rate"), ("Mean total tokens/task", "tokens_per_task.total"),
               ("Mean latency (s)", "latency_s.mean"), ("P95 latency (s)", "latency_s.p95"),
               ("External tool calls/task", "external_tool_calls_per_task"), ("Cache hit rate", "cache_hit_rate"),
               ("Duplicate tool-call rate", "duplicate_tool_call_rate")]
    for label, key in metrics:
        def value(report: dict[str, Any]) -> Any:
            item: Any = report
            for part in key.split("."):
                item = item[part]
            return pct(item) if key == "completed_rate" or key.endswith("rate") else f"{item:.6f}" if isinstance(item, float) else item
        lines.append(f"| {label} | {value(baseline)} | {value(optimized)} |")
    lines += ["", "## Fault injection", "", f"Recovery success rate: {pct(fault['recovery_success_rate'])}", "", "See `metrics.json` and `per_query.csv` for complete results."]
    (output / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    html = "<html><body><h1>BioAgent-Eval Agent Harness Benchmark</h1><pre>" + __import__('html').escape(json.dumps(payload, indent=2)) + "</pre></body></html>"
    (output / "report.html").write_text(html, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", type=Path, default=ROOT / "data/evaluation/rag_e2e.jsonl")
    parser.add_argument("--chunks", type=Path, default=ROOT / "artifacts/chunks/gene_info.chunks.jsonl")
    parser.add_argument("--output", type=Path, default=ROOT / "artifacts/evaluation/agent_harness_v1")
    args = parser.parse_args()
    questions = load_questions(args.dataset)
    if len(questions) < 100:
        raise SystemExit(f"Expected at least 100 benchmark questions, found {len(questions)}")
    questions = questions[:100]
    async def execute():
        baseline, baseline_rows = await run_config(questions, args.chunks, cache=False, max_context_tokens=100000)
        optimized, optimized_rows = await run_config(questions, args.chunks, cache=True, max_context_tokens=1200)
        fault, _ = await run_config(questions, args.chunks, cache=True, max_context_tokens=1200, transient_failure=True)
        fault["injected_failures"] = 1
        fault["recovered_injected_failures"] = int(fault["completed_rate"] == 1.0)
        fault["recovery_success_rate"] = fault["recovered_injected_failures"] / fault["injected_failures"]
        return baseline, optimized, fault, baseline_rows + optimized_rows
    baseline, optimized, fault, rows = asyncio.run(execute())
    write_report(args.output, baseline, optimized, fault, rows)
    print(json.dumps({"baseline": baseline, "optimized": optimized, "fault_injection": fault}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
