# Ops

Diagnosing the running app with Docker Compose: a health report, planned-failure drills, and what each showed. **When something's wrong, start with the [runbook](runbook.md).** The server's setup and everyday commands are in [docs/deployment.md](../docs/deployment.md).

| File | What it is |
| --- | --- |
| [collect.sh](collect.sh) | A read-only health report: containers, resources, health checks, the certificate, Django's deployment checks, the scheduler, recent logs |
| [drill-database.sh](drill-database.sh) | Planned failure: stops the database, records what breaks, starts it again and times the recovery. About two minutes of errors on the live site |
| [drill-webhook.sh](drill-webhook.sh) | Planned failure: two Demo Family digests whose Discord post fails (refused, and unreachable). Checks the digest is still saved and the webhook URL is never logged. One-off containers, so the running app and `.env` are untouched; no downtime |
| [redact.py](redact.py) | Cleans server output before it's shared: visitors' IP addresses, webhook URLs, secret values. Both scripts pipe everything through it. Tested in [tests/](tests/) and in CI |
| [diagnosis/](diagnosis/) | The real output, from the production server |

## What the diagnosis found

From one health report and two drills on the production server, 2026-10-24 ([diagnosis/](diagnosis/README.md)):

- **Fixed:**
  - health checks every 3 seconds made most of the backend's log
  - container logs had no size limit
  - the build cache grew with every deploy
  - a `500` left no cause in the logs
- **Confirmed on the live site:**
  - with the database down, the page still loads but the API fails, and it recovers 5 seconds after the database is back
  - a failed Discord post keeps the digest and never logs the webhook URL
- **Known gaps, in the [runbook](runbook.md#known-gaps):**
  - nothing alerts on an outage
  - API errors are HTML
  - backups are by hand
  - production has no webhook set

## Running them

On the server, as `deploy`. Once they're on `main`, they're in the deployed copy:

```sh
/srv/stepboard/ops/collect.sh
```

From a branch, run them from a temporary second checkout. `deploy.sh` resets `/srv/stepboard` to `main`, so checking out a branch there would be undone by the next deploy, and could leave the server running code that isn't on `main`. A worktree in `/tmp` changes nothing the app uses:

```sh
cd /srv/stepboard
git fetch -q origin <branch>
git worktree add --detach /tmp/ops FETCH_HEAD
/tmp/ops/ops/collect.sh            # or drill-database.sh, drill-webhook.sh
git worktree remove /tmp/ops       # afterwards
```

The scripts always act on the deployed app in `/srv/stepboard`, wherever they're run from.

**What they never do:** read `.env`, or run `docker compose config`, which prints every setting, secrets included. Their output is safe to paste into an AI tool or commit (see [security/ai-policy.md](../security/ai-policy.md)). Still, glance at it first.

## Rehearsing locally

The drills run against the local stack too, which is how they were tested before they were run on production:

```sh
docker compose up -d --wait
APP_DIR=. COMPOSE_FILES="-f docker-compose.yml" BASE_URL=http://localhost:8080 PYTHON=python DOWN_FOR=30 bash ops/drill-database.sh
APP_DIR=. COMPOSE_FILES="-f docker-compose.yml" BASE_URL=http://localhost:8080 PYTHON=python bash ops/drill-webhook.sh
```
