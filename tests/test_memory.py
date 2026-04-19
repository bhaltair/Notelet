from pathlib import Path
from uuid import uuid4

import pytest

from memory import NoteStore


PROJECT_TMP = Path(__file__).resolve().parents[1] / "test_runs"


def temporary_db_path():
    PROJECT_TMP.mkdir(exist_ok=True)
    return PROJECT_TMP / f"{uuid4().hex}.db"


def test_note_store_adds_and_lists_recent_notes():
    store = NoteStore(temporary_db_path())

    result = store.add_note("Review the simple agent design")
    notes = store.list_recent_notes(limit=5)

    assert result == "Note saved."
    assert len(notes) == 1
    assert notes[0]["content"] == "Review the simple agent design"
    assert notes[0]["created_at"]


def test_note_store_rejects_empty_notes():
    store = NoteStore(temporary_db_path())

    with pytest.raises(ValueError, match="Note content cannot be empty"):
        store.add_note("   ")


def test_note_store_searches_notes_by_keyword():
    store = NoteStore(temporary_db_path())
    store.add_note("Review the simple agent design")
    store.add_note("Buy milk")

    matches = store.search_notes("agent")

    assert [match["content"] for match in matches] == ["Review the simple agent design"]


def test_note_store_formats_empty_recent_notes():
    db_path = temporary_db_path()
    store = NoteStore(db_path)

    assert store.format_recent_notes() == "No notes yet."
    assert not db_path.exists()


def test_note_store_formats_search_misses():
    db_path = temporary_db_path()
    store = NoteStore(db_path)

    assert store.format_search_results("missing") == "No matching notes."
    assert not db_path.exists()
