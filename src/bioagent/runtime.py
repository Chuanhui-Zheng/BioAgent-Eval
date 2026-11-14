from __future__ import annotations

import asyncio
import hashlib
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from bioagent.checkpoint import Checkpoint
from bioagent.context import ContextManager
from bioagent.model import ModelAdapter, Usage
from bioagent.retry import RetryPolicy
from bioagent.tools import ToolExecutor, ToolExecution
from bioagent.tracing import Trace


@dataclass(frozen=True)
class RuntimeConfig:
    max_steps: int = 8
    execution_timeout_s: float = 120.0
    retry: RetryPolicy = field(default_factory=RetryPolicy)
    checkpoint_dir: str | None = None
    trace_path: str | None = None
    max_context_tokens: int = 6000
    max_tool_calls: int = 16


@dataclass
class RunResult:
    run_id: str
    status: str
    answer: str
    steps: int
    tool_calls: list[dict[str, Any]]
    trace: dict[str, Any]


class AgentRuntime:
    def __init__(self, model: ModelAdapter, tools: ToolExecutor, config: RuntimeConfig | None = None) -> None:
        self.model = model
        self.tools = tools
        self.config = config or RuntimeConfig()

    async def run(self, task: str, *, run_id: str | None = None,
                  _messages: list[dict[str, Any]] | None = None,
                  _prior_calls: list[ToolExecution] | None = None,
                  _start_step: int = 0) -> RunResult:
        if not task.strip():
            raise ValueError("task must not be empty")
        run_id = run_id or hashlib.sha256(f"{task}|{time.time_ns()}".encode()).hexdigest()[:16]
        trace = Trace(run_id, task, getattr(self.model, "model", "unknown"))
        messages: list[dict[str, Any]] = list(_messages or [{"role": "user", "content": task}])
        calls: list[ToolExecution] = list(_prior_calls or [])
        seen_calls: set[str] = {self.tools.cache_key(call.tool_name, call.arguments) for call in calls}
        usage = Usage()
        context_manager = ContextManager(self.config.max_context_tokens)

        async def loop() -> RunResult:
            for step in range(_start_step + 1, self.config.max_steps + 1):
                model_messages, context_info = context_manager.prepare(messages)
                trace.event("context_prepared", step=step, **context_info)
                decision = self.model.decide(task, model_messages, self.tools.registry.schemas())
                usage.add(decision.usage)
                trace.event("model_decision", step=step, action=decision.action,
                            tool_name=decision.tool_name, usage=decision.usage.to_dict())
                if decision.action == "final":
                    trace.final_status = "completed"
                    trace.usage = usage.to_dict()
                    result = RunResult(run_id, "completed", decision.content, step,
                                       [call.to_dict() for call in calls], trace.to_dict())
                    self._persist(result, task, messages, calls, step)
                    return result
                if not decision.tool_name:
                    trace.final_status = "failed"
                    return RunResult(run_id, "failed", "Model selected no tool.", step, [], trace.to_dict())
                if len(calls) >= self.config.max_tool_calls:
                    trace.final_status = "tool_budget_exceeded"
                    trace.usage = usage.to_dict()
                    result = RunResult(run_id, "tool_budget_exceeded",
                                       "Agent reached the maximum tool-call budget.", step,
                                       [call.to_dict() for call in calls], trace.to_dict())
                    self._persist(result, task, messages, calls, step)
                    return result
                call_key = self.tools.cache_key(decision.tool_name, decision.tool_arguments)
                execution = await self._execute_with_retry(
                    decision.tool_name, decision.tool_arguments,
                    idempotency_key=f"{run_id}:{step}:{call_key}",
                )
                execution.duplicate = call_key in seen_calls
                seen_calls.add(call_key)
                calls.append(execution)
                trace.event("tool_execution", step=step, **execution.to_dict())
                messages.append({"role": "assistant", "tool_call": {
                    "name": decision.tool_name, "arguments": decision.tool_arguments
                }})
                messages.append({"role": "tool", "name": decision.tool_name, "content": execution.result})
                if execution.status == "error":
                    # The model receives the structured error and may recover on its next turn.
                    continue
            trace.final_status = "max_steps"
            trace.usage = usage.to_dict()
            result = RunResult(run_id, "max_steps", "Agent reached the maximum execution steps.",
                               self.config.max_steps, [call.to_dict() for call in calls], trace.to_dict())
            self._persist(result, task, messages, calls, self.config.max_steps)
            return result

        try:
            return await asyncio.wait_for(loop(), timeout=self.config.execution_timeout_s)
        except asyncio.TimeoutError:
            trace.final_status = "timeout"
            trace.usage = usage.to_dict()
            result = RunResult(run_id, "timeout", "Agent execution timed out.", len(calls),
                               [call.to_dict() for call in calls], trace.to_dict())
            self._persist(result, task, messages, calls, len(calls))
            return result

    async def resume(self, checkpoint_path: Path) -> RunResult:
        """Resume a non-completed run from a persisted checkpoint."""
        checkpoint = Checkpoint.load(checkpoint_path)
        if checkpoint.status == "completed":
            raise ValueError("cannot resume a completed checkpoint")
        calls = [ToolExecution(
            tool_name=item["tool_name"], arguments=item.get("arguments", {}),
            result=item.get("result"), status=item.get("status", "success"),
            error_type=item.get("error_type"), latency_s=float(item.get("latency_s", 0.0)),
            cache_hit=bool(item.get("cache_hit", False)), duplicate=bool(item.get("duplicate", False)),
            idempotency_replay=bool(item.get("idempotency_replay", False)),
        ) for item in checkpoint.tool_calls]
        return await self.run(checkpoint.task, run_id=checkpoint.run_id,
                              _messages=checkpoint.messages, _prior_calls=calls,
                              _start_step=checkpoint.step)

    async def _execute_with_retry(self, name: str, arguments: dict[str, Any], *, idempotency_key: str) -> ToolExecution:
        execution = await self.tools.execute(name, arguments, idempotency_key=idempotency_key)
        attempts = 1
        while execution.status == "error" and self.config.retry.retryable(execution.error_type) \
                and attempts < self.config.retry.max_attempts:
            await asyncio.sleep(min(self.config.retry.max_delay_s,
                                    self.config.retry.base_delay_s * (2 ** (attempts - 1))))
            execution = await self.tools.execute(name, arguments, idempotency_key=idempotency_key)
            attempts += 1
        return execution

    def _persist(self, result: RunResult, task: str, messages: list[dict[str, Any]],
                 calls: list[ToolExecution], step: int) -> None:
        if self.config.checkpoint_dir:
            Checkpoint(result.run_id, task, result.status, step, messages,
                       [call.to_dict() for call in calls]).save(Path(self.config.checkpoint_dir))
        if self.config.trace_path:
            Trace(**result.trace).write_jsonl(Path(self.config.trace_path))
