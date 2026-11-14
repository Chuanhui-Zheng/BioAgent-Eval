from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ContextManager:
    """Bound model context while preserving the task and latest evidence."""

    max_tokens: int = 6000
    chars_per_token: int = 4

    def estimate_tokens(self, messages: list[dict[str, Any]]) -> int:
        text = json.dumps(messages, ensure_ascii=False, default=str)
        return max(1, (len(text) + self.chars_per_token - 1) // self.chars_per_token)

    def prepare(self, messages: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        original = self.estimate_tokens(messages)
        if original <= self.max_tokens:
            return messages, {"estimated_tokens": original, "compressed": False, "estimated": True}

        # Keep the user task and the newest tool result intact. Older tool output is
        # represented by a bounded summary, never silently discarded as evidence.
        first = messages[:1]
        latest = messages[-1:] if len(messages) > 1 else []
        omitted = messages[1:-1] if len(messages) > 2 else []
        ledger = self._evidence_ledger(messages)
        summary = " ".join(str(item.get("content", ""))[:400] for item in omitted)
        if ledger:
            summary = f"Evidence ledger: {json.dumps(ledger, ensure_ascii=False)} {summary}"
        compressed = [*first, {"role": "context_summary", "content": summary[: self.max_tokens * self.chars_per_token]}, *latest]
        while self.estimate_tokens(compressed) > self.max_tokens:
            if len(summary) > 200:
                summary = summary[: max(200, len(summary) // 2)]
                compressed[1]["content"] = summary
                continue
            if latest and isinstance(latest[0].get("content"), str) and len(latest[0]["content"]) > 200:
                latest[0]["content"] = latest[0]["content"][: max(200, len(latest[0]["content"]) // 2)]
                compressed[-1] = latest[0]
                continue
            break
        return compressed, {
            "estimated_tokens_before": original,
            "estimated_tokens": self.estimate_tokens(compressed),
            "compressed": True,
            "estimated": True,
            "preserved_evidence_ids": [item["id"] for item in ledger],
        }

    @staticmethod
    def _evidence_ledger(messages: list[dict[str, Any]]) -> list[dict[str, str]]:
        ledger: list[dict[str, str]] = []
        seen: set[str] = set()
        for message in messages:
            content = message.get("content")
            if not isinstance(content, dict):
                continue
            passages = content.get("passages", [])
            if not isinstance(passages, list):
                continue
            for passage in passages:
                if not isinstance(passage, dict):
                    continue
                identifier = passage.get("chunk_id") or passage.get("source_id") or passage.get("id")
                if not identifier or str(identifier) in seen:
                    continue
                seen.add(str(identifier))
                ledger.append({"id": str(identifier), "title": str(passage.get("title", ""))[:160]})
        return ledger[:64]
