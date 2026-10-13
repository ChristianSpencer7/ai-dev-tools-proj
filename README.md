# Family Step Leaderboard

A web app where a family logs daily steps and competes on a weekly board (Monday–Sunday) and an all-time board. It builds weekly and monthly digests, shows them in the app, and posts them to Discord when a webhook is configured.

- Design and schedule: [docs/plan.md](docs/plan.md)
- Behavior and acceptance criteria: [product-spec.md](product-spec.md)
- API contract: [openapi.yaml](openapi.yaml)
- Notes for AI coding agents: [AGENTS.md](AGENTS.md)

## Run it

You only need Docker.

```sh
docker compose up --build
```

- App: <http://localhost:8080>
- API docs: <http://localhost:8000/docs>

The Demo Family comes preloaded with about four weeks of steps, so the boards are filled on first load.

## Try it as a reviewer

1. Open <http://localhost:8080>. The demo family's weekly board is showing; switch to **All-time** to see the totals.
2. Go to **Join or create**, enter invite code `DEMO` and your name, then **Join**.
3. On **Log steps**, enter a big number for today and save. Check the leaderboard to see your rank.
4. Open **Messages** and choose **Send weekly digest now**.

## Discord (optional)

Without setup, digests appear only on the Messages page. To also post them to a channel, create a webhook (Channel settings → Integrations → Webhooks), then:

```sh
cp .env.example .env    # set DISCORD_WEBHOOK_URL
docker compose up --build
```

## Develop without Docker

```sh
# Backend: http://localhost:8000, using a local SQLite file
cd backend
python -m venv .venv && .venv/Scripts/activate     # macOS/Linux: source .venv/bin/activate
pip install -e ".[dev]"
python -m stepboard.seed
uvicorn stepboard.api:create_app --factory --reload

# Frontend: http://localhost:5173, sends /api to the backend
cd frontend
npm install
npm run dev
```

## Tests

```sh
cd backend && pytest
cd frontend && npm test
```

## Repository layout

| Path | Contents |
| --- | --- |
| `backend/` | FastAPI app, database models, leaderboard logic, seed script, scheduler |
| `frontend/` | React app with one central API client (`src/api.js`) |
| `.github/workflows/` | CI |
| `docs/` | Design plan, agent extension pack, permissions |
| `security/`, `ops/` | Security scans and ops notes (day 7) |
| `agent-capabilities/`, `agent-hooks/`, `mcp-server/`, `custom-agent/` | Agent extension pack (day 6) |
