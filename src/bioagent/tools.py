from __future__ import annotations

import asyncio
import hashlib
import inspect
import json
import time
from dataclasses import dataclass, field
from typing import Any, Callable

from pydantic import BaseModel, ValidationError


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
        }


@dataclass
class ToolExecutor:
    registry: ToolRegistry
    timeout_s: float = 30.0
    cache: dict[str, tuple[float, Any]] = field(default_factory=dict)

    @staticmethod
    def cache_key(name: str, arguments: dict[str, Any]) -> str:
        payload = json.dumps([name, arguments], sort_keys=True, default=str).encode()
        return hashlib.sha256(payload).hexdigest()

    async def execute(self, name: str, arguments: dict[str, Any]) -> ToolExecution:
        tool = self.registry.get(name)
        started = time.perf_counter()
        try:
            parsed = tool.args_model.model_validate(arguments)
        except ValidationError as exc:
            return ToolExecution(name, arguments, status="error", error_type="invalid_arguments",
                                  result={"error": "invalid_arguments", "details": exc.errors()},
                                  latency_s=time.perf_counter() - started)

        key = self.cache_key(name, parsed.model_dump())
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
            return ToolExecution(name, parsed.model_dump(), result=value,
                                 latency_s=time.perf_counter() - started)
        except asyncio.TimeoutError:
            return ToolExecution(name, parsed.model_dump(), status="error", error_type="timeout",
                                  result={"error": "tool_timeout", "tool": name},
                                  latency_s=time.perf_counter() - started)
        except ToolError as exc:
            return ToolExecution(name, parsed.model_dump(), status="error", error_type=exc.error_type,
                                  result={"error": exc.error_type, "message": str(exc)},
                                  latency_s=time.perf_counter() - started)
        except Exception as exc:  # tool exceptions never escape as raw model context
            return ToolExecution(name, parsed.model_dump(), status="error", error_type=type(exc).__name__,
                                  result={"error": "tool_execution_error", "message": str(exc)},
                                  latency_s=time.perf_counter() - started)
