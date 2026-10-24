# Scan outputs

Raw output of each scanner, run on 2026-10-24 against branch `security-scans` (from `main` at `d88e0f0`). What each finding means, and what was done about it, is in [findings.md](../findings.md).

[after-fixes/](after-fixes/) holds the same scans rerun after the fixes, for the scans whose results changed: pip-audit on the backend image and local environment, npm audit, and Trivy on both images.

| File | Scanner | What was scanned |
| --- | --- | --- |
| `bandit.txt` | Bandit 1.9.4 | Python code: `backend/stepboard`, `backend/leaderboard` (not migrations), `mcp-server/stepboard_mcp`, `agent-hooks` (not tests) |
| `pip-audit-backend-image.txt` | pip-audit 2.10.1 | The Python packages in the backend Docker image, which is what production runs (`packages-backend-image.txt`) |
| `pip-audit-backend-dev.txt` | pip-audit 2.10.1 | The local backend `.venv`, with the dev tools (`packages-backend-dev.txt`) |
| `pip-audit-mcp.txt` | pip-audit 2.10.1 | The MCP server's `.venv` (`packages-mcp.txt`) |
| `npm-audit.txt` | npm audit (npm 10) | `frontend/package-lock.json`, everything |
| `npm-audit-production.txt` | npm audit `--omit=dev` | Only what ships in the built site |
| `gitleaks.txt`, `gitleaks.json` | gitleaks 8.30.1 | Every commit in the history (73, plus 5 merges), secrets redacted |
| `trivy-stepboard-backend.txt` | Trivy 0.76.1 | The backend image: Debian packages and Python packages |
| `trivy-ai-dev-tools-proj-frontend.txt` | Trivy 0.76.1 | The frontend image: Alpine packages (nginx base) |

## In CI

Every push and pull request runs the same scanners ([ci.yml](../../.github/workflows/ci.yml)): Bandit, pip-audit, npm audit and gitleaks in the **Security scans** job, and Trivy in **Docker images**, after the images are built. Each prints its whole report. The build fails on:

| Scanner | Fails on |
| --- | --- |
| Bandit | High severity |
| pip-audit | Any known vulnerability (its sources give no severity), in the backend's and MCP server's dependencies, dev tools included |
| npm audit | High or critical |
| gitleaks | Any secret, in any commit |
| Trivy | High or critical **with a released fix**. Findings with no fix yet, like the backend's Debian packages, are reported but don't fail, since a rebuild can't remove them ([findings.md](../findings.md#accepted-debian-packages-in-the-backend-image)) |

Deploying waits for both jobs. Each gate was checked both ways before it was added: it passes on the current code, and fails on a known problem (Bandit: a planted `shell=True`; npm audit: the lock file from before the fixes; Trivy: `nginx:1.27-alpine`; gitleaks: a planted token).

## Running them again

From the repository root, with Docker running. The scanners run in their own environment or container, not the project's.

```sh
# Bandit and pip-audit, in a separate virtual environment
python -m venv /tmp/sectools && /tmp/sectools/bin/pip install bandit pip-audit
/tmp/sectools/bin/bandit -r backend/stepboard backend/leaderboard mcp-server/stepboard_mcp agent-hooks \
    -x agent-hooks/tests,backend/leaderboard/migrations
docker compose build backend frontend
# The image has no pip since the fixes, so list its packages with Python itself
docker run --rm --entrypoint python stepboard-backend -c \
    "import importlib.metadata as m; print('\n'.join(sorted(f'{d.name}=={d.version}' for d in m.distributions() if d.name != 'stepboard')))" > /tmp/image.txt
/tmp/sectools/bin/pip-audit -r /tmp/image.txt --no-deps --disable-pip --desc

# npm audit
(cd frontend && npm audit && npm audit --omit=dev)

# gitleaks, over the whole history
docker run --rm -v "$PWD:/repo" -e GIT_CONFIG_COUNT=1 -e GIT_CONFIG_KEY_0=safe.directory -e GIT_CONFIG_VALUE_0='*' \
    zricethezav/gitleaks:latest git /repo --redact -v

# Trivy, on each image
docker run --rm -v /var/run/docker.sock:/var/run/docker.sock aquasec/trivy:latest image --scanners vuln stepboard-backend
docker run --rm -v /var/run/docker.sock:/var/run/docker.sock aquasec/trivy:latest image --scanners vuln ai-dev-tools-proj-frontend
```

To check gitleaks can actually find something, a fake GitHub token planted in a scratch folder was reported (`leaks found: 1`) before the history scan was trusted.
