# Family Step Leaderboard

A Discord bot that tracks family members' daily steps and posts weekly and all-time leaderboards. See [docs/path.md](docs/path.md) for the design plan.

Current status: **phase 1** (core bot, SQLite, `/log`, `/leaderboard`).

## Set up the Discord bot

1. Create an application at <https://discord.com/developers/applications>, open the **Bot** tab, and copy the token.
2. Under **OAuth2 → URL Generator**, select the `bot` and `applications.commands` scopes and the **Send Messages** permission. Open the generated URL to add the bot to the family server.
3. Turn on Developer Mode in Discord (Settings → Advanced), then right-click the server and choose **Copy Server ID**.

## Run locally

```sh
python -m venv .venv
.venv/Scripts/activate        # Windows; use .venv/bin/activate on macOS/Linux
pip install -e ".[dev]"
cp .env.example .env          # then fill in the token, server ID, and launch day
python -m stepboard
```

The web endpoint runs at `http://localhost:8000/health`.

## Commands

| Command | What it does |
| --- | --- |
| `/log <steps> [day]` | Record steps by hand for `today` (the default), `yesterday`, or `YYYY-MM-DD` |
| `/leaderboard [week \| all-time]` | Show this week's standings so far, or the all-time totals |

## Tests

```sh
pytest
```
