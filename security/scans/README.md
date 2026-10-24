# Scan outputs

Raw output of each scanner, run on 2026-10-24 against branch `security-scans` (from `main` at `d88e0f0`). What each finding means, and what was done about it, is in [findings.md](../findings.md).

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

## Running them again

From the repository root, with Docker running. The scanners run in their own environment or container, not the project's.

```sh
# Bandit and pip-audit, in a separate virtual environment
python -m venv /tmp/sectools && /tmp/sectools/bin/pip install bandit pip-audit
/tmp/sectools/bin/bandit -r backend/stepboard backend/leaderboard mcp-server/stepboard_mcp agent-hooks \
    -x agent-hooks/tests,backend/leaderboard/migrations
docker compose build backend frontend
docker run --rm --entrypoint pip stepboard-backend freeze --exclude stepboard > /tmp/image.txt
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
