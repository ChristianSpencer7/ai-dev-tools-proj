# Permissions

What each piece of the [agent extension pack](agent-extension-pack.md) can read, run and change, why, and where its limits are. Everything here applies to Claude Code sessions opened in this repository.

## At a glance

| Piece | Can read | Can run | Can change | Enforced by |
| --- | --- | --- | --- | --- |
| [`AGENTS.md`](../AGENTS.md) (project instructions) | n/a | n/a | n/a | Nothing: it guides the agent; the rows below enforce |
| [`add-api-endpoint`](../.claude/skills/add-api-endpoint/SKILL.md) skill | What the session can | What the session can | What the session can | Adds no rights: it's instructions, and everything below still applies |
| [`leaderboard-rules-reviewer`](../.claude/agents/leaderboard-rules-reviewer.md) subagent | Project files, except secrets | **Read-only commands only**: `git diff/log/show/status`, `grep`, `cat`, `ls`, `find`, `sed` without `-i`, `pytest`, `manage.py check` | **Nothing** | Its tool list (`Read, Grep, Glob, Bash`, no `Edit`/`Write`) and its own hook, [`read_only_commands.py`](../agent-hooks/read_only_commands.py) |
| [MCP server](../mcp-server/README.md) (`get_leaderboard`, `list_members`, `log_steps`) | One family's boards and members, **through the public API** | Nothing | **That family's step totals** (`log_steps`) | Its design: it calls only the API in [`openapi.yaml`](../openapi.yaml), has no database access and no secrets, and points at the local backend unless told otherwise |
| [`guard_files.py`](../agent-hooks/guard_files.py) hook | n/a | n/a | Blocks agents changing **`.env` files, database files and committed migrations**, and reading `.env` | Claude Code runs it before every `Edit`, `Write`, `Bash` and `PowerShell` call |
| [`contract_check.py`](../agent-hooks/contract_check.py) hook | Runs the contract tests | The backend's tests | Nothing; it reports drift to Claude | Claude Code runs it after edits to `openapi.yaml`, `urls.py`, `views.py` or `serializers.py` |
| Permission rules in [`.claude/settings.json`](../.claude/settings.json) | Deny reading `.env`, `.env.local` and `.env.production` anywhere | | (A `Read` deny also blocks editing and creating them) | Claude Code itself, before any tool runs |

## Why these limits

- **Secrets stay out of conversations.** `.env` holds `DJANGO_SECRET_KEY` and `DISCORD_WEBHOOK_URL`. Anything an agent reads can end up in its context, its logs, or a reply. So two layers keep it out: the `Read` deny rules for Claude's file tools, and the guard for shell commands (`cat .env`, `Get-Content .env`), which `Read` rules don't cover. The production `.env` lives only on the server, and no agent has access to it.
- **Committed migrations are history.** Other databases, including production's, may already have applied them; editing one makes databases disagree silently. Agents add a new migration instead, which the guard's message says.
- **The reviewer only reports.** A reviewer that could also edit would mark its own work. Read-only means its findings are suggestions a person or the main session acts on.
- **The MCP server writes, so it starts local.** `log_steps` changes data, and the app has no logins. Pointing it at the live site (`STEPBOARD_API_URL`) is a deliberate choice, and each server works with one family.
- **Contract drift is caught straight away.** The contract check doesn't block; it tells Claude the moment `openapi.yaml` and the code disagree, before CI would.

## Limits

These guardrails make the usual mistakes hard. They aren't a sandbox.

- **The guard checks a shell command's text, not what it does.** It catches the ordinary ways of changing a file (`sed -i`, `>`/`>>`, `tee`, `rm`, `mv`, `cp`, `Set-Content`, `Remove-Item`, Python's `open(..., 'w')`), but a command built to hide its target (a variable holding the path, a script file) can get past it. Claude Code's own [sandboxing](https://code.claude.com/docs/en/sandboxing.md) is the tool for a hard boundary.
- **It has false positives.** Any shell command that mentions `.env` is blocked, including one that only writes text containing it, such as a commit message or test strings. The workaround is to use the edit tool (which checks the file being changed, not the text) or a message file. This happened twice while building the pack; it's the price of not letting secrets be read.
- **The reviewer's allowlist is deliberately small.** Commands it doesn't know are blocked, even harmless ones. It can still run the test suite, which writes only to its own temporary test database.
- **Hooks need Python on the `PATH`.** If `python` can't be found, Claude Code reports a hook error and the call goes ahead. The tests in [`agent-hooks/tests/`](../agent-hooks/tests/) run in CI, but they can't check your machine.
- **Prompt injection.** Text an agent reads (a web page, an issue, a file) could tell it to log steps or change code. The guardrails above still apply, and Claude Code's permission prompts are the other check: `log_steps` is marked destructive, so keep asking before it runs.
- **Project settings load without a prompt in the VS Code extension.** Opening this repository there turned on its MCP server and hooks without asking. That's convenient here, and a reason to read `.claude/` and `.mcp.json` in any repository you clone.

## Turning things off

- **A hook:** remove its entry from `.claude/settings.json`, or for the reviewer's, from its front matter. `/hooks` in Claude Code shows what's active.
- **The MCP server:** remove `stepboard` from `.mcp.json`, or add it to `disabledMcpjsonServers` in your own settings.
- **The skill or subagent:** delete its folder or file under `.claude/`.
- **A permission rule:** edit `permissions.deny` in `.claude/settings.json`; `/permissions` shows what's active.
