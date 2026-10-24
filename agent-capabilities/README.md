# Agent capabilities

Reusable workflows for AI agents working on this project. Claude Code only finds skills in `.claude/skills/`, so that's where the working file is; this folder explains it.

## `add-api-endpoint`

**File:** [`.claude/skills/add-api-endpoint/SKILL.md`](../.claude/skills/add-api-endpoint/SKILL.md)

Adds or changes an endpoint of the API, contract first:

1. `openapi.yaml`
2. the model and a new migration, if data changes
3. `serializers.py`, `views.py`, `urls.py`, and `frontend/src/api.js`
4. tests, including the contract response tests
5. the checks
6. the MCP server, `product-spec.md`, the AI workflow log, and a pull request

It encodes the "contract first", "migrations" and "tests with changes" rules from [AGENTS.md](../AGENTS.md) as a checklist an agent follows in order.

**Use it** by name, `/add-api-endpoint GET /families/{family_id}/streaks, ...`, or by asking for any API change: the skill's description tells Claude Code when it applies. It works alongside the [contract check hook](../agent-hooks/README.md), which runs the contract tests after each API edit.

More examples and the other pieces: [docs/agent-extension-pack.md](../docs/agent-extension-pack.md).
