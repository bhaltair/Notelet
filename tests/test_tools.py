import pytest

from tools import add_note, read_notes


def test_add_note_appends_timestamped_content(tmp_path):
    notes_path = tmp_path / "notes.md"

    result = add_note("Review the simple agent design", notes_path=notes_path)

    saved = notes_path.read_text(encoding="utf-8")
    assert result == "Note saved."
    assert "- " in saved
    assert "Review the simple agent design" in saved


def test_add_note_rejects_empty_content(tmp_path):
    notes_path = tmp_path / "notes.md"

    with pytest.raises(ValueError, match="Note content cannot be empty"):
        add_note("   ", notes_path=notes_path)

    assert not notes_path.exists()


def test_read_notes_handles_missing_file(tmp_path):
    notes_path = tmp_path / "notes.md"

    result = read_notes(notes_path=notes_path)

    assert result == "No notes yet."


def test_read_notes_returns_existing_notes(tmp_path):
    notes_path = tmp_path / "notes.md"
    notes_path.write_text("- 2026-04-17T09:00:00+08:00 Review agent design\n", encoding="utf-8")

    result = read_notes(notes_path=notes_path)

    assert "Review agent design" in result


def test_read_notes_trims_large_output(tmp_path):
    notes_path = tmp_path / "notes.md"
    notes_path.write_text("a" * 6000, encoding="utf-8")

    result = read_notes(notes_path=notes_path, max_chars=100)

    assert len(result) < 200
    assert result.endswith("\n[Notes trimmed to 100 characters.]")
