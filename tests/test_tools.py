from pathlib import Path
from uuid import uuid4

import pytest

from tools import default_registry, add_note, read_notes


PROJECT_TMP = Path(__file__).resolve().parents[1] / "test_runs"


def temporary_notes_path():
    PROJECT_TMP.mkdir(exist_ok=True)
    return PROJECT_TMP / f"{uuid4().hex}.md"


def test_add_note_appends_timestamped_content():
    notes_path = temporary_notes_path()
    result = add_note("Review the simple agent design", notes_path=notes_path)

    saved = notes_path.read_text(encoding="utf-8")

    assert result == "Note saved."
    assert "- " in saved
    assert "Review the simple agent design" in saved


def test_add_note_rejects_empty_content():
    notes_path = temporary_notes_path()
    with pytest.raises(ValueError, match="Note content cannot be empty"):
        add_note("   ", notes_path=notes_path)

    assert not notes_path.exists()


def test_read_notes_handles_missing_file():
    notes_path = temporary_notes_path()
    result = read_notes(notes_path=notes_path)

    assert result == "No notes yet."


def test_read_notes_returns_existing_notes():
    notes_path = temporary_notes_path()
    notes_path.write_text(
        "- 2026-04-17T09:00:00+08:00 Review agent design\n",
        encoding="utf-8",
    )

    result = read_notes(notes_path=notes_path)

    assert "Review agent design" in result


def test_read_notes_trims_large_output():
    notes_path = temporary_notes_path()
    notes_path.write_text("a" * 6000, encoding="utf-8")

    result = read_notes(notes_path=notes_path, max_chars=100)

    assert len(result) < 200
    assert result.endswith("\n[Notes trimmed to 100 characters.]")


def test_default_registry_exposes_tool_schemas():
    registry = default_registry()

    schemas = registry.schemas()

    assert [schema["function"]["name"] for schema in schemas] == ["add_note", "read_notes"]
    assert schemas[0]["type"] == "function"


def test_default_registry_runs_registered_tool():
    notes_path = temporary_notes_path()
    registry = default_registry(notes_path=notes_path)

    result = registry.run("add_note", {"content": "Registry note"})

    assert result == "Note saved."
    assert "Registry note" in registry.run("read_notes", {})


def test_default_registry_rejects_unknown_tool():
    registry = default_registry()

    with pytest.raises(ValueError, match="Unknown tool"):
        registry.run("missing_tool", {})
