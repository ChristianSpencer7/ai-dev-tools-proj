# AI Workflow Log

How AI tools were used to build this project, what they were given to work from, and how their work was reviewed and verified. New entries go at the end of the log, one per backlog task.

## Tools and roles

| Tool | Used for |
| --- | --- |
| **Claude Code** (Claude Opus 5.5) in VS Code | Planning, writing code, tests and docs, running commands and checks, diagnosing failures, writing commit messages |
| **GitHub Actions** | Running every check on each push and pull request, then deploying `main` |

Division of work:

- **The developer** chose what to build and in what order, made the decisions the plan left open, ran the server setup that needs personal accounts and credentials (DigitalOcean, GitHub secrets, SSH keys), tested by hand in the browser and on the server, and approved every commit and push.
- **The AI** proposed plans, broke each backlog task into steps, implemented one step at a time, verified its own work before reporting it, and explained trade-offs where a decision was needed. It never committed or pushed without being asked, and never handled the production secrets.

## Context files

These files are what the AI works from. Keeping them accurate is part of the workflow: an outdated one leads an AI assistant to follow the wrong instructions.

| File | Role |
| --- | --- |
| [docs/plan.md](plan.md) | The design: what the app does and why |
| [docs/backlog.md](backlog.md) | The 18 tasks, each with a "Done when" check, and how they map to the course rubric |
| [product-spec.md](../product-spec.md) | Behavior and acceptance criteria |
| [openapi.yaml](../openapi.yaml) | The API contract the backend and frontend both follow |
| [AGENTS.md](../AGENTS.md) | Instructions for AI agents: layout, commands, and rules such as "contract first" and "tests never reach real services" |
| [docs/deployment.md](deployment.md) | How the production server is set up and run |

## The working loop

Every backlog task followed the same loop:

1. **Plan the task.** Prompt: *"let's move to task 6"* or *"give the steps I need to go through task 2"*. The AI breaks the task into numbered steps, names the gotchas, and lists any decisions that belong to the developer, with a recommendation for each.
2. **Decide.** The developer answers the open questions (see [Decisions](#decisions-made-by-the-developer)).
3. **One step at a time.** Prompt: *"step 3"*. The AI implements that step only.
4. **Verify before reporting.** The AI runs the step against real inputs: throwaway databases, a real server process, real HTTP requests, a fake Discord webhook, Docker. Then it runs the full test suite. For test steps, it also breaks the code on purpose (mutation checks) to confirm the tests would notice. Its reports say what was checked and what wasn't.
5. **Review.** The developer reads the summary and the diff, asks questions (*"what does the imported models do?"*, *"what is the secret_key used for?"*), and tests by hand when the step is user-facing.
6. **Commit and push**, only when asked: *"commit and push"*. One commit per step, with a message saying what changed and why.

## Log

### 2026-10-12 to 10-13: Plan and backlog

- **Prompt:** *"there is a new plan.md. can you edit the project so it lines up with this plan?"* The AI rebuilt the first prototype (a Discord bot) as a web app matching the plan, with a FastAPI backend (`d3b86a0`).
- **Prompt:** *"using the plan.md, propose a small backlog of tasks for building this in django"* gave the 12-task backlog (`86d4049`).
- **Prompt:** the course rubric, then *"do the tasks you created in the backlog do its best to cover the rubric?"* The AI's answer was no: 4 criteria had no task (AI workflow, integration tests, security, most of the extension pack). The backlog grew to 18 tasks, plus a table mapping each rubric criterion to its tasks (`5fe0b6b`).

### 2026-10-17 to 10-18: Tasks 1–2, Django project and models

- **Delegated:** project scaffolding, settings from environment variables, `/health`, pytest-django, the four models, constraints, migrations, admin, and model tests.
- **Found along the way:**
  - The app folder had been created as `leaderbpard` (a typo); the AI noticed and renamed it.
  - `startproject` refused the name `stepboard` because the old FastAPI package was still installed under that name. The AI explained the cause and uninstalled it.
- **Developer review:** created the admin account, entered data by hand, and confirmed the database rejects a duplicate day. Then asked to reword the 100,000-step error. The AI implemented "Steps must be below 100000", but pointed out that 100,000 itself is allowed, so the wording was inaccurate. The developer chose "Steps must be 100,000 or fewer." (`65f2f72`).
- **Verified:** migrations and all tests on both SQLite and Postgres (in Docker).

### 2026-10-19: Tasks 3–10, the API, scheduler, contract tests and Docker

- **Delegated:** every endpoint in `openapi.yaml`, the demo seed, digests with optional Discord, the scheduler, the contract tests and the Docker setup, one step and one commit at a time.
- **Developer review:** tested each group of endpoints by hand in DRF's browsable pages and the React app: joining with a lowercase invite code, logging steps, the boards, sending digests.
- **What verification caught.** These were each found by the AI's own checks before being reported, unless noted:

| Problem | How it was caught | Fix |
| --- | --- | --- |
| Tests didn't detect comparing "the week so far" with **all** of last week | Mutation check: a deliberate break went unnoticed | Added a test that does catch it (task 6) |
| Weekly and monthly digest jobs ran **at the same time** on a Monday the 1st; on SQLite the second failed with "database is locked" | Forcing both scheduled jobs to run at once | Jobs now run one at a time (`d7d137c`) |
| `httpx` logs each request's full URL, which for Discord is the **webhook secret** | Turning on INFO logging, then searching the log for the URL | `httpx` logging kept at WARNING; a test guards it |
| Three endpoints returned `422` for bad dates, but `openapi.yaml` didn't document it | The new response contract test | `openapi.yaml` updated first, then committed separately (`94e37f5`) |
| `tests/conftest.py`: a real `DISCORD_WEBHOOK_URL` in `.env` would have made `pytest` post to Discord | Reasoning about the setup, then proved: with the guard, 0 requests reached a fake webhook; without it, 7 did | The guard fixture |
| `pytest` errors on the developer's machine | Reported by the developer | It had been run from the repository root instead of `backend/`; documented in `AGENTS.md` |
| The old database URL format (`postgresql+psycopg://`) wasn't understood by Django's `dj-database-url` | Checking the Compose settings before running them | `postgres://` |

### 2026-10-19 to 10-23: Task 11, CI and deployment

- **Developer decision:** a DigitalOcean server running the same Docker Compose setup, after the AI compared it with Render and Fly.io.
- **Delegated:**
  - the CI workflow
  - production HTTPS settings
  - `docker-compose.prod.yml`, the `Caddyfile` and the deploy script
  - the runbook
  - the deploy job
- **Done by the developer, with commands the AI wrote out:** creating the server and SSH keys, hardening SSH and the firewall, installing Docker, the first start, and adding the four GitHub secrets.
- **What verification caught:**

| Problem | How it was caught | Fix |
| --- | --- | --- |
| An empty `DATABASE_URL`, which the first CI draft set for SQLite, gives Django's "dummy" database, so every test would fail | Checking it locally before pushing | Empty now counts as unset; explicit URLs per CI job (`c3e6c89`) |
| `DJANGO_HTTPS=1` never reached the containers: Compose only passes the settings it lists | A Docker test expecting a redirect got `200` | Listed in `docker-compose.yml` (`4fcf41d`) |
| `check --deploy` failed on startproject's development email backend | Running the deployment check with production settings | Removed; the app sends no email |
| Behind the proxy, HTTPS redirects would loop, and the container's own health check would be redirected | Reasoning, then a test for each | nginx passes `X-Forwarded-Proto`; `/health` exempt |
| On the server, ports 80 and 443 looked blocked | Port checks from outside, then a test container on port 80 | Not a fault: the server gives no reply when nothing is listening |
| Starting the stack failed: "port is already allocated" | Reported by the developer | The test container was still running. Afterwards, Caddy couldn't get a certificate; its logs and `dc ps` showed the container had been half-created during the failed start. Recreating it fixed it, and the runbook now covers it (`7fcbd2b`) |

- **Result:** the first automatic deploy, from merging pull request #2, passed every check, deployed, and confirmed the live site responds.

### 2026-10-23: Task 13, integration tests

- **Prompt:** *"let's go with task 13"*. The developer chose the AI's definition: **unit** tests call one module directly; **integration** tests go through the HTTP API across endpoints.
- **Delegated:**
  - splitting the 145 tests into `tests/unit/` and `tests/integration/`
  - seven workflow tests, each a whole user journey
  - separate CI steps for each kind
  - `backend/tests/README.md`
- **Verified:** both folders on SQLite and Postgres locally, then on GitHub, where CI showed "Unit tests" and "Integration tests" as separate steps on both databases.
- **What verification caught:**

| Problem | How it was caught | Fix |
| --- | --- | --- |
| A digest built for the wrong family passed all seven workflow tests, because the family under test was always the first one in the database | Mutation checks aimed at the links between components (10 breaks) | The digest workflow creates a neighbouring family first (`1039734`) |
| A test file left directly in `tests/` would run in neither CI step | Reasoning about the split | `conftest.py` rejects test files outside the two folders |
| The AI's comment claimed a misspelled `pytest -m` marker would be an error; it silently selects nothing | Trying it | The comment and the docs now say so, and recommend the folder form |



Verification found these before they caused harm. They're recorded because catching them is the point of the loop.

- Shell quoting mistakes in its own check commands. Caught because the commands failed; rerun correctly.
- An edit to `ci.yml` that mangled escape characters. Caught by reading the file back before testing; fixed by hand.
- A port probe that reported an open SSH port as blocked. Caught because SSH had just answered on it; redone with a plain connection test.
- A mutation check aimed at a field that only reads requests, so it couldn't fail. Spotted in the results and redone on a response field.
- Restoring files after mutation checks changed their line endings. Caught by `git status`; files restored byte for byte from then on.
- Two of task 13's mutation checks were flawed: one turned the code into a crash, the other lacked an import and failed with `NameError`, so neither tested what it claimed. Spotted from the `ERROR`s in the results; one was redone properly and the other dropped (its case was already covered).
- A commit meant to hold only `docs/backlog.md` also took 13 test-file moves that `git mv` had already staged. Caught by checking what the next commit contained. With the developer's agreement, the two commits were rebuilt and the branch replaced on GitHub with `--force-with-lease`. Since then the AI checks what's staged before committing only part of the changes.

## Decisions made by the developer

| Decision | Options the AI laid out | Chosen |
| --- | --- | --- |
| How families join | Accounts, or invite code only | Invite code only |
| Ties on a board | Shared rank, or best single day wins | Shared rank |
| The same day twice in one import | Last one wins, or reject | Reject |
| One bad entry in a batch | Save the rest, or save nothing | Save nothing |
| `--reset` for the demo seed | Add it or not | Add it |
| Scheduler | Call the API, or the code directly; block duplicates; skip the demo family | Code directly; block duplicates; skip the demo (`--include-demo` to include it) |
| Contract tests | Routes only, or also responses | Both |
| Host | VPS with Docker Compose, Render, Fly.io | DigitalOcean VPS |
| Web address | sslip.io, or a domain | sslip.io |

## Adding an entry

For each task, add a dated section with:

- the prompt or prompts that started it
- what was delegated, and what the developer did themselves
- what was checked, and anything verification caught: the problem, how it was caught, the fix
- the developer's decisions and any manual testing
- the commits
