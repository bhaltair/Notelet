from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable


NOTES_PATH = Path(__file__).with_name("notes.md")
DEFAULT_MAX_CHARS = 4000

ToolHandler = Callable[[dict[str, object]], str]


@dataclass(frozen=True)
class Tool:
    name: str
    description: str
    parameters: dict[str, object]
    handler: ToolHandler

    def schema(self) -> dict[str, object]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        if tool.name in self._tools:
            raise ValueError(f"Tool already registered: {tool.name}")
        self._tools[tool.name] = tool

    def schemas(self) -> list[dict[str, object]]:
        return [tool.schema() for tool in self._tools.values()]

    def run(self, name: str, arguments: dict[str, object]) -> str:
        tool = self._tools.get(name)
        if tool is None:
            raise ValueError(f"Unknown tool: {name}")
        return tool.handler(arguments)


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


def default_registry(notes_path: Path = NOTES_PATH) -> ToolRegistry:
    registry = ToolRegistry()
    registry.register(
        Tool(
            name="add_note",
            description="Append a timestamped note to the local notes file.",
            parameters={
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
            handler=lambda arguments: _run_add_note(arguments, notes_path),
        )
    )
    registry.register(
        Tool(
            name="read_notes",
            description="Read the local notes file.",
            parameters={
                "type": "object",
                "properties": {},
                "additionalProperties": False,
            },
            handler=lambda arguments: read_notes(notes_path=notes_path),
        )
    )
    return registry


def _run_add_note(arguments: dict[str, object], notes_path: Path) -> str:
    content = arguments.get("content")
    if not isinstance(content, str):
        raise ValueError("add_note requires a string content argument.")
    return add_note(content, notes_path=notes_path)


DEFAULT_REGISTRY = default_registry()
TOOLS = DEFAULT_REGISTRY.schemas()


def run_tool(name: str, arguments: dict[str, object]) -> str:
    return DEFAULT_REGISTRY.run(name, arguments)
