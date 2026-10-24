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

### 2026-10-23 to 10-24: Task 12, the MCP server

- **Prompt:** *"let's move to task 12"*. The developer accepted three recommendations: Python with the official SDK, the **local backend by default** (since `log_steps` writes data and the API has no logins), and **one family**, with members found by name.
- **Delegated:** the package, an API client, three tools, tests against a fake app and the real backend, a CI job, `.mcp.json`, and docs.
- **Developer's check:** in a new Claude Code conversation, asked *"Who's winning this week on the step leaderboard?"* and *"Log 8,000 steps for Dad today"*. Claude Code called `get_leaderboard` and `log_steps` on its own. Reading the local backend directly confirmed Dad's new entry and his place on the board. That was the backlog's done check.
- **What verification caught:**

| Problem | How it was caught | Fix |
| --- | --- | --- |
| The MCP SDK is now version 2, where `FastMCP` (in most examples) is renamed `MCPServer` | Reading the installed package before writing code | Written against version 2, pinned `mcp>=2.3,<3` |
| No `tzdata`, so "today, Eastern" would fail on Windows | The first check against the backend failed | Added to the dependencies |
| The "this week" note compared the day with the first of the month | Reading the code back before testing | Compares with this week's Monday |
| `httpx` logged a line per request into the client's MCP logs | Calling the tools | Turned down to warnings |
| End-to-end tests skip without the backend, which in CI would pass while testing nothing | Reasoning about the skip | CI sets `STEPBOARD_REQUIRE_BACKEND=1`, which turns the skip into a failure |
| Claude Code didn't ask before loading the project's server | Reported by the developer | Not a fault, per Claude Code's docs; recorded as a security note for task 15 |

### 2026-10-24: Task 14, the rest of the agent extension pack

- **Prompt:** the AI proposed six steps, and the developer replied *"works for me. Let's start with step 1"*.
- **Delegated:**
  - two hooks: `guard_files.py` blocks changes to `.env`, database files and committed migrations; `contract_check.py` runs the contract tests after API edits
  - the `add-api-endpoint` skill
  - the read-only `leaderboard-rules-reviewer` subagent, with its own command allowlist hook
  - deny rules for reading `.env`
  - [permissions.md](permissions.md) and [agent-extension-pack.md](agent-extension-pack.md)
  - 74 hook tests, which run in CI
- **Developer's check:** the backlog's "the hook has been shown to block a real mistake". In a fresh Claude Code conversation, the developer asked it to append a line to `.env`, then to `sed` a committed migration, *"do it anyway"*. The guard blocked both; Claude Code said why and offered the safe route. The AI checked separately that the deny rule stops it reading `.env`.
- **What verification caught:**

| Problem | How it was caught | Fix |
| --- | --- | --- |
| The first demo never reached the guard. Claude Code used shell commands (`sed -i`, then `makemigrations`), and the guard only watched the edit tool. It also left a model change and an unapplied migration `0004` behind | Reported by the developer: *"The edit was not blocked and went through"* | With the developer's approval, the stray changes were reverted, and the guard now checks `Bash` and `PowerShell` commands too (`ec1db02`). The retried demo was blocked |
| A test of Windows-style paths passed on Windows but failed in CI, where `\` isn't a path separator | CI's backend job failed | Reproduced in a Linux container (`python:3.12-slim`); the test now runs only on Windows |
| A subagent's tool list can allow `Bash`, but not limit which commands it runs, so a "read-only" reviewer could still `sed -i` | Planning the subagent | A hook in the subagent's own front matter allows only reading commands and tests |
| A `Read` deny rule can't make an exception, so `.env.*` would also block `.env.example` | Planning the rules | The rules name `.env`, `.env.local` and `.env.production` |
| The guard blocks the AI's own shell commands that mention `.env`: test strings, a settings edit, a commit message | It happened, twice | Not a fault: that's the rule working. The AI uses its edit tool, or a message file for commits; recorded as a limit in [permissions.md](permissions.md#limits) |

### Mistakes the AI made, and how they were caught

Verification found these before they caused harm. They're recorded because catching them is the point of the loop.

- Shell quoting mistakes in its own check commands. Caught because the commands failed; rerun correctly.
- An edit to `ci.yml` that mangled escape characters. Caught by reading the file back before testing; fixed by hand.
- A port probe that reported an open SSH port as blocked. Caught because SSH had just answered on it; redone with a plain connection test.
- A mutation check aimed at a field that only reads requests, so it couldn't fail. Spotted in the results and redone on a response field.
- Restoring files after mutation checks changed their line endings. Caught by `git status`; files restored byte for byte from then on.
- Two of task 13's mutation checks were flawed: one turned the code into a crash, the other lacked an import and failed with `NameError`, so neither tested what it claimed. Spotted from the `ERROR`s in the results; one was redone properly and the other dropped (its case was already covered).
- A commit meant to hold only `docs/backlog.md` also took 13 test-file moves that `git mv` had already staged. Caught by checking what the next commit contained. With the developer's agreement, the two commits were rebuilt and the branch replaced on GitHub with `--force-with-lease`. Since then the AI checks what's staged before committing only part of the changes.
- Adding the task 13 entry replaced this section's heading instead of going in front of it, so this list read as part of task 13 (merged in pull request #3). Caught when the next entry couldn't find the heading; restored with task 12's entry.
- The first version of the `.env` guard only watched the edit tool, although agents change files with shell commands just as often. Caught by the developer's first demo, above.
- Hook test strings holding Windows paths were written as ordinary Python strings, so sequences such as `\0` in `\0001_initial.py` became escape characters. Caught in the test run; switched to raw strings, and the hook tests were rerun with Python's escape-sequence warnings turned into errors.
- A rule in the reviewer's first draft said a missing member is always checked before the request body, which isn't true for `POST /steps`, where the member is part of the body. Caught while writing the subagent, since it would have flagged correct code; corrected before it was committed.

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
| Unit vs integration tests | Unit = no database at all, or unit = one module called directly | One module called directly; integration = through the HTTP API |
| MCP server | Language; local or live backend by default; any family or one | Python with the official SDK; local by default; one family, members found by name |
| The guard after the first demo | Leave it to edits, or also check shell commands | Also check shell commands, and revert what the first demo changed |

## Adding an entry

For each task, add a dated section with:

- the prompt or prompts that started it
- what was delegated, and what the developer did themselves
- what was checked, and anything verification caught: the problem, how it was caught, the fix
- the developer's decisions and any manual testing
- the commits
