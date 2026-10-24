# Diagnosis: 2026-10-24

Real output from the production server, collected with Docker Compose by [ops/collect.sh](../collect.sh) and [ops/drill-database.sh](../drill-database.sh). The developer ran them on the server and pasted the output back; it was already redacted by [ops/redact.py](../redact.py).

| File | What |
| --- | --- |
| [2026-10-24-production-report.txt](2026-10-24-production-report.txt) | The health report, 09:14 UTC |
| [2026-10-24-production-drill-database.txt](2026-10-24-production-drill-database.txt) | The database drill on production, straight after |
| [2026-10-24-production-drill-webhook.txt](2026-10-24-production-drill-webhook.txt) | The bad-webhook drill on production, 17:34 UTC |
| [2026-10-24-rehearsal-local-1.txt](2026-10-24-rehearsal-local-1.txt), [-2](2026-10-24-rehearsal-local-2.txt), [-webhook](2026-10-24-rehearsal-local-webhook.txt) | The drills rehearsed on the local stack first (Docker Desktop on Windows) |

## The healthy server

| Check | Result |
| --- | --- |
| Containers | All 5 running; backend and database healthy |
| `/health` (runs a database query), inside and through Caddy | `200` in 0.1–0.2 s |
| HTTP | `308` redirect to HTTPS |
| Certificate | Let's Encrypt, valid until 21 January 2027; Caddy is tracking its renewal |
| Django's deployment checks | No issues |
| Scheduler | Weekly digests Monday 26 October 08:00, monthly Sunday 1 November 08:00 (Eastern) |
| Memory | 337 MiB available of 961 MiB; 134 MiB of swap in use. Tight, but steady |
| Disk | 29% of 24 GB |

**Found:**

1. **Health checks flood the backend's log.** Docker checks the backend every 3 seconds, and each check is an access-log line. 22 of the backend's last 25 lines were health checks.
2. **Container logs have no size limit.** Docker's default `json-file` driver keeps everything, about 25,000 health-check lines a day for the backend alone.
3. **The build cache grows with every deploy.** It holds 1.1 GB, all of it reclaimable: `deploy.sh` removes old images but not the build cache.
4. **The first report showed a redaction gap.** IPv4 addresses with a port (Caddy's `"remote":"1.2.3.4:33955"`) weren't replaced. They were Let's Encrypt's validation servers, not visitors, but it was fixed (in `redact.py`, with tests) before the drill.

## The database drill

The database was stopped for 81 seconds on the live site, which holds only the Demo Family.

| | What happened |
| --- | --- |
| API (`/api/...`) | `500` from the first second, every time |
| Each failing request | 0.05–0.13 s: it failed fast |
| The page shell (`/`) | `200` throughout: nginx serves it without the backend, so visitors get the page with no data |
| What a visitor gets | An **HTML** "Server Error (500)" page, not the API's JSON `{"detail": ...}` |
| Backend logs | 16 `500`s and 37 failed health checks, and **not one line saying why** |
| Backend container | Marked **unhealthy after ~75 s**, and then **nothing happened**: no restart (which wouldn't help), and no alert |
| Recovery | The site answered **5 s** after the database started; one more failure while Postgres was still starting, then all fine. No restart needed |

**Found:**

5. **Errors leave no trace.** With `DEBUG` off, Django sends unhandled exceptions only to email (`mail_admins`), and none is configured. So the logs show `500`, but not `OperationalError: could not connect to server`. Anyone diagnosing this without knowing the database was stopped would have nothing to go on.
6. **Nothing notices an outage.** "Unhealthy" is visible in `docker compose ps` and nowhere else. The only automatic check of the live site is the one after each deploy.
7. **API errors aren't JSON.** The frontend's `api.js` expects `{"detail": ...}`; a `500` gives it HTML.

**Predicted but didn't happen:** that each worker would fail one more request on a dead connection after the restart (`conn_max_age=600`). Django drops a connection after an error, so none was reused.

**The rehearsal and production differed.** Locally, each failing request took **7.5 s** and "unhealthy" took about 2 minutes. On the Linux server, the database's absence was noticed at once. The slow failures were Docker Desktop's name lookup for a stopped container, not the app. The rehearsal tested the script; only production showed how the app behaves.

## The bad-webhook drill

Two Demo Family digests were sent from one-off containers with a broken webhook. The running backend kept its own setting, and the site stayed up.

| Case | Logged | The digest |
| --- | --- | --- |
| Discord refuses the webhook (a made-up token) | `WARNING leaderboard.discord: Discord webhook post failed: HTTPStatusError (HTTP 404)` | Saved, shown on the Messages page, `discord_status=failed` |
| The webhook's host can't be reached (`.invalid`) | `WARNING leaderboard.discord: Discord webhook post failed: ConnectError` | Saved, shown, `discord_status=failed` |

- **"A failed post must never lose a digest" holds** on the real deployment, for both kinds of failure.
- **"The webhook URL must never be logged" holds.** A marker in both fake URLs appeared in 0 lines of the drill's output and of every service's logs, counted before redaction, so `redact.py` couldn't have hidden a leak.
- **Production has no webhook set.** The running backend reports "not set", so real digests go only to the in-app Messages page. That's allowed by design ("Discord stays optional"), but it's worth knowing: nobody is told a digest is ready.
