from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class Trace:
    run_id: str
    task: str
    model: str
    events: list[dict[str, Any]] = field(default_factory=list)
    usage: dict[str, Any] = field(default_factory=dict)
    final_status: str = "running"

    def event(self, name: str, **payload: Any) -> None:
        self.events.append({"event": name, **payload})

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def write_jsonl(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(self.to_dict(), ensure_ascii=False) + "\n")
