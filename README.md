# Simple Notes Agent

A minimal Python CLI agent that uses the OpenAI Responses API to call two local tools:

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

## Test

```powershell
uv run pytest
```

## Project Shape

- `agent.py`: interactive CLI loop and Responses API tool-call loop
- `tools.py`: local note tools, tool schemas, and tool dispatcher
- `notes.md`: local durable notes storage
- `tests/`: unit tests for tool behavior and the agent loop
