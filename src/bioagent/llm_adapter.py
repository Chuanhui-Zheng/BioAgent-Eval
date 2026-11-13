from __future__ import annotations

import json
from typing import Any

from bioagent.model import ModelDecision, Usage


class StructuredToolModelAdapter:
    """Adapt an existing OpenAI-compatible generator to Agent Runtime decisions.

    The provider owns transport, credentials and usage accounting. This adapter only
    defines the small JSON decision contract needed by the generic runtime.
    """

    def __init__(self, provider: Any, *, system_prompt: str | None = None) -> None:
        if not callable(getattr(provider, "complete", None)):
            raise TypeError("provider must expose complete(messages, ...)")
        self.provider = provider
        self.model = getattr(provider, "model", "unknown")
        self.system_prompt = system_prompt or (
            "You are an Agent controller. Return exactly one JSON object. "
            "Choose either {action:'tool', tool_name:string, tool_arguments:object} "
            "or {action:'final', content:string}. Use tools for evidence retrieval."
        )

    def decide(self, task: str, messages: list[dict[str, Any]], tools: list[dict[str, Any]]) -> ModelDecision:
        request = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": json.dumps({"task": task, "messages": messages, "tools": tools}, ensure_ascii=False)},
        ]
        content = self.provider.complete(request, json_mode=True)
        try:
            payload = json.loads(content)
        except json.JSONDecodeError as exc:
            raise ValueError("model adapter returned invalid JSON") from exc
        action = payload.get("action")
        if action not in {"tool", "final"}:
            raise ValueError("model adapter returned an unsupported action")
        usage = Usage()
        records = getattr(self.provider, "usage_records", [])
        if records:
            last = records[-1]
            usage = Usage(last.get("input_tokens"), last.get("output_tokens"),
                          estimated=last.get("input_tokens") is None or last.get("output_tokens") is None)
        return ModelDecision(
            action=action,
            content=str(payload.get("content", "")),
            tool_name=payload.get("tool_name"),
            tool_arguments=dict(payload.get("tool_arguments") or {}),
            usage=usage,
            model=self.model,
        )
