from __future__ import annotations

import asyncio
import hashlib
import inspect
import json
import time
from dataclasses import dataclass, field
from typing import Any, Callable

from pydantic import BaseModel, ValidationError

from bioagent.idempotency import SQLiteIdempotencyStore


class ToolError(RuntimeError):
    """A classified tool failure safe to return to the model."""

    def __init__(self, error_type: str, message: str, *, retryable: bool = False):
        super().__init__(message)
        self.error_type = error_type
        self.retryable = retryable


@dataclass
class Tool:
    name: str
    description: str
    args_model: type[BaseModel]
    handler: Callable[..., Any]
    permission: str = "default"
    cache_ttl_s: float | None = None
    side_effect: bool = False
    requires_idempotency_key: bool = False

    def schema(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self.args_model.model_json_schema(),
        }


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        if not tool.name or tool.name in self._tools:
            raise ValueError(f"tool name already registered: {tool.name!r}")
        self._tools[tool.name] = tool

    def get(self, name: str) -> Tool:
        try:
            return self._tools[name]
        except KeyError as exc:
            raise ToolError("unknown_tool", f"Unknown tool: {name}") from exc

    def schemas(self) -> list[dict[str, Any]]:
        return [tool.schema() for tool in self._tools.values()]

    def names(self) -> list[str]:
        return list(self._tools)


@dataclass
class ToolExecution:
    tool_name: str
    arguments: dict[str, Any]
    result: Any = None
    status: str = "success"
    error_type: str | None = None
    latency_s: float = 0.0
    cache_hit: bool = False
    duplicate: bool = False
    idempotency_replay: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "tool_name": self.tool_name,
            "arguments": self.arguments,
            "result": self.result,
            "status": self.status,
            "error_type": self.error_type,
            "latency_s": self.latency_s,
            "cache_hit": self.cache_hit,
            "duplicate": self.duplicate,
            "idempotency_replay": self.idempotency_replay,
        }


@dataclass
class ToolExecutor:
    registry: ToolRegistry
    timeout_s: float = 30.0
    allowed_permissions: frozenset[str] = frozenset({"default"})
    cache: dict[str, tuple[float, Any]] = field(default_factory=dict)
    idempotency_store: SQLiteIdempotencyStore | None = None

    @staticmethod
    def cache_key(name: str, arguments: dict[str, Any]) -> str:
        payload = json.dumps([name, arguments], sort_keys=True, default=str).encode()
        return hashlib.sha256(payload).hexdigest()

    async def execute(self, name: str, arguments: dict[str, Any], *, idempotency_key: str | None = None) -> ToolExecution:
        tool = self.registry.get(name)
        started = time.perf_counter()
        if tool.permission not in self.allowed_permissions:
            return ToolExecution(name, arguments, status="error", error_type="permission_denied",
                                  result={"error": "permission_denied", "permission": tool.permission},
                                  latency_s=time.perf_counter() - started)
        if (tool.requires_idempotency_key or tool.side_effect) and not idempotency_key:
            return ToolExecution(name, arguments, status="error", error_type="missing_idempotency_key",
                                  result={"error": "missing_idempotency_key", "tool": name},
                                  latency_s=time.perf_counter() - started)
        if tool.side_effect and self.idempotency_store is None:
            return ToolExecution(name, arguments, status="error", error_type="idempotency_store_unconfigured",
                                  result={"error": "idempotency_store_unconfigured", "tool": name},
                                  latency_s=time.perf_counter() - started)
        try:
            parsed = tool.args_model.model_validate(arguments)
        except ValidationError as exc:
            return ToolExecution(name, arguments, status="error", error_type="invalid_arguments",
                                  result={"error": "invalid_arguments", "details": exc.errors()},
                                  latency_s=time.perf_counter() - started)

        key = self.cache_key(name, parsed.model_dump())
        if tool.side_effect and self.idempotency_store is not None and idempotency_key:
            existing = self.idempotency_store.claim(idempotency_key)
            if existing is not None:
                if existing.status == "completed":
                    return ToolExecution(name, parsed.model_dump(), result=existing.result,
                                         cache_hit=True, idempotency_replay=True,
                                         latency_s=time.perf_counter() - started)
                return ToolExecution(name, parsed.model_dump(), status="error",
                                     error_type="idempotency_in_progress",
                                     result={"error": "idempotency_in_progress", "key": idempotency_key},
                                     latency_s=time.perf_counter() - started)
        if tool.cache_ttl_s is not None and key in self.cache:
            expires, result = self.cache[key]
            if expires > time.monotonic():
                return ToolExecution(name, parsed.model_dump(), result=result, cache_hit=True,
                                     latency_s=time.perf_counter() - started)
            self.cache.pop(key, None)

        try:
            if inspect.iscoroutinefunction(tool.handler):
                value = await asyncio.wait_for(tool.handler(**parsed.model_dump()), timeout=self.timeout_s)
            else:
                value = await asyncio.wait_for(
                    asyncio.to_thread(tool.handler, **parsed.model_dump()), timeout=self.timeout_s
                )
            if tool.cache_ttl_s is not None:
                self.cache[key] = (time.monotonic() + tool.cache_ttl_s, value)
            if tool.side_effect and self.idempotency_store is not None and idempotency_key:
                self.idempotency_store.complete(idempotency_key, value)
            return ToolExecution(name, parsed.model_dump(), result=value,
                                 latency_s=time.perf_counter() - started)
        except asyncio.TimeoutError:
            if tool.side_effect and self.idempotency_store is not None and idempotency_key:
                self.idempotency_store.release(idempotency_key)
            return ToolExecution(name, parsed.model_dump(), status="error", error_type="timeout",
                                  result={"error": "tool_timeout", "tool": name},
                                  latency_s=time.perf_counter() - started)
        except ToolError as exc:
            if tool.side_effect and self.idempotency_store is not None and idempotency_key:
                self.idempotency_store.release(idempotency_key)
            return ToolExecution(name, parsed.model_dump(), status="error", error_type=exc.error_type,
                                  result={"error": exc.error_type, "message": str(exc)},
                                  latency_s=time.perf_counter() - started)
        except Exception as exc:  # tool exceptions never escape as raw model context
            if tool.side_effect and self.idempotency_store is not None and idempotency_key:
                self.idempotency_store.release(idempotency_key)
            return ToolExecution(name, parsed.model_dump(), status="error", error_type=type(exc).__name__,
                                  result={"error": "tool_execution_error", "message": str(exc)},
                                  latency_s=time.perf_counter() - started)
