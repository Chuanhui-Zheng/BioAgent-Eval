from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal

AnswerStatus = Literal["answer", "qualified", "refuse", "error"]


@dataclass
class Claim:
    text: str
    citations: list[str]


@dataclass
class GeneratedAnswer:
    status: AnswerStatus
    answer: str
    claims: list[Claim]
    citations: list[dict[str, Any]]
    limitations: list[str]
    provider: str = "offline_evidence"
    prompt_policy_version: str = "1.0.0"
    diagnostics: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
