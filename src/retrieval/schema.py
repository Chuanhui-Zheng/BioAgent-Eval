from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class ChunkRecord:
    chunk_id: str
    collection: str
    entity_type: str
    title: str
    content: str
    metadata: dict[str, Any]
    citation: dict[str, Any]

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> ChunkRecord:
        required = ["chunk_id", "collection", "entity_type", "title", "content", "metadata", "citation"]
        missing = [name for name in required if name not in payload or payload[name] in (None, "")]
        if missing:
            raise ValueError(f"Chunk missing required fields: {missing}")
        return cls(
            chunk_id=str(payload["chunk_id"]),
            collection=str(payload["collection"]),
            entity_type=str(payload["entity_type"]),
            title=str(payload["title"]),
            content=str(payload["content"]),
            metadata=dict(payload["metadata"]),
            citation=dict(payload["citation"]),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def indexed_text(self, text_fields: list[str]) -> str:
        parts: list[str] = []
        for field_name in text_fields:
            value = getattr(self, field_name, None)
            if value:
                parts.append(str(value))
        return "\n".join(parts)


@dataclass
class SearchResult:
    chunk_id: str
    collection: str
    rank: int
    score: float
    method: str
    component_scores: dict[str, Any] = field(default_factory=dict)
    chunk: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class RouteDecision:
    collections: list[str]
    matched_rules: list[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
