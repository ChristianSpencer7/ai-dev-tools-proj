# Ops

Diagnosing the running app with Docker Compose: a health report, planned-failure drills, and what each showed. The server's setup and everyday commands are in [docs/deployment.md](../docs/deployment.md).

| File | What it is |
| --- | --- |
| [collect.sh](collect.sh) | A read-only health report: containers, resources, health checks, the certificate, Django's deployment checks, the scheduler, recent logs |
| [drill-database.sh](drill-database.sh) | Planned failure: stops the database, records what breaks, starts it again and times the recovery. About two minutes of errors on the live site |
| [redact.py](redact.py) | Cleans server output before it's shared: visitors' IP addresses, webhook URLs, secret values. Both scripts pipe everything through it. Tested in [tests/](tests/) and in CI |
| [diagnosis/](diagnosis/) | The real output, from the production server |

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
/tmp/ops/ops/collect.sh            # or /tmp/ops/ops/drill-database.sh
git worktree remove /tmp/ops       # afterwards
```

The scripts always act on the deployed app in `/srv/stepboard`, wherever they're run from.

**What they never do:** read `.env`, or run `docker compose config`, which prints every setting, secrets included. Their output is safe to paste into an AI tool or commit (see [security/ai-policy.md](../security/ai-policy.md)). Still, glance at it first.

## Rehearsing locally

The drill runs against the local stack too, which is how it was tested before it was run on production:

```sh
docker compose up -d --wait
APP_DIR=. COMPOSE_FILES="-f docker-compose.yml" BASE_URL=http://localhost:8080 PYTHON=python DOWN_FOR=30 bash ops/drill-database.sh
```
