# Simple Notes Agent

A minimal Python CLI agent that uses the OpenAI-compatible Chat Completions API
to call two local tools:

- `add_note(content)`: append a timestamped note to `notes.md`
- `read_notes()`: read saved notes, with large output trimmed before returning to the model

The code is intentionally small so the model/tool loop is easy to inspect.

## Setup

Install dependencies with uv:

```powershell
uv sync
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

## Test

```powershell
uv run pytest
```

## Project Shape

- `agent.py`: interactive CLI loop and Chat Completions tool-call loop
- `tools.py`: local note tools, tool schemas, and the tool registry
- `notes.md`: local durable notes storage
- `tests/`: unit tests for tool behavior and the agent loop
