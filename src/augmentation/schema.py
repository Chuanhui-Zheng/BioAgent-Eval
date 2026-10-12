from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal

EvidenceStatus = Literal["answer", "qualified", "refuse"]


@dataclass
class EvidencePassage:
    chunk_id: str
    collection: str
    rank: int
    score: float
    title: str
    content: str
    metadata: dict[str, Any]
    citation: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ContextPackage:
    question: str
    authorized_collections: list[str]
    effective_collections: list[str]
    retrieval_method: str
    passages: list[EvidencePassage]
    citation_registry: dict[str, dict[str, Any]]
    evidence_status: EvidenceStatus
    limitations: list[str]
    estimated_tokens: int
    max_context_tokens: int
    diagnostics: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
