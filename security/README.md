# Security

Planned for day 7: security scan results, the PR audit, and the AI tool and data policy.

## Noted so far, to review in task 15

- **The MCP server's `log_steps` writes data, and the API has no logins.** It defaults to the local backend and one family; see [mcp-server/README.md](../mcp-server/README.md#security).
- **AI tools act on what the assistant reads**, so injected instructions could try to log steps. The destructive-tool permission prompt is the check.
- **Project `.mcp.json` servers loaded without a prompt** in the Claude Code VS Code extension.
- **Already in place:** the Discord webhook URL is never logged (`httpx` logging kept at WARNING) and tests can't reach real Discord; HTTPS, HSTS and secure cookies in production; secrets only in the server's `.env`; a deploy-only SSH key restricted to `scripts/deploy.sh`.
