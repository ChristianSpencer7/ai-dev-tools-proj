# Custom agent

A specialist agent for this project. Claude Code only finds subagents in `.claude/agents/`, so that's where the working file is; this folder explains it.

## `leaderboard-rules-reviewer`

**File:** [`.claude/agents/leaderboard-rules-reviewer.md`](../.claude/agents/leaderboard-rules-reviewer.md)

A read-only reviewer. It checks a branch's changes, committed and uncommitted, against 12 rules from [product-spec.md](../product-spec.md) and [AGENTS.md](../AGENTS.md):

- Eastern days
- same-day replace
- all-or-nothing imports
- shared ranks and a pure `ranking.py`
- the boards' date ranges
- validation and error codes
- contract first
- optional Discord
- digests and the scheduler
- invite codes
- configuration and secrets
- tests

It runs the related tests and reports findings with `file:line`, the rules it checked and found fine, and the test results.

**Read-only, enforced twice:**

1. Its tool list is `Read, Grep, Glob, Bash`, with no edit tools.
2. Its own hook, [`agent-hooks/read_only_commands.py`](../agent-hooks/read_only_commands.py), allows only reading commands and tests in `Bash`. It's registered in the subagent's front matter, so it applies only while the reviewer runs.

A reviewer that could edit would be marking its own work.

**Use it** before opening a pull request: *"Use the leaderboard-rules-reviewer to review this branch"*, or `@agent-leaderboard-rules-reviewer`. `/agents` shows it's loaded.

The tests in [`agent-hooks/tests/test_read_only_commands.py`](../agent-hooks/tests/test_read_only_commands.py) check its hook and its definition: no edit tools, the hook registered, and every file it points to exists. More in [docs/agent-extension-pack.md](../docs/agent-extension-pack.md).
