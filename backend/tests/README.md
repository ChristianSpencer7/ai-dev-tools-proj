# Backend tests

The backend has two kinds of tests, in two folders. Every test must be in one of them: CI runs each folder as its own step, so `tests/conftest.py` rejects a test file anywhere else rather than let it silently never run.

| Folder | What it tests | How |
| --- | --- | --- |
| [`unit/`](unit/) | One module on its own: the ranking rules, model constraints, building a board, the demo seed, scheduled digests and the schedule | Calls the code directly in Python. May use Django's test database. |
| [`integration/`](integration/) | The app as its users see it: every endpoint, whole user journeys across endpoints, HTTPS behind the proxy, and the `openapi.yaml` contract | Through the HTTP API only, the way the React app and a reviewer use it |

## What's in each

**Unit**

| File | Covers |
| --- | --- |
| `test_ranking.py` | Ranks, shared ranks for ties, medals, movement, callouts, message formatting (pure functions) |
| `test_models.py` | The database's own rules: one entry per member per day, 0–100,000 steps, unique invite codes, deletes |
| `test_boards.py` | Weekly and all-time boards: what counts, comparisons, titles, callouts, edge cases |
| `test_seed.py` | The demo family and the `seed_demo` command, including `--reset` |
| `test_scheduled_digests.py` | The `send_digests` command, which families it skips, and the schedule's run times |

**Integration**

| File | Covers |
| --- | --- |
| `test_workflows.py` | **Whole user journeys:** a reviewer's first visit, a new family's first two weeks, correcting a day, imports, a refused import, a digest reaching Discord, scheduled digests showing in the app |
| `test_families.py`, `test_steps.py`, `test_leaderboards.py`, `test_digests.py`, `test_health.py` | Each endpoint: successes, `404`s, `422`s, wrong methods |
| `test_contract.py` | The backend serves exactly the routes and path parameters in `openapi.yaml` |
| `test_contract_responses.py` | Every response's status code and body match `openapi.yaml`, with no fields it doesn't list |
| `test_https.py` | HTTPS redirects behind the proxy, and the health check's exemption |

## Running them

From `backend/`, with the virtual environment active:

```sh
pytest tests/unit           # fast
pytest tests/integration
pytest                      # both
pytest tests/integration/test_workflows.py -k reviewer   # one file, or tests matching a name
```

`pytest -m unit` and `pytest -m integration` also work, but a misspelled `-m` selects nothing without complaint; the folder form can't.

`pytest` must be run from `backend/`, where `pytest.ini` is; from the repository root, Django isn't set up and every file fails to load.

**On Postgres**, as CI and production use it, with a local Postgres on port 5432 (for example `docker run -d --name stepboard-pg -e POSTGRES_USER=stepboard -e POSTGRES_PASSWORD=stepboard -e POSTGRES_DB=stepboard -p 5432:5432 postgres:16-alpine`):

```powershell
$env:DATABASE_URL = "postgres://stepboard:stepboard@localhost:5432/stepboard"
pytest
Remove-Item Env:DATABASE_URL
```

## In CI

The backend job runs `pytest tests/unit`, then `pytest tests/integration` (even if the unit tests failed, so one run shows both), on SQLite and on Postgres. GitHub shows each as its own step.

## Writing tests

- **Which folder:** calling a function or model directly → `unit/`; going through `client.get` / `client.post` → `integration/`.
- **Never reach real services.** `conftest.py` clears `DISCORD_WEBHOOK_URL` and fails any test that tries to post to Discord, even with a real webhook in `.env`. Tests that need Discord replace `httpx.post` with a fake (see `test_digests.py`).
- **Pin "today".** Anything date-based must not depend on the real clock. Workflow tests pin Django's clock beneath `today_eastern()`, so every part of the app agrees on the date (see the `today` fixture in `test_workflows.py`).
- **Check the tests can fail.** For a new rule, break the code on purpose and confirm a test fails for the right reason, not because of a crash.
