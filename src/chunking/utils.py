from __future__ import annotations

import hashlib
import json
import re
import os
import subprocess
import tempfile
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator


CODING_SEQUENCE_RE = re.compile(
    r"^(?:(?:chr)?([^:]+):)?(\d+)-(\d+)$|^(HSCHR[^:]+):(\d+)-(\d+)$",
    re.IGNORECASE,
)


@contextmanager
def artifact_staging_directory(parent: Path, prefix: str):
    """Stage artifacts with parent access on Windows before atomic replacement.

    Python 3.13 creates private Windows temporary directories. Renamed files
    retain those ACLs, so enable normal inheritance before creating artifacts.
    """
    with tempfile.TemporaryDirectory(prefix=prefix, dir=parent) as directory:
        if os.name == "nt":
            subprocess.run(["icacls.exe", directory, "/inheritance:e"],
                           check=True, capture_output=True)
        yield Path(directory)


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def unix_to_iso8601(unix_ts: int | None) -> str:
    if unix_ts is None:
        return "unknown"
    return datetime.fromtimestamp(unix_ts, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_coding_sequence(value: str | None) -> tuple[str | None, int | None, int | None]:
    if not value:
        return None, None, None

    text = value.strip()
    if ":" in text and "-" in text:
        chromosome, coords = text.split(":", 1)
        if "-" in coords:
            start_text, end_text = coords.split("-", 1)
            if start_text.isdigit() and end_text.isdigit():
                return chromosome, int(start_text), int(end_text)

    match = CODING_SEQUENCE_RE.match(text)
    if not match:
        return None, None, None

    groups = match.groups()
    if groups[0] is not None:
        return groups[0], int(groups[1]), int(groups[2])
    return groups[3], int(groups[4]), int(groups[5])


def load_jsonl(path: Path) -> Iterator[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as handle:
        for line_no, line in enumerate(handle, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSONL at {path}:{line_no}") from exc


def write_jsonl(path: Path, records: Iterator[dict[str, Any]]) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with path.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
            count += 1
    return count


def infer_gene_data_quality(record: dict[str, Any]) -> str:
    if record.get("error"):
        return "error"
    if record.get("function_summary"):
        return "complete"
    return "partial"


def significance_tag(p_value: float) -> str:
    if p_value < 0.05:
        return " (statistically significant at p<0.05)"
    return " (not significant)"


def format_optional(value: Any, fallback: str = "N/A") -> str:
    if value is None or value == "":
        return fallback
    return str(value)


def relative_source_path(path: Path, project_root: Path) -> str:
    try:
        return path.relative_to(project_root).as_posix()
    except ValueError:
        return path.as_posix()
