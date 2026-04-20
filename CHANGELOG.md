# Changelog

All notable changes to Notelet are documented here.

## v0.0.5 - 2026-04-20

### Added

- Added streaming agent turns that emit `answer_delta`, tool, model response,
  and final answer events.
- Added a thin Flask API with JSON chat, SSE streaming chat, health, and notes
  endpoints.
- Added a lightweight browser runtime console for streaming answers, runtime
  events, and recent memory.
- Added deterministic tests for streaming agent behavior and Flask endpoints.

## v0.0.4 - 2026-04-19

### Added

- Added deterministic agent-loop tests for malformed tool arguments, unknown
  tools, and maximum tool-round failures.
- Added structured `tool_error` trace events and `is_error` markers on tool
  results when local tool execution fails.

## v0.0.3 - 2026-04-19

### Added

- Added JSONL execution traces for user messages, model responses, tool calls,
  tool results, final answers, and errors.
- Added SQLite-backed persistent note memory.
- Added `search_notes` and `list_recent_notes` tools.

### Changed

- Moved runtime note storage from `notes.md` to ignored `notes.db`.

## v0.0.2 - 2026-04-19

### Added

- Added a lightweight `ToolRegistry` so tools can be registered with a schema and handler instead of being dispatched through hard-coded conditionals.
- Added CLI tool tracing that prints tool calls and tool results before the final agent answer.
- Added `.env.example` for OpenAI and OpenAI-compatible provider setup.
- Added tests for tool registry schema exposure, registered tool execution, unknown tool errors, and tool event emission.

### Changed

- Updated the project version to `0.0.2`.
- Updated README setup, run, and project structure documentation.
- Scoped pytest collection to `tests/` to avoid local temporary directories on Windows.

## v0.0.1 - 2026-04-17

### Added

- Added the first Python CLI agent loop for local note-taking.
- Added local tools for appending timestamped notes and reading saved notes.
- Added persistent `notes.md` storage.
- Added uv-managed dependencies and automated tests for the agent loop and note tools.
