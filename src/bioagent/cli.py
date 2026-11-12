from __future__ import annotations

import argparse
import asyncio
import json
from typing import Any

from pydantic import BaseModel, Field

from bioagent.model import ModelDecision, Usage
from bioagent.runtime import AgentRuntime, RuntimeConfig
from bioagent.tools import Tool, ToolExecutor, ToolRegistry


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
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "run":
        registry = ToolRegistry()
        registry.register(Tool("retrieve_evidence", "Retrieve approved scientific evidence.", EvidenceArgs,
                               _rag_tool(), cache_ttl_s=60.0))
        runtime = AgentRuntime(DemoModel(), ToolExecutor(registry), RuntimeConfig(
            trace_path=args.trace_path, checkpoint_dir=args.checkpoint_dir))
        result = asyncio.run(runtime.run(args.query))
        print(json.dumps({"run_id": result.run_id, "status": result.status,
                          "answer": result.answer, "trace": result.trace}, ensure_ascii=False, indent=2))
        return 0 if result.status == "completed" else 1
    return 2
