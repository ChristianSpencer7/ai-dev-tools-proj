"""The MCP server: tools an AI assistant can call to read the boards and log steps.

Run it over stdio, as Claude Code does (see .mcp.json at the repository root): `python -m stepboard_mcp`.
"""

from mcp.server.mcpserver import MCPServer

from stepboard_mcp.config import Config

INSTRUCTIONS = """\
Tools for one family's step leaderboard. Weeks run Monday to Sunday and days end at midnight Eastern time.
Logging steps for a day that already has a total replaces it; it doesn't add to it.
"""


def build_server(config: Config) -> MCPServer:
    server = MCPServer(
        name="stepboard",
        title="Family Step Leaderboard",
        instructions=INSTRUCTIONS + f"Family: {config.family}. App: {config.api_url}.",
    )
    return server


def main() -> None:
    build_server(Config.from_env()).run()  # stdio by default
