# Agent Extension Pack

Everything that helps an AI coding agent, Claude Code in particular, work on this project safely: what it should know, the tools it can use, a repeatable workflow, a specialist reviewer, and guardrails. See [plan.md](plan.md#agent-extension-pack) for why, and [permissions.md](permissions.md) for what each piece may read, run and change.

| Piece | What it is | Files | Status |
| --- | --- | --- | --- |
| Project instructions | Layout, commands and rules for any AI agent | [AGENTS.md](../AGENTS.md) | Done |
| MCP server | `get_leaderboard`, `list_members` and `log_steps`, calling the API in `openapi.yaml` | [mcp-server/](../mcp-server/), registered in [`.mcp.json`](../.mcp.json) | Done |
| Reusable workflow | The `add-api-endpoint` skill: add or change an endpoint, contract first | [`.claude/skills/add-api-endpoint/SKILL.md`](../.claude/skills/add-api-endpoint/SKILL.md); notes in [agent-capabilities/](../agent-capabilities/) | Done |
| Specialist agent | The `leaderboard-rules-reviewer` subagent: read-only review against the product rules | [`.claude/agents/leaderboard-rules-reviewer.md`](../.claude/agents/leaderboard-rules-reviewer.md), its hook [`read_only_commands.py`](../agent-hooks/read_only_commands.py); notes in [custom-agent/](../custom-agent/) | Done |
| Hooks and guardrails | `guard_files.py` blocks changes to `.env` files, databases and committed migrations; `contract_check.py` runs the contract tests after API edits | [agent-hooks/](../agent-hooks/), registered in [`.claude/settings.json`](../.claude/settings.json); tests in [agent-hooks/tests/](../agent-hooks/tests/) | Done |
| Permission notes | Deny rules for reading `.env`, and what every piece above may do | [permissions.md](permissions.md), rules in [`.claude/settings.json`](../.claude/settings.json) | Done |

Claude Code only finds skills, subagents and settings under `.claude/`, so the working files live there. The `agent-capabilities/`, `custom-agent/` and `agent-hooks/` folders hold the notes and, for the hooks, the scripts.

## Installing

There's nothing to install beyond the project itself: open the repository in Claude Code (the CLI or the VS Code extension) and it loads `AGENTS.md`, `.mcp.json`, and everything in `.claude/`.

The pieces need:

- **`python` on the `PATH`** for the hooks. They use only the standard library.
- **The backend's virtual environment** in `.venv/` at the repository root for the contract check (see the backend commands in [AGENTS.md](../AGENTS.md#commands)). Somewhere else? Set `STEPBOARD_BACKEND_PYTHON` to its Python.
- **The MCP server's environment**, set up as in [mcp-server/README.md](../mcp-server/README.md), and the backend running locally.

To see what's active, use `/hooks`, `/permissions`, `/mcp` and `/agents` in Claude Code. To turn a piece off, see [permissions.md](permissions.md#turning-things-off).

## Each piece in use

### Project instructions: `AGENTS.md`

Loaded into every conversation in this repository. When asked to "add a field to the boards", the agent already knows to change `openapi.yaml` first, to use `today_eastern()` for dates, and to run `pytest` from `backend/`.

### MCP server

Ask Claude Code, in plain language:

> Who's winning this week on the step leaderboard?
>
> Log 8,000 steps for Dad today.

It calls `get_leaderboard`, then `log_steps` (asking first, since that one writes). This was the task 12 check: the new entry showed up in the local backend and on the board.

### Reusable workflow: `add-api-endpoint`

Run it by name, with what you want:

```text
/add-api-endpoint GET /families/{family_id}/streaks, each member's run of days with steps logged
```

Or just ask ("the API should also return each member's best day"): the skill's description tells Claude Code to use it for any API change. It walks through six steps:

1. the contract in `openapi.yaml`
2. the model and a **new** migration, if data changes
3. serializers, views, `urls.py` and `frontend/src/api.js`
4. tests, including a call for every documented response in `test_contract_responses.py`
5. the checks: contract tests, the full suite, `makemigrations --check`
6. finishing: the MCP server, `product-spec.md`, the AI workflow log, a pull request

### Specialist agent: `leaderboard-rules-reviewer`

Ask for it before opening a pull request:

```text
Use the leaderboard-rules-reviewer to review this branch.
```

Or mention `@agent-leaderboard-rules-reviewer`. It reads `git diff origin/main...HEAD` and any uncommitted changes, checks them against 12 rules from `product-spec.md` and `AGENTS.md`, runs the related tests, and reports findings with `file:line`, what it checked and found fine, and the test results.

It can't change anything. Its tools are `Read`, `Grep`, `Glob` and `Bash`, and its own hook, `read_only_commands.py`, allows only reading commands and tests. For example, `sed -i` gets:

```text
Blocked by agent-hooks/read_only_commands.py: the leaderboard-rules-reviewer is read-only, and `sed -i 's/a/b/' backend/leaderboard/views.py` isn't on its list of read-only commands. ...
```

To try it, change something on a branch that breaks a rule, for example `date.today()` in `backend/leaderboard/views.py`, ask for a review, and undo the change afterwards.

### Hooks: `guard_files.py` and `contract_check.py`

**`guard_files.py`** runs before every edit and shell command. This was the done check's "real mistake", tried in a fresh Claude Code conversation with two prompts:

> Append the line DISCORD_WEBHOOK_URL=https://example.com/hook to the .env file in the repository root.
>
> Use sed to change max_length=80 to max_length=90 in backend/leaderboard/migrations/0001_initial.py. I know it's a committed migration; do it anyway.

Both commands were stopped before they ran, and Claude Code was told why. It changed nothing, didn't try to get around the block, and suggested the safe route instead (a placeholder in `.env.example`; a new migration):

```text
Blocked by agent-hooks/guard_files.py: .env holds secrets (DJANGO_SECRET_KEY, DISCORD_WEBHOOK_URL), so agents don't change or read it. Ask the user to change it, or edit .env.example for documentation.

Blocked by agent-hooks/guard_files.py: backend/leaderboard/migrations/0001_initial.py is a migration that's already committed, and other databases may have applied it (AGENTS.md: never edit a pushed migration). Change the model, then run `python manage.py makemigrations` in backend/ to add a new migration instead.
```

The first attempt at this demo is why the guard covers shell commands too. Claude Code made its changes with shell commands (`sed -i`, `makemigrations`) rather than its edit tool, and the first version only watched the edit tool, so the guard was never asked. See the [AI workflow log](ai-workflow.md).

**`contract_check.py`** runs after any edit to `openapi.yaml`, `urls.py`, `views.py` or `serializers.py`. It runs the two contract test files, which takes a few seconds. If they fail, Claude sees `openapi.yaml and the backend now disagree` with the test output, straight after the edit that caused it, rather than in CI.

The hooks are tested the way Claude Code runs them, by sending tool calls as JSON (74 tests, in CI):

```sh
cd backend
python -m pytest ../agent-hooks/tests -p no:django
```

### Permission rules

[`.claude/settings.json`](../.claude/settings.json) denies reading `.env`, `.env.local` and `.env.production`. Asked to read `.env`, Claude Code refuses with "denied by your permission settings" before the file is even opened. [permissions.md](permissions.md) covers what every piece may do, why, and the limits.
