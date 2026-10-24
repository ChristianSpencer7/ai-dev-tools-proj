# MCP server

An [MCP](https://modelcontextprotocol.io) server that lets an AI assistant, such as Claude Code, read the family's leaderboards and log steps. It calls only the app's public API (the paths in [openapi.yaml](../openapi.yaml)), the same way the React app does, so the app's own rules all still apply.

Ask an assistant *"Who's winning this week?"* or *"Log 8,000 steps for Dad today"*, and it answers with these tools.

## Tools

| Tool | What it does | Changes data? |
| --- | --- | --- |
| `get_leaderboard(board="weekly", as_of=None)` | The weekly (Monday–today) or `all_time` board as text: who leads, each member's medal, rank, steps and movement since the last period, and the callouts. `as_of` is a `YYYY-MM-DD` date. | No |
| `list_members()` | The family's members, so the assistant knows who steps can be logged for | No |
| `log_steps(member, steps, day=None)` | Logs a member's total for a day (today, Eastern, by default). Says whether it replaced an earlier total for that day, and where they now stand this week. | **Yes**: a day's total replaces any earlier one |

- **Members are found by name** within the configured family: an exact match (any letter case) first, otherwise the only name that starts with what was given. If it could be more than one person, the tool asks which, and logs nothing.
- **The tools are marked for the client:** `get_leaderboard` and `list_members` as read-only, `log_steps` as destructive (it replaces a day's total) and idempotent (repeating it changes nothing). Claude Code uses these marks to decide when to ask before running a tool.
- **Errors come back as messages the assistant can pass on:**
  - **the app's own:** "Steps must be 100,000 or fewer.", "These days haven't happened yet: …"
  - **an unknown member or family:** with the names that do exist
  - **the app not running:** "Can't reach the app at … Is it running?"
- Steps logged this way are saved with source `manual`, since a person asked for them.

## Settings

Two environment variables, both optional:

| Variable | Default | Meaning |
| --- | --- | --- |
| `STEPBOARD_API_URL` | `http://localhost:8000` | The app's API. For the live site, `https://159-89-228-242.sslip.io/api`. Must be `https://`, or `http://` to this machine; anything else stops the server at startup |
| `STEPBOARD_FAMILY` | `Demo Family` | The one family the tools read and write |

**It points at your local backend by default on purpose.** `log_steps` changes data, and the app has no logins, so a server pointed at the live site can change real boards. Use the live site deliberately, for reading or for a real family's own steps.

## Set up

From `mcp-server/`, in its own virtual environment (the MCP SDK brings many packages; they stay out of the backend's):

```sh
python -m venv .venv
.venv/Scripts/activate            # macOS/Linux: source .venv/bin/activate
pip install -e ".[dev]"
python -m stepboard_mcp           # runs over stdio; normally your MCP client starts it
```

It uses the official MCP SDK, **version 2** (`mcp>=2.3`). Version 2 renamed `FastMCP`, used in most online examples, to `MCPServer`.

## Use it from Claude Code

[`.mcp.json`](../.mcp.json) at the repository root registers it as `stepboard`, so Claude Code in this project starts it automatically:

1. Start the backend: `python manage.py runserver` in `backend/`.
2. Open a new Claude Code conversation in this repository. `/mcp` shows `stepboard` and whether it's connected.
3. Ask *"Who's winning this week?"*, or *"Log 8,000 steps for Dad today"*.

Notes:

- `.mcp.json` runs `mcp-server/.venv/Scripts/python.exe` (Windows). On macOS or Linux, set `STEPBOARD_MCP_PYTHON=mcp-server/.venv/bin/python`. `STEPBOARD_API_URL` and `STEPBOARD_FAMILY` in your environment override the defaults in `.mcp.json`.
- Claude Code asks before using a project's `.mcp.json` servers in some kinds of session. **In the VS Code extension, it loaded this one without asking.** Anyone who opens the repository there gets these tools, including `log_steps`; see [Security](#security).

## Tests

```sh
pytest                     # from mcp-server/
```

| File | Covers |
| --- | --- |
| `tests/test_tools.py` | The tools through a real MCP client against a fake app: what's sent to the API (or not), the replies, name matching, board text, and every error |
| `tests/test_against_backend.py` | The tools against the real Django app on a temporary database, including starting the server over stdio the way Claude Code does |

The second file needs the backend installed: `pip install -e ../backend` in this environment, or `STEPBOARD_BACKEND_PYTHON` pointing at a Python that has it (locally, the repository's `.venv`). Without it, those tests are skipped with the reason. CI installs both and sets `STEPBOARD_REQUIRE_BACKEND=1`, so there they fail rather than skip.

## Security

The full notes are in [security/agent-extension-pack.md](../security/agent-extension-pack.md), and the security review of this server's pull request, with what it fixed, is in [security/pr-audit.md](../security/pr-audit.md). In short:

- **`log_steps` writes data, and the app's API has no logins.** Anyone who can run this server against an address can change that family's boards. Hence the local default, and one family per server.
- **The tools act on what the assistant reads.** Text the assistant sees elsewhere (a web page, a file, an issue) could try to instruct it to log steps. Claude Code's permission prompt for destructive tools is the check; don't allow `log_steps` without asking.
- **Project `.mcp.json` servers can load without a prompt** in some clients, as in the VS Code extension.
- **The server only calls the public API.** It has no database access and no secrets: no keys, no webhook URL.
