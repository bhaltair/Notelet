# AGENTS.md

Guidance for coding agents working on Notelet.

## Project Intent

Notelet is a small, inspectable CLI agent runtime. Keep it educational, explicit,
and easy to explain on a resume. Prefer focused agent-runtime capabilities over
product sprawl.

The project should demonstrate:

- A clear model/tool execution loop.
- Safe local tools with narrow side effects.
- Persistent memory that lives outside the model context.
- Deterministic tests for agent behavior.
- Observable execution, so tool calls and failures are debuggable.

## Architecture Rules

- Keep `agent.py` responsible for the CLI loop and model/tool orchestration.
- Keep `tools.py` responsible for local tools, tool schemas, and `ToolRegistry`.
- Do not add a web UI, database, scheduler, or multi-agent system unless the
  change is explicitly part of the current task.
- Add new tools through `ToolRegistry`; do not reintroduce hard-coded
  `if name == ...` dispatch in the agent loop.
- Keep provider compatibility through OpenAI-compatible Chat Completions unless
  a task explicitly asks to change the provider interface.
- Keep side effects narrow. Tools may only touch the files or stores they are
  designed to own.

## Development Workflow

- Use `uv` for dependency and command execution.
- Run tests with:

```powershell
uv run pytest
```

- Run syntax verification with:

```powershell
uv run python -m py_compile agent.py tools.py tests/test_agent.py tests/test_tools.py
```

- Do not commit `.env`, local temporary directories, Python caches, or generated
  notes from personal runs.
- Treat `notes.md` as runtime data. Do not include user note changes in feature
  commits unless the task explicitly asks for fixture data.

## Testing Expectations

- Add or update tests for every behavior change.
- Use fake model clients for agent-loop tests; do not require live API calls in
  automated tests.
- Cover both successful tool execution and failure boundaries, especially:
  unknown tools, malformed arguments, empty note content, and max tool rounds.
- Keep tests deterministic and local.

## Release Notes

- Update `CHANGELOG.md` for user-visible features, behavior changes, or release
  preparation.
- Keep `pyproject.toml` and `uv.lock` versions aligned when changing the project
  version.
- Use annotated tags for release points, for example:

```powershell
git tag -a v0.0.2 -m "v0.0.2: add tool registry and CLI tracing"
```

## Style

- Prefer simple Python over clever abstractions.
- Keep comments rare and useful.
- Keep docs concise and runnable.
- Optimize for a reader who wants to understand how a minimal agent runtime
  works in one sitting.
