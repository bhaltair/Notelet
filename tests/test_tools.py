from pathlib import Path
from uuid import uuid4

import pytest

from tools import default_registry, add_note, list_recent_notes, read_notes, search_notes


PROJECT_TMP = Path(__file__).resolve().parents[1] / "test_runs"


def temporary_db_path():
    PROJECT_TMP.mkdir(exist_ok=True)
    return PROJECT_TMP / f"{uuid4().hex}.db"


def test_add_note_appends_timestamped_content():
    db_path = temporary_db_path()
    result = add_note("Review the simple agent design", db_path=db_path)

    saved = read_notes(db_path=db_path)

    assert result == "Note saved."
    assert "Review the simple agent design" in saved


def test_add_note_rejects_empty_content():
    db_path = temporary_db_path()
    with pytest.raises(ValueError, match="Note content cannot be empty"):
        add_note("   ", db_path=db_path)

    assert not db_path.exists()


def test_read_notes_handles_missing_file():
    db_path = temporary_db_path()
    result = read_notes(db_path=db_path)

    assert result == "No notes yet."


def test_read_notes_returns_existing_notes():
    db_path = temporary_db_path()
    add_note("Review agent design", db_path=db_path)

    result = read_notes(db_path=db_path)

    assert "Review agent design" in result


def test_read_notes_trims_large_output():
    db_path = temporary_db_path()
    add_note("a" * 6000, db_path=db_path)

    result = read_notes(db_path=db_path, max_chars=100)

    assert len(result) < 200
    assert result.endswith("\n[Notes trimmed to 100 characters.]")


def test_default_registry_exposes_tool_schemas():
    registry = default_registry()

    schemas = registry.schemas()

    assert [schema["function"]["name"] for schema in schemas] == [
        "add_note",
        "read_notes",
        "search_notes",
        "list_recent_notes",
    ]
    assert schemas[0]["type"] == "function"


def test_default_registry_runs_registered_tool():
    db_path = temporary_db_path()
    registry = default_registry(db_path=db_path)

    result = registry.run("add_note", {"content": "Registry note"})

    assert result == "Note saved."
    assert "Registry note" in registry.run("read_notes", {})


def test_search_notes_returns_matching_notes():
    db_path = temporary_db_path()
    add_note("Review agent design", db_path=db_path)
    add_note("Buy milk", db_path=db_path)

    result = search_notes("agent", db_path=db_path)

    assert "Review agent design" in result
    assert "Buy milk" not in result


def test_list_recent_notes_respects_limit():
    db_path = temporary_db_path()
    add_note("First", db_path=db_path)
    add_note("Second", db_path=db_path)

    result = list_recent_notes(limit=1, db_path=db_path)

    assert "Second" in result
    assert "First" not in result


def test_default_registry_rejects_unknown_tool():
    registry = default_registry()

    with pytest.raises(ValueError, match="Unknown tool"):
        registry.run("missing_tool", {})
