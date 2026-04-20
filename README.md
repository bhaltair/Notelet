# Simple Notes Agent

A minimal Python CLI agent that uses the OpenAI-compatible Chat Completions API
to call local memory tools:

- `add_note(content)`: save a timestamped note to SQLite memory
- `read_notes()`: read recent saved notes
- `search_notes(query)`: search saved notes by keyword
- `list_recent_notes(limit)`: list the newest notes

The code is intentionally small so the model/tool loop is easy to inspect.
It also includes a React/Vite runtime console for watching streaming answers,
tool calls, tool results, and local memory in the browser.

## Setup

Install dependencies with uv:

```powershell
uv sync
```

Install frontend dependencies with npm:

```powershell
cd frontend
npm.cmd install
cd ..
```

Set your API key:

```powershell
$env:OPENAI_API_KEY = "your-api-key"
```

Optionally choose a model:

```powershell
$env:OPENAI_MODEL = "gpt-5.4-mini"
```

You can also put these values in a local `.env` file:

```env
OPENAI_API_KEY=your-api-key
OPENAI_MODEL=gpt-5.4-mini
```

Or copy `.env.example` and fill in your own values.

### DeepSeek

DeepSeek's API is OpenAI-compatible, so the same Chat Completions loop works
after changing the base URL and model.

Set these values in PowerShell:

```powershell
$env:OPENAI_API_KEY = "your-deepseek-api-key"
$env:OPENAI_BASE_URL = "https://api.deepseek.com"
$env:OPENAI_MODEL = "deepseek-chat"
```

Or put them in `.env`:

```env
OPENAI_API_KEY=your-deepseek-api-key
OPENAI_BASE_URL=https://api.deepseek.com
OPENAI_MODEL=deepseek-chat
```

Use `deepseek-reasoner` instead of `deepseek-chat` if you want DeepSeek's
reasoning model.

## Run

### CLI

```powershell
uv run python agent.py
```

Try:

```text
Remember: review the simple agent design on Friday
```

Then:

```text
What notes have I saved?
```

Type `exit` or `quit` to stop.

When the model uses a tool, the CLI prints the local action before the final
answer:

```text
Tool call: add_note({"content": "review the simple agent design on Friday"})
Tool result: Note saved.
Agent> Saved it.
```

The agent also writes structured execution traces to `traces/YYYY-MM-DD.jsonl`
with user messages, model responses, tool calls, tool results, final answers,
and errors.

### Web Runtime Console

Run the Flask API backend:

```powershell
uv run python server.py
```

In a second terminal, run the React/Vite frontend:

```powershell
cd frontend
npm.cmd run dev
```

Then open:

```text
http://127.0.0.1:5173
```

The Vite dev server proxies `/api` and `/health` to Flask. The console streams
assistant answers with Server-Sent Events and shows runtime events alongside
recent SQLite memory. It is intended as a local, single-user runtime view rather
than a multi-user web product.

To serve a built frontend from Flask:

```powershell
cd frontend
npm.cmd run build
cd ..
uv run python server.py
```

Then open:

```text
http://127.0.0.1:5000
```

### HTTP API

Health:

```powershell
Invoke-RestMethod http://127.0.0.1:5000/health
```

Non-streaming chat:

```powershell
Invoke-RestMethod `
  -Method Post `
  -Uri http://127.0.0.1:5000/api/chat `
  -ContentType "application/json" `
  -Body '{"message":"What notes have I saved?"}'
```

Streaming chat:

```text
POST /api/chat/stream
Content-Type: application/json

{"message":"Remember: review the streaming console"}
```

The streaming endpoint returns SSE events such as `answer_delta`, `tool_call`,
`tool_result`, `tool_error`, and `final_answer`.

Recent notes:

```powershell
Invoke-RestMethod http://127.0.0.1:5000/api/notes
```

## Test

```powershell
uv run pytest
```

Build the frontend:

```powershell
cd frontend
npm.cmd run build
```

## Project Shape

- `agent.py`: interactive CLI loop, Chat Completions tool-call loop, and trace wiring
- `frontend/`: React, TypeScript, and Vite runtime console
- `memory.py`: SQLite-backed persistent note memory
- `server.py`: local Flask API, SSE streaming endpoint, and built frontend serving
- `tracing.py`: JSONL execution tracing
- `tools.py`: local note tools, tool schemas, and the tool registry
- `.agents/skills/git-release-flow`: repo-local release workflow skill
- `notes.db`: ignored local durable notes storage
- `traces/`: ignored local JSONL execution traces
- `tests/`: unit tests for tool behavior and the agent loop
