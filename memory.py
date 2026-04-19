from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


MEMORY_DB_PATH = Path(__file__).with_name("notes.db")


class NoteStore:
    def __init__(self, db_path: Path = MEMORY_DB_PATH) -> None:
        self.db_path = db_path

    def add_note(self, content: str) -> str:
        note = content.strip()
        if not note:
            raise ValueError("Note content cannot be empty.")

        created_at = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
        with self._connect() as connection:
            connection.execute(
                "INSERT INTO notes (content, created_at) VALUES (?, ?)",
                (note, created_at),
            )

        return "Note saved."

    def list_recent_notes(self, limit: int = 10) -> list[dict[str, Any]]:
        if not self.db_path.exists():
            return []

        safe_limit = max(1, min(limit, 50))
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT id, content, created_at
                FROM notes
                ORDER BY id DESC
                LIMIT ?
                """,
                (safe_limit,),
            ).fetchall()

        return [_row_to_note(row) for row in rows]

    def search_notes(self, query: str, limit: int = 10) -> list[dict[str, Any]]:
        term = query.strip()
        if not term:
            return []
        if not self.db_path.exists():
            return []

        safe_limit = max(1, min(limit, 50))
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT id, content, created_at
                FROM notes
                WHERE content LIKE ?
                ORDER BY id DESC
                LIMIT ?
                """,
                (f"%{term}%", safe_limit),
            ).fetchall()

        return [_row_to_note(row) for row in rows]

    def format_recent_notes(self, limit: int = 10, max_chars: int = 4000) -> str:
        notes = self.list_recent_notes(limit=limit)
        if not notes:
            return "No notes yet."
        return _trim(_format_notes(notes), max_chars)

    def format_search_results(
        self,
        query: str,
        limit: int = 10,
        max_chars: int = 4000,
    ) -> str:
        notes = self.search_notes(query, limit=limit)
        if not notes:
            return "No matching notes."
        return _trim(_format_notes(notes), max_chars)

    def _connect(self) -> sqlite3.Connection:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS notes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                content TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        return connection


def _row_to_note(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "content": row["content"],
        "created_at": row["created_at"],
    }


def _format_notes(notes: list[dict[str, Any]]) -> str:
    return "\n".join(f"- {note['created_at']} {note['content']}" for note in notes)


def _trim(content: str, max_chars: int) -> str:
    if len(content) <= max_chars:
        return content
    return f"{content[:max_chars]}\n[Notes trimmed to {max_chars} characters.]"
