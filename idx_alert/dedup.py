"""Deduplikasi pengumuman lewat SQLite lokal (PRD bagian 6)."""
from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path


class Deduplicator:
    def __init__(self, db_path: Path):
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._db_path = db_path
        self._init_schema()

    @contextmanager
    def _connect(self):
        conn = sqlite3.connect(self._db_path)
        try:
            yield conn
        finally:
            conn.close()

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS sent_announcements (
                    id TEXT PRIMARY KEY,
                    emiten TEXT NOT NULL,
                    subject TEXT NOT NULL,
                    sent_at TEXT NOT NULL DEFAULT (datetime('now'))
                )
                """
            )
            conn.commit()

    def has_seen(self, announcement_id: str) -> bool:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT 1 FROM sent_announcements WHERE id = ?", (announcement_id,)
            ).fetchone()
            return row is not None

    def mark_seen(self, announcement_id: str, emiten: str, subject: str) -> None:
        with self._connect() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO sent_announcements (id, emiten, subject) VALUES (?, ?, ?)",
                (announcement_id, emiten, subject),
            )
            conn.commit()
