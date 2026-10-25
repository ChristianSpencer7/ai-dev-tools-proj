# Runbook

What to do when something's wrong with the live site, <https://159-89-228-242.sslip.io>. Each section starts from a symptom: what to run, what the output means, and the fix. It's built from real runs on the production server ([ops/diagnosis/](diagnosis/README.md)).

Everything runs on the server, as `deploy`, in `/srv/stepboard`. `dc` is `docker compose -f docker-compose.yml -f docker-compose.prod.yml` (set up as an alias in [docs/deployment.md](../docs/deployment.md)). Setting up a server, deploying, backups and secrets are covered there too.

## Start here

```sh
cd /srv/stepboard
ops/collect.sh          # the whole picture, read-only, safe to share (see "Sharing output" below)
```

Or the three quickest checks:

```sh
dc ps                                                      # all 5 running? backend and db "(healthy)"?
curl -s -o /dev/null -w '%{http_code}\n' https://159-89-228-242.sslip.io/api/health   # 200 = backend and database OK
dc logs --since 15m backend | grep -E 'ERROR |Error: ' | sed -E 's/^[^|]*[|] +//; s/^[0-9-]+ [0-9:,]+ //' | sort | uniq -c | sort -rn | head   # what's failing, by kind
```

| Symptom | Go to |
| --- | --- |
| The page loads, but the boards are empty or show an error | [The API returns 500](#the-api-returns-500) |
| `dc ps` shows the backend as `(unhealthy)` | [The backend is unhealthy](#the-backend-is-unhealthy) |
| Nothing loads at all, or the browser warns about the certificate | [Nothing loads](#nothing-loads) |
| A Monday or monthly digest didn't arrive | [A digest didn't arrive](#a-digest-didnt-arrive) |
| Disk or memory is running low | [Disk and memory](#disk-and-memory) |

## The API returns 500

**What it looks like:** the page itself loads (`/` answers `200`, since nginx serves it without the backend), but every `/api/...` request answers `500` with an HTML "Server Error (500)" page. That's what stopping the database looked like in the [drill](diagnosis/2026-10-24-production-drill-database.txt).

**Find the cause.** Every `500` logs its cause and traceback (since `ops-and-ai-policy`; before that, the logs showed only "500"):

```sh
dc logs --since 15m backend | grep -E 'ERROR |Error: ' | sed -E 's/^[^|]*[|] +//; s/^[0-9-]+ [0-9:,]+ //' | sort | uniq -c | sort -rn | head
```

The `sed` drops each line's container name and timestamp, so the same error is counted as one kind. On the local stack, after a database outage, it gives:

```text
      9 django.db.utils.OperationalError: failed to resolve host 'db': [Errno -3] Temporary failure in name resolution
      7 ERROR django.request: Internal Server Error: /health
      5 ERROR django.request: Internal Server Error: /families
      3 django.db.utils.OperationalError: terminating connection due to administrator command
```

| The error says | It means | Fix |
| --- | --- | --- |
| `OperationalError: failed to resolve host 'db'` | The database container isn't running | `dc ps db`; then `dc up -d --wait db`. In the drill, the site answered again **5 seconds** after the database started, without restarting anything else |
| `OperationalError: connection ... refused` | The database is starting, or restarting | Wait half a minute; if it persists, `dc logs --tail 50 db` |
| `OperationalError: terminating connection due to administrator command` | The database was stopped or restarted while connected. Seen once per open connection | Nothing, if it stops; the next request reconnects |
| `OperationalError: ... password authentication failed` | The database password in `.env` changed | See "Changing a secret" in [docs/deployment.md](../docs/deployment.md#changing-a-secret) |
| Anything else (`KeyError`, `TypeError`, ...) with a traceback in `leaderboard/` | A bug in the code, most likely the latest deploy | Look at the traceback (`dc logs --since 15m backend`). Then [undo the deploy](../docs/deployment.md#undoing-a-bad-deploy): revert on GitHub, or by hand in an emergency |

## The backend is unhealthy

**What it means:** Docker calls `/health` inside the backend, which runs a database query. It checks every 3 seconds while starting, then every 30 seconds, and marks it `(unhealthy)` after 3 failures in a row, about 90 seconds.

**What it doesn't do:** restart anything, or tell anyone. In the drill, the backend sat `(unhealthy)` until the database came back, then turned healthy again by itself. A restart wouldn't have helped: the problem was the database.

**It lags behind.** It's checked every 30 seconds, so it can say `(unhealthy)` for up to 30 seconds after the site works again. In the second production drill the site answered 1 second after the database started, while `dc ps` still said `(unhealthy)`. The site's own answer (`curl` on `/api/health`) is the up-to-date one.

1. `dc ps db`: if the database isn't running and healthy, fix that first ([above](#the-api-returns-500)).
2. Find what `/health` is failing on: `dc exec backend python -c "import urllib.request as u; print(u.urlopen('http://localhost:8000/health', timeout=5).read())"`, and the error summary above.
3. If the database is fine and the backend is still failing: `dc restart backend`, then `dc ps` until it's `(healthy)`, usually within 15 seconds.

## Nothing loads

The backend and the page are behind Caddy, so if nothing at all answers, start with Caddy. The steps for this are in [docs/deployment.md, Troubleshooting](../docs/deployment.md#troubleshooting): `dc ps` (five services, Caddy with ports 80 and 443), then `dc logs caddy --tail 30`.

**The certificate:** Caddy gets and renews it on its own, about 30 days before it expires. To see its dates:

```sh
echo | openssl s_client -connect localhost:443 -servername 159-89-228-242.sslip.io 2>/dev/null | openssl x509 -noout -dates
```

On 2026-10-24 it was valid until 21 January 2027. If it's within two weeks of expiring, look for `tls` errors in `dc logs caddy`.

## A digest didn't arrive

Digests are saved first and posted to Discord second, so first find out whether it was made at all:

```sh
dc exec -T backend python manage.py shell -v 0 -c "
from leaderboard.models import Message
for m in Message.objects.select_related('family').order_by('-created_at')[:8]:
    print(m.created_at.strftime('%Y-%m-%d %H:%M'), m.family.name, m.kind, m.discord_status)"
```

This asks the database directly, because the API needs each family's invite code, which a server operator may not have. Don't paste this output into an AI tool: it names real families.

| What you see | It means | Fix |
| --- | --- | --- |
| No digest for that day | The scheduler didn't run it | `dc ps scheduler`; when it runs next: `dc logs scheduler \| grep -E '(weekly\|monthly) +[A-Z]'`. To send it now (safe to repeat; families that have it are skipped): `dc exec backend python manage.py send_digests weekly` (or `monthly`) |
| `discord_status: not_configured` | No webhook is set. **This is production's state as of 2026-10-24**: digests appear only on the Messages page | If they should go to Discord, add `DISCORD_WEBHOOK_URL` to `.env` yourself, then `./scripts/deploy.sh` |
| `discord_status: failed` | It was saved, but the post failed | Scheduled digests: `dc logs --since 2d scheduler \| grep 'Discord webhook post failed'`; see below. A digest sent by hand prints the same line in your terminal |

The log line names the error type, never the URL ([drill](diagnosis/2026-10-24-production-drill-webhook.txt)):

| Logged | It means |
| --- | --- |
| `HTTPStatusError (HTTP 404)` or `(HTTP 401)` | The webhook was deleted, or the URL is wrong. Make a new one in Discord, put it in `.env`, and deploy |
| `HTTPStatusError (HTTP 429)` | Discord is rate-limiting. There's no retry; the next digest should post normally |
| `HTTPStatusError (HTTP 5xx)` | A problem on Discord's side |
| `ConnectError` or `ConnectTimeout` | The server couldn't reach Discord: a network or DNS problem |

A failed digest isn't lost: it's on the Messages page. There's no automatic retry, so to post it again, send it by hand; `send_digests` skips families that already have it, so for this one family, delete the failed message in the admin (`/admin/`) first.

## Disk and memory

```sh
df -h /              # 29% of 24 GB on 2026-10-24
docker system df     # images, containers, volumes, build cache
free -h              # 961 MiB in all; about 340 MiB available is normal
```

- **Logs** are capped at 3 files of 10 MB per service, so at most about 150 MB in all.
- **Build cache** older than a week is cleared on every deploy. To clear all of it now: `docker builder prune -f` (the next build is slower).
- **Old images:** `docker image prune -f`, also done on every deploy.
- **Never** run `docker system prune --volumes` or `docker volume prune`. The database lives in the `pgdata` volume, and those commands would delete it. Back it up first ([docs/deployment.md, Backups](../docs/deployment.md#backups)).
- **Memory:** the server has 1 GB and 2 GB of swap. If `free -h` shows under 100 MiB available and swap growing, `docker stats --no-stream` shows which container is using it; `dc restart <service>` is a stopgap, and a bigger Droplet the fix.

## Drills

Practise these before you need them, and repeat them after changes to the Compose files, the settings or the deployment. They're in [ops/](README.md), and were rehearsed on the local stack before they were run on production.

| Drill | What it shows | Cost |
| --- | --- | --- |
| [drill-database.sh](drill-database.sh) | What a database outage looks like from outside and in the logs, and how long recovery takes | About 3 minutes of errors on the live site. The database is started again however the drill ends, including Ctrl+C or a dropped SSH session; if in doubt, `dc ps db` |
| [drill-webhook.sh](drill-webhook.sh) | That a failed Discord post keeps the digest and never logs the URL | None: two failed digests on the Demo Family's Messages page |

## Known gaps

- **Nothing notices an outage.** `(unhealthy)` is only visible in `dc ps`. A free external uptime monitor, checking `https://159-89-228-242.sslip.io/api/health` every few minutes and emailing on failure, would close this; it needs an account, so it's for the site's owner to set up.
- **API errors are HTML, not JSON.** A `500` from `/api/...` is Django's HTML error page, while the frontend expects `{"detail": ...}`. It shows as a generic error in the app.
- **Backups are by hand.** Nothing makes them automatically; the commands are in [docs/deployment.md](../docs/deployment.md#backups).
- **No webhook in production**, so nobody is notified of a new digest (see above).

## Sharing output

`ops/collect.sh` and the drills pass everything through [ops/redact.py](redact.py), so their output can be pasted into an AI assistant or committed. **Raw `dc logs` aren't redacted**: the frontend's access log has visitors' IP addresses. Pipe them through it first, `dc logs --tail 100 frontend | python3 ops/redact.py`, and never paste `.env` or `docker compose config` output anywhere. The rules are in [security/ai-policy.md](../security/ai-policy.md).
