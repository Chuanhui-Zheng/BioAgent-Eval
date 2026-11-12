from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal, Protocol


@dataclass
class Usage:
    """Token accounting returned by a model adapter.

    ``estimated`` is true when the provider did not return usage metadata.
    """

    input_tokens: int | None = None
    output_tokens: int | None = None
    estimated: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def total_tokens(self) -> int | None:
        if self.input_tokens is None or self.output_tokens is None:
            return None
        return self.input_tokens + self.output_tokens

    def add(self, other: "Usage") -> None:
        if self.input_tokens is None or other.input_tokens is None:
            self.input_tokens = None
        else:
            self.input_tokens += other.input_tokens
        if self.output_tokens is None or other.output_tokens is None:
            self.output_tokens = None
        else:
            self.output_tokens += other.output_tokens
        self.estimated = self.estimated or other.estimated

    def to_dict(self) -> dict[str, Any]:
        return {
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "total_tokens": self.total_tokens,
            "estimated": self.estimated,
            "metadata": self.metadata,
        }


@dataclass
class ModelDecision:
    action: Literal["tool", "final"]
    content: str = ""
    tool_name: str | None = None
    tool_arguments: dict[str, Any] = field(default_factory=dict)
    usage: Usage = field(default_factory=Usage)
    model: str = "unknown"


class ModelAdapter(Protocol):
    model: str

    def decide(
        self,
        task: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
    ) -> ModelDecision: ...
