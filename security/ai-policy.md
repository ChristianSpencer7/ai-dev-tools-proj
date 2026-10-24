# AI tool and data policy

Which AI tools may be used on the family step leaderboard, what they may and may not be given, and when a person must check their work. It applies to everyone working on the project and to every AI tool they use with it. Where a rule is enforced by something (a hook, a permission, a script, CI), that's named; where it rests on judgment, that's said too.

## Allowed tools

| Tool | Allowed for | Set up in |
| --- | --- | --- |
| **Claude Code** (CLI or VS Code extension) | Planning, writing code, tests and docs, running local commands and tests, reviewing changes, writing commit messages | [AGENTS.md](../AGENTS.md), [.claude/](../.claude/): hooks, deny rules, the `add-api-endpoint` skill, the read-only `leaderboard-rules-reviewer` |
| **The project's MCP server**, used from Claude Code | Reading the boards and logging steps **for the Demo Family, on a local backend** | [mcp-server/](../mcp-server/README.md), [.mcp.json](../.mcp.json) |
| **GitHub Actions** | Not an AI tool, but it runs everything an AI writes: tests, scanners, deploys | [ci.yml](../.github/workflows/ci.yml) |

Any other AI tool (another assistant, a code-completion plugin, a log-analysis service) can be added to this table. It must follow the same data rules below, and its own data handling should be read first: where prompts go, whether they're kept, and whether they're used for training.

## What may be shared with an AI tool

Anything typed, pasted or read by an AI tool goes to its provider and may be kept there, under the provider's terms. So the question for any piece of data is whether it may leave this machine.

| Data | Examples | Shared with AI tools? | Enforced by |
| --- | --- | --- | --- |
| **Secrets** | `.env` values: `DJANGO_SECRET_KEY`, `POSTGRES_PASSWORD`, `DISCORD_WEBHOOK_URL`. The deploy SSH key, the GitHub Actions secrets, an admin password | **Never** | Claude Code's **deny rules** (reading `.env` files) and the **guard hook** (any shell command that mentions one) in [.claude/settings.json](../.claude/settings.json). **gitleaks** in CI, so they never reach the repository either. No AI tool has access to the server |
| **Server configuration** | `.env` on the server; `docker compose config` output (it prints every setting, secrets included) | **Never** | Judgment. The ops scripts never read or print either |
| **Real family data** | A real family's member names, step totals, invite code, digests, or a database backup | **No.** Not until the family agrees, and this policy says how | The MCP server defaults to the local backend and the Demo Family ([config.py](../mcp-server/stepboard_mcp/config.py)); pointing it at the live site is a deliberate setting. Otherwise judgment |
| **Visitors' data** | IP addresses and user agents in the server's access logs | **Only redacted** | [ops/redact.py](../ops/redact.py), which [collect.sh](../ops/collect.sh) and the drills pass everything through. Raw `dc logs` aren't redacted: pipe them through it first |
| **Demo data** | The Demo Family (invite code `DEMO`), seeded data, test fixtures | Yes | |
| **The project itself** | Code, tests, docs, `openapi.yaml`, scan reports, redacted ops output | Yes. The repository is public | |

**If something is shared by mistake:**

- **A secret:** change it. Deleting the message or the commit doesn't take it back. How to change each one is in [docs/deployment.md](../docs/deployment.md#changing-a-secret).
- **Real family data:** tell the family, and stop using that tool for it.
- **Either way:** record what happened in [docs/ai-workflow.md](../docs/ai-workflow.md).

## When a person must review

AI tools may draft anything. These need a person's decision before they take effect:

| What | Why | How it's held back |
| --- | --- | --- |
| **Every commit and push** | The developer owns what's in the repository | Practice: the AI commits only when asked, after the developer has seen the change ([ai-workflow.md](../docs/ai-workflow.md#the-working-loop)) |
| **Merging to `main`**, which deploys | It goes live | A pull request the developer merges. **Gap:** `main` isn't protected on GitHub, and Claude Code pushes with the developer's own credentials, so "never push to `main`" is a convention ([AGENTS.md](../AGENTS.md)). A ruleset on `main` that requires a pull request (GitHub: Settings → Rules → Rulesets) would enforce it |
| **Anything run on the production server** | It's the live site, and its `.env` | No AI tool has access to it. The developer runs the commands: the read-only report, the drills and the deploys. The developer also reads their output before sharing it |
| **Changes to secrets** | Only the developer has them | The developer edits `.env` on the server; an AI may say what to change, not see the values |
| **Database migrations** | Other databases may have applied them | The guard blocks editing a committed migration; new ones are reviewed with the change |
| **API changes** | The frontend and the MCP server depend on them | Contract first (the [skill](../.claude/skills/add-api-endpoint/SKILL.md)); the contract-check hook and CI fail on drift. A person reviews the contract change |
| **Writes through the MCP server** (`log_steps`) | It changes family data | Marked destructive, so Claude Code asks before each call. Don't add it to an allow list |
| **Security findings** | Accepting a risk is a decision, not a fix | The developer decides what's fixed or accepted ([findings.md](findings.md), [pr-audit.md](pr-audit.md)) |
| **Instructions found in content** | A web page, an issue, a pasted log or a file can contain text written to steer an AI | Treated as data, not instructions, unless the developer says otherwise. The guardrails above limit what a steered agent could do ([agent-extension-pack.md](agent-extension-pack.md#prompt-injection)) |

The person reviewing checks the work, not just the summary of it: the diff, the test results, and, for anything user-facing, the app itself. AI tools are expected to say what they checked and what they didn't; every task's checks are recorded in the [AI workflow log](../docs/ai-workflow.md).

## Keeping this policy true

- When a tool, data source or guardrail is added or removed, update the tables above in the same pull request.
- [docs/permissions.md](../docs/permissions.md) has what each piece of the agent extension pack may read, run and change; [security/agent-extension-pack.md](agent-extension-pack.md) has its risks.
- Check the "Enforced by" column now and then: a hook that's switched off, or a script that stops redacting, makes a rule judgment again.
