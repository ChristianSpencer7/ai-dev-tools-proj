# Security findings

What the scanners found on 2026-10-24, and what was done about each finding: fixed, or accepted and why. The raw output is in [scans/](scans/) (before) and [scans/after-fixes/](scans/after-fixes/) (after); [scans/README.md](scans/README.md) says how each scan was run.

## Summary

| Scanner | What | Before | After | High or critical left |
| --- | --- | --- | --- | --- |
| Bandit | Python code | 7 low | 7 low, all accepted | None |
| pip-audit | Production backend image | 0 | 0 | None |
| pip-audit | Local backend environment | 1 (`certifi`) | 0 | None |
| pip-audit | MCP server environment | 0 | 0 | None |
| npm audit | What ships in the built site | 0 | 0 | None |
| npm audit | Frontend dev tools | 6 (2 critical, 1 high, 3 moderate) | 0 | None |
| gitleaks | All 73 commits, plus 5 merges | 0 | 0 | None |
| Trivy | Frontend image | 212 (2 critical, 58 high) | **0** | None |
| Trivy | Backend image, Python packages | 6 (in `pip`) | 0 | None |
| Trivy | Backend image, Debian packages | 164 (44 high, 0 critical) | 164 | **44 high, accepted:** no fix released yet; see [below](#accepted-debian-packages-in-the-backend-image) |

## Fixed

| Finding | Severity | Fix |
| --- | --- | --- |
| Frontend image: OpenSSL (including 2 critical), curl, libexpat, libpng, libxml2, musl, zlib and others, 212 in all | Critical, high | The image was built on `nginx:1.27-alpine` (Alpine 3.21), which no longer gets fixes. It now uses `nginx:1.30-alpine` (Alpine 3.24), and runs `apk upgrade` when the image is built, which picked up a brotli fix released after the base image was made. Trivy: 0 |
| Frontend dev tools: tinypool (prototype pollution leading to code execution), Vitest (mock registration code injection, path traversal), Vite and esbuild (the development server could be read by any website) | Critical, high, moderate | Vite 5 → 7.3.7, Vitest 2 → 4.1.12, `@vitejs/plugin-react` 4 → 5.2.0, the smallest upgrade that fixes all six. Vite 8 and Vitest 5 would also work, but are bigger jumps for no extra fixes. These tools never reach the built site, but they run on developers' machines and in CI. The 6 frontend tests and the build pass |
| Node 20, used to build the frontend and in CI, reached end of life in April 2026 | n/a | Node 24 LTS in `frontend/Dockerfile` and CI. `package.json` now states the Node versions Vite 7 needs (`^20.19.0 \|\| >=22.12.0`) |
| Backend image: `pip` 25.0.1 had 6 known issues (malicious wheels and indexes, path traversal) | Medium, low | First tried upgrading pip, which brought in **new** findings: 4 high in the libraries pip bundles (`urllib3`, `msgpack`, `setuptools`). The app never uses pip at runtime, so the image now **removes pip** once the app is installed. Trivy: 0 Python findings |
| Local backend environment: `certifi` 2026.7.22 trusted a root certificate whose intermediates' keys were compromised | Not rated (PYSEC) | Upgraded to 2026.10.23 (`pip install -U certifi`). The Docker image already had the fixed version, because it installs fresh on every build. pip itself was also upgraded in both local environments |

After the fixes, the full stack started from the new images. The site and `/api/health` answered through nginx, the API answered, and the backend reported healthy.

## Accepted

### Accepted: Debian packages in the backend image

44 high, 58 medium, 61 low and 1 unknown finding, in packages that come with the `python:3.12-slim` base image (Debian 13.7). **Debian hasn't released fixes for any of them** (Trivy's "affected" or "fix deferred"), so a rebuild can't remove them yet. The 44 high findings are 8 distinct CVEs, repeated across packages built from the same source:

| CVE | Package | Why it doesn't apply here |
| --- | --- | --- |
| CVE-2026-76642, -78408, -78409, -78410 | util-linux (`mount`, `nsenter` and their libraries) | Attacks on mount helpers and `nsenter`, which need privileges to be useful. The app runs as an unprivileged user (uid 1000) in a container with Docker's default capabilities, and never runs `mount` or `nsenter` |
| CVE-2026-16742 | systemd libraries | A privilege escalation in `systemd-homed`, which doesn't run in the container. Only the libraries are present |
| CVE-2026-54369 | libacl | Symlink traversal by a local user who can already run programs |
| CVE-2025-69720 | ncurses | Buffer overflow in terminal handling. The app has no terminal; gunicorn writes logs to stdout |
| CVE-2026-9538 | perl-base (Archive::Tar) | Denial of service on a crafted tar file. Nothing in the app runs Perl or opens tar files |

Each one needs an attacker who can already run commands in the container, or a program the app never uses. **When to revisit:** every rebuild pulls the latest `python:3.12-slim`, so fixes arrive as Debian releases them; the Trivy step in CI (step 5) reports the count on each run.

### Accepted: no authentication

The PR audit found that the API has no logins: anyone who can reach it can read any family's boards and log steps for any member. The invite code only controls joining. Accepted for now, by the developer's decision, with the live site holding only the Demo Family. See [pr-audit.md](pr-audit.md#2-no-authentication-high-by-design-accepted-for-now) for the options and the planned fix.

### Accepted: Bandit's low findings

| Finding | Where | Why it's accepted |
| --- | --- | --- |
| B404, B603: `subprocess` used (×4) | `agent-hooks/contract_check.py:11,62`, `agent-hooks/guard_files.py:19,63` | The hooks run fixed commands (`git cat-file`, the backend's `pytest`) as a list, with no shell, so nothing in the input can become a command. The only value from outside is a file path, passed as one argument |
| B607: process started with a partial path | `agent-hooks/guard_files.py:63` | It runs `git` from the `PATH`, on the developer's own machine, with the same trust as Claude Code running the hook at all |
| B311: `random` isn't suitable for security | `backend/leaderboard/seed.py:38` | It makes up demo step counts, with a fixed seed so they're the same every time. Invite codes, the one value that must be unguessable, come from `secrets` (`invites.py`) |
| B105: possible hardcoded password | `backend/stepboard/settings.py:34` | The fallback `SECRET_KEY` is only used when `DJANGO_DEBUG` is on and no key is set. With debug off, a missing key stops the app (`ImproperlyConfigured`), and production sets its own key, from the server's environment file |

## Clean results

- **gitleaks:** no secrets in any commit. To check the scanner could find one, a fake GitHub token planted in a scratch folder was reported first. The environment files that hold real secrets are gitignored; the history shows only the `.env.example` template was ever committed.
- **pip-audit**, production image and MCP server: no known vulnerabilities.
- **npm audit**, what ships: React and React DOM have no known vulnerabilities.
