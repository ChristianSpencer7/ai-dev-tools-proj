# AGENTS.md

Instructions for AI coding agents working in this repo.

## What this is

A family step leaderboard: React (Vite) frontend, FastAPI backend, Postgres (SQLite in tests), run with `docker compose up`. Read [product-spec.md](product-spec.md) for behavior and [docs/plan.md](docs/plan.md) for the design and schedule.

## Layout

| Path | What's there |
| --- | --- |
| `openapi.yaml` | The API contract. Change it first, then the code. |
| `backend/src/stepboard/` | `api.py` routes, `schemas.py` bodies, `db.py` tables and queries, `leaderboard.py` pure ranking math, `reports.py` boards, `digests.py` digests and Discord, `seed.py` demo data, `scheduler.py` Monday and monthly jobs |
| `backend/tests/` | pytest; `test_contract.py` checks routes against `openapi.yaml` |
| `frontend/src/api.js` | The **only** place the frontend calls the backend |
| `frontend/src/components/` | Leaderboard, LogSteps, Messages, JoinFamily |

## Commands

```sh
# Backend (from backend/)
pip install -e ".[dev]"
pytest

# Frontend (from frontend/)
npm install
npm test
npm run build

# Everything
docker compose up --build
```

## Rules

- **Contract first.** Any API change updates `openapi.yaml`, `schemas.py` and `api.py` together. `pytest` fails if the routes and the spec drift apart.
- **One API client.** Components call `api.*` from `frontend/src/api.js`, never `fetch` directly.
- **Eastern time.** A day ends at midnight `America/New_York`. Use `today_eastern()` (backend) or `todayEastern()` (frontend), never the server's local date or UTC.
- **Same day replaces.** Step entries are keyed by (member, day); a new total overwrites the old one.
- **Keep `leaderboard.py` pure.** No database or network code there, so ranking rules stay easy to test.
- **Discord stays optional.** Nothing may require `DISCORD_WEBHOOK_URL`, and a failed post must never lose a digest.
- **Tests with changes.** Add or update tests for any behavior change, and run both test suites before saying you're done.
- **No secrets in the repo.** Configuration comes from environment variables; `.env` is gitignored.
