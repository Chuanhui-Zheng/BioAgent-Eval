from __future__ import annotations

import asyncio
import json

from pydantic import BaseModel, Field

from bioagent.model import ModelDecision, Usage
from bioagent.context import ContextManager
from bioagent.runtime import AgentRuntime, RuntimeConfig
from bioagent.tools import Tool, ToolExecutor, ToolRegistry
from bioagent.idempotency import SQLiteIdempotencyStore


class AddArgs(BaseModel):
    left: int
    right: int


class MockModel:
    model = "mock-agent"

    def decide(self, task, messages, tools):
        if not any(message.get("role") == "tool" for message in messages):
            return ModelDecision("tool", tool_name="add", tool_arguments={"left": 2, "right": 3},
                                 usage=Usage(4, 2), model=self.model)
        return ModelDecision("final", f"result={messages[-1]['content']}",
                             usage=Usage(3, 1), model=self.model)


def test_runtime_executes_tool_and_records_usage(tmp_path):
    registry = ToolRegistry()
    registry.register(Tool("add", "Add two integers", AddArgs, lambda left, right: left + right,
                           cache_ttl_s=60))
    trace_path = tmp_path / "traces.jsonl"
    runtime = AgentRuntime(MockModel(), ToolExecutor(registry), RuntimeConfig(
        checkpoint_dir=str(tmp_path / "checkpoints"), trace_path=str(trace_path)))

    result = asyncio.run(runtime.run("add numbers"))

    assert result.status == "completed"
    assert result.answer == "result=5"
    assert result.trace["usage"]["total_tokens"] == 10
    assert result.tool_calls[0]["result"] == 5
    assert trace_path.exists()
    assert json.loads(trace_path.read_text()) ["final_status"] == "completed"
    assert list((tmp_path / "checkpoints").glob("*.json"))


def test_invalid_tool_arguments_are_structured_errors():
    registry = ToolRegistry()
    registry.register(Tool("add", "Add two integers", AddArgs, lambda left, right: left + right))
    result = asyncio.run(ToolExecutor(registry).execute("add", {"left": "bad", "right": 3}))
    assert result.status == "error"
    assert result.error_type == "invalid_arguments"


def test_tool_permission_and_idempotency_guards():
    registry = ToolRegistry()
    registry.register(Tool("write", "A side-effecting tool", AddArgs,
                           lambda left, right: left + right, permission="write",
                           side_effect=True, requires_idempotency_key=True))
    executor = ToolExecutor(registry)
    denied = asyncio.run(executor.execute("write", {"left": 1, "right": 2}))
    assert denied.error_type == "permission_denied"
    executor.allowed_permissions = frozenset({"default", "write"})
    missing = asyncio.run(executor.execute("write", {"left": 1, "right": 2}))
    assert missing.error_type == "missing_idempotency_key"
    unconfigured = asyncio.run(executor.execute("write", {"left": 1, "right": 2}, idempotency_key="run-1"))
    assert unconfigured.error_type == "idempotency_store_unconfigured"


def test_side_effect_result_is_replayed_from_durable_idempotency_store(tmp_path):
    calls = []
    registry = ToolRegistry()
    registry.register(Tool("write", "A side-effecting tool", AddArgs,
                           lambda left, right: calls.append((left, right)) or left + right,
                           permission="write", side_effect=True))
    executor = ToolExecutor(registry, allowed_permissions=frozenset({"default", "write"}),
                            idempotency_store=SQLiteIdempotencyStore(tmp_path / "idempotency.sqlite"))
    first = asyncio.run(executor.execute("write", {"left": 1, "right": 2}, idempotency_key="run-1"))
    second = asyncio.run(executor.execute("write", {"left": 1, "right": 2}, idempotency_key="run-1"))
    assert first.status == "success"
    assert second.status == "success"
    assert second.idempotency_replay is True
    assert calls == [(1, 2)]


def test_context_manager_preserves_task_and_latest_tool_result():
    manager = ContextManager(max_tokens=20)
    messages = [{"role": "user", "content": "task"}]
    messages.extend({"role": "tool", "content": "evidence " * 100} for _ in range(3))
    prepared, info = manager.prepare(messages)
    assert prepared[0]["content"] == "task"
    assert prepared[-1]["content"].startswith("evidence")
    assert info["compressed"] is True


def test_context_manager_preserves_evidence_ids_when_compressing():
    manager = ContextManager(max_tokens=30)
    messages = [{"role": "user", "content": "task"},
                {"role": "tool", "content": {"passages": [
                    {"chunk_id": "chunk-1", "title": "BRCA1 evidence", "content": "evidence"}
                ]}},
                {"role": "tool", "content": "older evidence " * 100}]
    prepared, info = manager.prepare(messages)
    assert "chunk-1" in info["preserved_evidence_ids"]
    assert "chunk-1" in prepared[1]["content"]


def test_runtime_can_resume_checkpoint(tmp_path):
    registry = ToolRegistry()
    registry.register(Tool("add", "Add two integers", AddArgs, lambda left, right: left + right))
    runtime = AgentRuntime(MockModel(), ToolExecutor(registry), RuntimeConfig(
        max_steps=1, checkpoint_dir=str(tmp_path / "checkpoints")))
    first = asyncio.run(runtime.run("add numbers"))
    checkpoint = next((tmp_path / "checkpoints").glob("*.json"))

    resumed_runtime = AgentRuntime(MockModel(), ToolExecutor(registry), RuntimeConfig(
        max_steps=3, checkpoint_dir=str(tmp_path / "checkpoints")))
    resumed = asyncio.run(resumed_runtime.resume(checkpoint))

    assert first.status == "max_steps"
    assert resumed.status == "completed"
    assert resumed.answer == "result=5"
