# Backlog — Django Build

A small backlog for building the [plan](plan.md) with a Django backend instead of FastAPI. Everything else in the plan stays the same: a React (Vite) frontend with one central API client, Postgres (SQLite for tests), `openapi.yaml` as the contract, and `docker compose up` loading demo data.

**Stack:** Django 5, Django REST Framework (DRF), drf-spectacular to check the API against `openapi.yaml`, pytest-django, psycopg.

**Reuse:** `leaderboard.py` (ranking, medals, callouts, message formatting) is pure Python and moves over unchanged, with its tests. `openapi.yaml`, the React frontend and the docs need no changes, apart from the backend commands and paths.

## Summary

| # | Task | Plan day | Size |
| --- | --- | --- | --- |
| 1 | Django project skeleton and settings | 1 | S |
| 2 | Models and migrations | 2 | S |
| 3 | Families, members and join endpoints | 2 | M |
| 4 | Step logging and import endpoint | 2 | M |
| 5 | Demo seed command | 2 | S |
| 6 | Leaderboard endpoints | 3 | M |
| 7 | Digests, Messages and Discord webhook | 3 | M |
| 8 | Scheduled digests | 3 | S |
| 9 | Contract test against `openapi.yaml` | 3 | S |
| 10 | Docker compose with Django | 1–2 | S |
| 11 | CI and deployment | 5 | M |
| 12 | MCP server on the Django API | 6 | M |

S = half a day or less, M = about a day.

## Tasks

### 1. Django project skeleton and settings
Create `backend/` with a `stepboard` project and a `leaderboard` app.
- Settings read `DATABASE_URL` (Postgres in compose, SQLite by default) and `DISCORD_WEBHOOK_URL` (optional) from the environment.
- `TIME_ZONE = "America/New_York"` and a `today_eastern()` helper. A day ends at midnight Eastern.
- DRF installed; `GET /health` returns `{"ok": true}` after checking the database.
- **Done when:** `python manage.py runserver` serves `/health`, and `pytest` runs with pytest-django.

### 2. Models and migrations
- `Family` (name, start_date, unique invite_code), `Member` (family, name), `StepEntry` (member, day, steps 0–100,000, source, updated_at; unique on member + day), and `Message` (family, kind, text, discord_status, created_at).
- Register all four in Django admin, so the family's data can be fixed by hand.
- **Done when:** migrations apply on Postgres and SQLite, and a duplicate (member, day) is rejected by the database.

### 3. Families, members and join endpoints
- `GET/POST /families`, `GET /families/{id}`, `GET /families/{id}/members`, `POST /families/join`.
- The family list leaves out invite codes. Invite codes have 6 characters and are not case-sensitive.
- **Done when:** a test creates a family, joins it with a lowercase code, and gets 404 for an unknown code.

### 4. Step logging and import endpoint
- `POST /steps` takes `member_id`, an optional `source` and 1–366 `{day, steps}` entries. `GET /members/{id}/steps` returns the last 14 days, newest first.
- Logging the same day again replaces the total (`update_or_create`).
- Reject future days (Eastern) and totals outside 0–100,000 with a 422 and a clear message.
- **Done when:** tests cover replacing a day, a multi-day import, and each rejection.

### 5. Demo seed command
- `python manage.py seed_demo` creates the Demo Family (invite code `DEMO`), with Dad, Mom, Alex and Sam, and daily steps from 4 weeks before the current week through a partial today.
- Members get different weekly trends, so ranks change from week to week. If the family already exists, the command does nothing.
- **Done when:** after seeding, both boards show medals, rank changes and callouts, even on a Monday.

### 6. Leaderboard endpoints
- `GET /families/{id}/leaderboards/weekly` and `/all-time`, with an optional `as_of`.
- Weekly counts Monday through `as_of` and compares with the same days of the previous week. All-time counts from the family's start date and compares with the end of the previous month.
- Queries use Django ORM aggregates (`Sum`); ranking and callouts come from the reused `leaderboard.py`.
- **Done when:** the existing report tests pass against the Django version: shared ranks, "new" members, best single day, most improved, and no steps counted from before the start date.

### 7. Digests, Messages and Discord webhook
- `POST /families/{id}/digests` with `kind` (weekly or monthly) and an optional `as_of` builds the digest text and saves a `Message`.
- If `DISCORD_WEBHOOK_URL` is set, post the text with one `httpx` request. Record `sent`, `failed` or `not_configured`; a failed post never loses the message.
- `GET /families/{id}/messages`, newest first.
- **Done when:** tests cover all three Discord states, with the webhook mocked.

### 8. Scheduled digests
- `python manage.py send_digests weekly|monthly` sends a digest for every family, with `as_of` set to yesterday.
- A `scheduler` service runs it Mondays at 8:00 AM Eastern (weekly) and on the 1st at 8:00 AM Eastern (monthly). Use APScheduler in a small management command, so nothing beyond compose is needed.
- **Done when:** running the command by hand adds one message per family.

### 9. Contract test against `openapi.yaml`
- Generate the schema with drf-spectacular and compare its paths and methods with `openapi.yaml` in a test.
- **Done when:** adding or removing a route without updating `openapi.yaml` makes `pytest` fail.

### 10. Docker compose with Django
- The backend image runs `migrate`, then `seed_demo`, then gunicorn. Services: `db` (Postgres), `backend`, `scheduler` and `frontend` (nginx serving the React build and proxying `/api`).
- **Done when:** from a fresh clone, `docker compose up` shows filled boards at http://localhost:8080 with no `.env` file.

### 11. CI and deployment
- GitHub Actions runs the backend tests (pytest) and the frontend tests and build, then deploys `main` when all of them pass.
- Pick the cloud host (an open question in the plan) and use Postgres from that host.
- **Done when:** a push to `main` gets tested and deployed, and the deployed app shows the demo family.

### 12. MCP server on the Django API
- `mcp-server/` offers `get_leaderboard` and `log_steps`, and calls only the public API.
- **Done when:** an assistant can answer "who's winning this week?" and log steps for a member.

## Out of scope for this backlog

Watch integrations, the Discord bot, sync alerts, the Thursday midweek post, and login, as listed under "Cut for now" in the plan. The plan's open questions (ties, login, privacy of daily numbers, host, launch day) should be decided before tasks 3, 6 and 11.
