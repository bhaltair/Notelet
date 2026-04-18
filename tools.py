from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path


NOTES_PATH = Path(__file__).with_name("notes.md")
DEFAULT_MAX_CHARS = 4000

TOOLS = [
    {
        "type": "function",
        "name": "add_note",
        "description": "Append a timestamped note to the local notes file.",
        "parameters": {
            "type": "object",
            "properties": {
                "content": {
                    "type": "string",
                    "description": "The note text to save.",
                }
            },
            "required": ["content"],
            "additionalProperties": False,
        },
    },
    {
        "type": "function",
        "name": "read_notes",
        "description": "Read the local notes file.",
        "parameters": {
            "type": "object",
            "properties": {},
            "additionalProperties": False,
        },
    },
]


def add_note(content: str, notes_path: Path = NOTES_PATH) -> str:
    note = content.strip()
    if not note:
        raise ValueError("Note content cannot be empty.")

    notes_path.parent.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
    with notes_path.open("a", encoding="utf-8") as file:
        file.write(f"- {timestamp} {note}\n")

    return "Note saved."


def read_notes(notes_path: Path = NOTES_PATH, max_chars: int = DEFAULT_MAX_CHARS) -> str:
    if not notes_path.exists():
        return "No notes yet."

    content = notes_path.read_text(encoding="utf-8").strip()
    if not content:
        return "No notes yet."

    if len(content) > max_chars:
        return f"{content[:max_chars]}\n[Notes trimmed to {max_chars} characters.]"

    return content


def run_tool(name: str, arguments: dict[str, object]) -> str:
    if name == "add_note":
        content = arguments.get("content")
        if not isinstance(content, str):
            raise ValueError("add_note requires a string content argument.")
        return add_note(content)

    if name == "read_notes":
        return read_notes()

    raise ValueError(f"Unknown tool: {name}")
