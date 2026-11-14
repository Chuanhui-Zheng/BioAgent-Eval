from __future__ import annotations

import json
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class IdempotencyRecord:
    key: str
    status: str
    result: Any = None


class SQLiteIdempotencyStore:
    """Durable result store for side-effecting tool calls.

    A key is claimed before a handler runs. A later attempt with the same key
    replays the stored result instead of invoking the handler again. A failed
    handler releases its claim so a retry can make progress.
    """

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.execute(
                "CREATE TABLE IF NOT EXISTS idempotency ("
                "key TEXT PRIMARY KEY, status TEXT NOT NULL, result_json TEXT, updated_at REAL NOT NULL)"
            )

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=10)
        connection.execute("PRAGMA journal_mode=WAL")
        return connection

    def claim(self, key: str) -> IdempotencyRecord | None:
        now = time.time()
        try:
            with self._connect() as connection:
                connection.execute(
                    "INSERT INTO idempotency(key, status, updated_at) VALUES (?, 'running', ?)",
                    (key, now),
                )
            return None
        except sqlite3.IntegrityError:
            with self._connect() as connection:
                row = connection.execute(
                    "SELECT key, status, result_json FROM idempotency WHERE key = ?", (key,)
                ).fetchone()
            if row is None:
                return None
            result = json.loads(row[2]) if row[2] is not None else None
            return IdempotencyRecord(row[0], row[1], result)

    def complete(self, key: str, result: Any) -> None:
        with self._connect() as connection:
            connection.execute(
                "UPDATE idempotency SET status = 'completed', result_json = ?, updated_at = ? WHERE key = ?",
                (json.dumps(result, ensure_ascii=False, default=str), time.time(), key),
            )

    def release(self, key: str) -> None:
        with self._connect() as connection:
            connection.execute("DELETE FROM idempotency WHERE key = ?", (key,))
