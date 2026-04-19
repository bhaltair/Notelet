from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from memory import MEMORY_DB_PATH, NoteStore


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


def add_note(content: str, db_path: Path = MEMORY_DB_PATH) -> str:
    return NoteStore(db_path).add_note(content)


def read_notes(db_path: Path = MEMORY_DB_PATH, max_chars: int = DEFAULT_MAX_CHARS) -> str:
    return NoteStore(db_path).format_recent_notes(max_chars=max_chars)


def search_notes(
    query: str,
    db_path: Path = MEMORY_DB_PATH,
    limit: int = 10,
    max_chars: int = DEFAULT_MAX_CHARS,
) -> str:
    return NoteStore(db_path).format_search_results(
        query,
        limit=limit,
        max_chars=max_chars,
    )


def list_recent_notes(
    limit: int = 10,
    db_path: Path = MEMORY_DB_PATH,
    max_chars: int = DEFAULT_MAX_CHARS,
) -> str:
    return NoteStore(db_path).format_recent_notes(limit=limit, max_chars=max_chars)


def default_registry(db_path: Path = MEMORY_DB_PATH) -> ToolRegistry:
    registry = ToolRegistry()
    registry.register(
        Tool(
            name="add_note",
            description="Append a timestamped note to persistent local memory.",
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
            handler=lambda arguments: _run_add_note(arguments, db_path),
        )
    )
    registry.register(
        Tool(
            name="read_notes",
            description="Read recent notes from persistent local memory.",
            parameters={
                "type": "object",
                "properties": {},
                "additionalProperties": False,
            },
            handler=lambda arguments: read_notes(db_path=db_path),
        )
    )
    registry.register(
        Tool(
            name="search_notes",
            description="Search saved notes by keyword.",
            parameters={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Keyword or phrase to search for.",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of matching notes to return.",
                    },
                },
                "required": ["query"],
                "additionalProperties": False,
            },
            handler=lambda arguments: _run_search_notes(arguments, db_path),
        )
    )
    registry.register(
        Tool(
            name="list_recent_notes",
            description="List the most recent saved notes.",
            parameters={
                "type": "object",
                "properties": {
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of recent notes to return.",
                    }
                },
                "additionalProperties": False,
            },
            handler=lambda arguments: _run_list_recent_notes(arguments, db_path),
        )
    )
    return registry


def _run_add_note(arguments: dict[str, object], db_path: Path) -> str:
    content = arguments.get("content")
    if not isinstance(content, str):
        raise ValueError("add_note requires a string content argument.")
    return add_note(content, db_path=db_path)


def _run_search_notes(arguments: dict[str, object], db_path: Path) -> str:
    query = arguments.get("query")
    if not isinstance(query, str):
        raise ValueError("search_notes requires a string query argument.")
    limit = _optional_int(arguments.get("limit"), default=10)
    return search_notes(query, db_path=db_path, limit=limit)


def _run_list_recent_notes(arguments: dict[str, object], db_path: Path) -> str:
    limit = _optional_int(arguments.get("limit"), default=10)
    return list_recent_notes(limit=limit, db_path=db_path)


def _optional_int(value: object, default: int) -> int:
    if value is None:
        return default
    if not isinstance(value, int):
        raise ValueError("limit must be an integer.")
    return value


DEFAULT_REGISTRY = default_registry()
TOOLS = DEFAULT_REGISTRY.schemas()


def run_tool(name: str, arguments: dict[str, object]) -> str:
    return DEFAULT_REGISTRY.run(name, arguments)
