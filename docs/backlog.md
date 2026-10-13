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
| 13 | Integration tests | 3, 5 | M |
| 14 | Rest of the agent extension pack | 6 | M |
| 15 | Security scans and PR audit | 7 | M |
| 16 | Ops diagnosis and AI tool/data policy | 7 | S |
| 17 | AI workflow log | 1–8 | S |
| 18 | README and end-to-end run | 8 | S |

S = half a day or less, M = about a day.

## Rubric coverage

Which tasks earn each course rubric criterion.

| Criterion | Tasks |
| --- | --- |
| 1. Problem description | 18 |
| 2. AI-assisted workflow | 17 |
| 3. Technologies and architecture | 18 |
| 4. Frontend (with tests) | Existing React app and tests; run instructions in 18 |
| 5. API contract | 9 |
| 6. Backend (with tests) | 3–7 |
| 7. Database integration | 1, 2, 18 |
| 8. Containerization | 10 |
| 9. Integration tests | 13 |
| 10. Deployment | 11 |
| 11. CI/CD | 11, 13 |
| 12. Agent extension pack | 12, 14 |
| 13. Security, audit and DevOps | 15, 16 |
| 14. Reproducibility | 10, 18 |

Peer reviews are also required for points but aren't repo work, so they're tracked outside this backlog.

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
- **Done when:** a push to `main` gets tested and deployed, the deployed app shows the demo family, and the README links to the working URL.

### 12. MCP server on the Django API
- `mcp-server/` offers `get_leaderboard` and `log_steps`, and calls only the public API.
- **Done when:** an assistant can answer "who's winning this week?" and log steps for a member.

### 13. Integration tests
- Keep unit tests (`tests/unit/`: ranking, callouts, validation) separate from integration tests (`tests/integration/`), each runnable on its own: `pytest tests/unit`, `pytest tests/integration`.
- Integration tests go through the HTTP API against a real Postgres database and cover the key workflows:
  - seed, then read both boards
  - join with `DEMO`, log steps, and see the weekly board change
  - log the same day twice and keep only the newer total
  - send a digest with the Discord webhook mocked, then find it under Messages
- CI runs them against a Postgres service container.
- **Done when:** both suites pass in CI, and the README explains what each one covers and how to run it.

### 14. Rest of the agent extension pack
Builds on `AGENTS.md` and the MCP server from task 12.
- **Reusable workflow** in `agent-capabilities/`: for example, "add an API endpoint", which updates `openapi.yaml`, then the view and serializer, then the tests, then runs the contract test.
- **Specialist agent** in `custom-agent/`: for example, a leaderboard-rules reviewer that checks changes against `product-spec.md`.
- **Hook or guardrail** in `agent-hooks/`: for example, run the contract test whenever `openapi.yaml` or `urls.py` changes, and block edits to `.env`.
- **`docs/permissions.md`**: what each agent and tool may read, run and change, and why.
- **`docs/agent-extension-pack.md`**: what each piece is, how to install it, and an example of each one in use.
- **Done when:** every piece is in the repo and documented, and the hook has been shown to block a real mistake.

### 15. Security scans and PR audit
- Run deterministic scanners and save their output in `security/`:
  - Bandit (Python code)
  - pip-audit and npm audit (dependencies)
  - gitleaks (secrets)
  - Trivy (Docker images)
- Write `security/findings.md`: each finding, whether it was fixed or accepted, and why.
- Run an AI-assisted audit on a real pull request and save the output, plus what you changed because of it.
- Add security notes on the agent extension pack: what the MCP server can do, prompt-injection risks, and secrets handling.
- Add the scanners to CI where they're quick.
- **Done when:** `security/` holds the scan outputs, the PR audit and the notes, and every high-severity finding is fixed or explained.

### 16. Ops diagnosis and AI tool/data policy
- **`ops/`**: diagnose the running deployment (health check, logs, a planned failure such as stopping the database or setting a bad webhook URL) with the course's DevOps tools. Save the output and a short runbook.
- **`security/ai-policy.md`**: which AI tools are allowed, what data may be shared with them (no `.env`, no real family data), and when a person must review the work.
- **Done when:** `ops/` holds real diagnosis output and the runbook, and the policy is linked from the README.

### 17. AI workflow log
- Keep `docs/ai-workflow.md` up to date as you build:
  - tools used and what each was for
  - context files (`AGENTS.md`, `plan.md`, `product-spec.md`, `openapi.yaml`)
  - sample prompts and delegated tasks
  - what you reviewed by hand, what you rejected or fixed, and how you verified changes (tests, contract test, smoke runs)
- **Done when:** each plan day has an entry with at least one real prompt and how its result was reviewed.

### 18. README and end-to-end run
- Rewrite the README for the Django version:
  - the problem and what the app does
  - an architecture section covering how the frontend, backend, database, Docker and CI/CD fit together
  - the database setup for each environment
  - how to set up, run, test (unit, integration and frontend) and deploy
  - the deployed URL
  - links to the extension pack, `security/` and `ops/`
- Update `AGENTS.md` for the Django layout and commands.
- Follow the README from a fresh clone on a clean machine and fix anything that doesn't work.
- **Done when:** someone else can go from clone to a running, tested app using only the README.

## Out of scope for this backlog

Watch integrations, the Discord bot, sync alerts, the Thursday midweek post, and login, as listed under "Cut for now" in the plan. The plan's open questions (ties, login, privacy of daily numbers, host, launch day) should be decided before tasks 3, 6 and 11.
