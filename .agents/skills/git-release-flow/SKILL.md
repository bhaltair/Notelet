---
name: git-release-flow
description: Safe Git release workflow for coding agents. Use when the user asks to prepare a release, commit release changes, create an annotated version tag, push a branch, push tags, or perform the Notelet-style release sequence after tests pass.
---

# Git Release Flow

## Workflow

Use this sequence for release commits and tags:

1. Inspect state with `git status --short --branch`, recent log, and existing tag check.
2. Confirm the intended release version from project files such as `pyproject.toml`, changelog, package metadata, or the user's request.
3. Run the project's required validation commands before committing. Prefer repo instructions such as `AGENTS.md`, `README.md`, or CI config.
4. Review the diff with `git diff --stat` and targeted `git diff` for changed release files.
5. Stage only intended files. Do not include runtime data, secrets, caches, generated traces, or unrelated user changes.
6. Commit with a concise release-focused message, for example `feat: add streaming runtime console` or `chore: release vX.Y.Z`.
7. Create an annotated tag with `git tag -a vX.Y.Z -m "vX.Y.Z: short release summary"`.
8. Push the branch first, then push the tag: `git push origin <branch>` and `git push origin vX.Y.Z`.
9. Report the commit hash, tag name, validation results, and push status.

## Safety Rules

- Stop and ask if unexpected unrelated changes appear in files that should not be part of the release.
- Never use destructive commands such as `git reset --hard` or force push unless the user explicitly asks and confirms the risk.
- If a tag already exists, inspect it before doing anything. Do not delete or move tags without explicit approval.
- If push fails due to authentication, report that local commit/tag succeeded and retry only after the user re-authenticates.
- Prefer annotated tags for releases.

## Validation Pattern

For Python `uv` projects, a typical release validation is:

```powershell
uv run pytest
uv run python -m py_compile <project files and tests>
```

Use the exact commands from the repository instructions when available.

## Output Pattern

Keep the final release summary short and concrete:

- Commit: `<hash> <message>`
- Tag: `<tag>` pushed or local-only
- Validation: command names and pass/fail result
- Remote: branch/tag push result
