# Security

The security work on the family step leaderboard: what was scanned, what was found and done about it, a review of a real pull request, and the risks that come with AI agents.

| File | What's in it |
| --- | --- |
| [findings.md](findings.md) | **Start here.** Every scanner finding, fixed or accepted, and why. Before and after counts |
| [scans/](scans/) | The scanners' raw output: before the fixes, and [after](scans/after-fixes/). [scans/README.md](scans/README.md) has the versions, how to rerun them, and what fails CI |
| [pr-audit.md](pr-audit.md) | An AI-assisted security review of pull request #4 (the MCP server), and what changed because of it |
| [agent-extension-pack.md](agent-extension-pack.md) | The risks of the agent extension pack: the MCP server's reach, prompt injection, secrets, configuration that runs code |

## Where things stand

- **No high or critical finding is open without an explanation.**
  - The frontend image went from 212 findings (2 critical) to 0, and the frontend's dev tools from 6 findings to 0.
  - The backend image's remaining high findings are Debian packages with no fix released yet. They're explained one by one in [findings.md](findings.md#accepted-debian-packages-in-the-backend-image).
- **The PR audit found a real leak:** anyone could read every family's invite code. It's fixed, along with prompt injection through member names.
- **One known risk is accepted for now:** the API has no logins, so anyone can read and change any family's boards. The live site holds only the Demo Family until the invite code becomes the family's password ([pr-audit.md](pr-audit.md#2-no-authentication-high-by-design-accepted-for-now)).
- **The scanners run in CI** on every push and pull request, and deploying waits for them.

## Already in place before task 15

- **HTTPS everywhere in production:** HSTS and secure cookies; Django's deployment checks run in CI.
- **Secrets only in the server's `.env`:**
  - The deploy SSH key can only run `scripts/deploy.sh`.
  - The workflow's token is read-only.
- **The Discord webhook URL is never logged**, and tests can't reach real Discord.
- **The app runs as an unprivileged user** in its container.
