# Agent hooks

Claude Code hooks: scripts Claude Code runs before or after a tool call. A hook gets the call as JSON on stdin; exit code 2 blocks the call (before) or shows the message to Claude (after), with stderr as the reason. All three use only Python's standard library.

| Hook | Runs | Does | Registered in |
| --- | --- | --- | --- |
| [`guard_files.py`](guard_files.py) | Before every `Edit`, `Write`, `Bash` and `PowerShell` call | **Blocks** changes to `.env` files (not `.env.example`), SQLite database files and committed migrations; also any shell command that mentions a `.env` file | [`.claude/settings.json`](../.claude/settings.json) |
| [`contract_check.py`](contract_check.py) | After edits to `openapi.yaml`, `backend/leaderboard/urls.py`, `views.py` or `serializers.py` | Runs the contract tests; if they fail, tells Claude that `openapi.yaml` and the backend disagree | [`.claude/settings.json`](../.claude/settings.json) |
| [`read_only_commands.py`](read_only_commands.py) | Before the reviewer subagent's `Bash` calls | **Blocks** anything but reading commands and tests | [the subagent's front matter](../.claude/agents/leaderboard-rules-reviewer.md) |

## Requirements

- `python` on the `PATH`. If it's missing, Claude Code reports a hook error and lets the call through.
- For `contract_check.py`: the backend's environment in `.venv/` at the repository root, or `STEPBOARD_BACKEND_PYTHON` set to that Python.

## Example

Asked to append a line to `.env`, or to `sed` a committed migration "anyway", Claude Code got:

```text
Blocked by agent-hooks/guard_files.py: backend/leaderboard/migrations/0001_initial.py is a migration that's already committed, and other databases may have applied it (AGENTS.md: never edit a pushed migration). Change the model, then run `python manage.py makemigrations` in backend/ to add a new migration instead.
```

The full demo is in [docs/agent-extension-pack.md](../docs/agent-extension-pack.md#hooks-guard_filespy-and-contract_checkpy).

## Tests

[`tests/`](tests/) runs each hook the way Claude Code does, by sending tool calls as JSON. There are 74 tests, run in CI's backend job:

```sh
cd backend
python -m pytest ../agent-hooks/tests -p no:django
```

The guard checks a shell command's text, not what it does, so it isn't a sandbox. [docs/permissions.md](../docs/permissions.md#limits) has the limits.
