from __future__ import annotations

import json
import re
from pathlib import Path


ANCESTRY_LABELS = {
    "EU": "European",
    "HS": "Hispanic/South Asian",
    "Mixed": "Mixed ancestry",
}


class PhenotypeGlossary:
    def __init__(self, entries: dict[str, dict[str, str]] | None = None) -> None:
        self._entries = entries or {}

    @classmethod
    def from_file(cls, path: Path) -> "PhenotypeGlossary":
        with path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
        return cls(data)

    def get_label(self, code: str) -> tuple[str, str]:
        entry = self._entries.get(code)
        if entry and entry.get("label"):
            return entry["label"], "curated"

        return self._infer_label(code), "inferred"

    def get_category(self, code: str) -> str:
        entry = self._entries.get(code)
        if entry and entry.get("category"):
            return entry["category"]
        return "other"

    def get_group(self, code: str) -> str | None:
        entry = self._entries.get(code)
        if entry:
            return entry.get("group")
        return None

    def get_aliases(self, code: str) -> list[str]:
        entry = self._entries.get(code)
        if entry:
            return entry.get("aliases", [])
        return []

    def resolve_code(self, text_or_alias: str) -> str | None:
        """Resolve a label, abbreviation, or alias to its canonical code."""
        query_norm = text_or_alias.strip().lower()
        if not query_norm:
            return None
        # Exact match on code
        for code in self._entries:
            if code.lower() == query_norm:
                return code
        # Match on label or alias
        for code, entry in self._entries.items():
            label = entry.get("label", "").lower()
            if label == query_norm:
                return code
            for alias in entry.get("aliases", []):
                if alias.lower() == query_norm:
                    return code
        return None

    def _infer_label(self, code: str) -> str:
        known_tokens = {
            "T2D": "Type 2 Diabetes",
            "BMI": "Body Mass Index",
            "AD": "Alzheimer's Disease",
            "AF": "Atrial Fibrillation",
            "OGTT": "OGTT",
            "CVD": "cardiovascular disease",
            "FFA": "free fatty acids",
        }

        if code in known_tokens:
            return known_tokens[code]

        parts = re.findall(r"[A-Z]+(?=[A-Z][a-z]|[0-9]|$)|[A-Z]?[a-z]+|[0-9]+", code)
        if not parts:
            return code

        normalized = " ".join(parts)
        for token, replacement in known_tokens.items():
            normalized = re.sub(rf"\b{token}\b", replacement, normalized)
        return normalized


def ancestry_label(code: str) -> str:
    return ANCESTRY_LABELS.get(code, code)
