"""The MCP server: tools an AI assistant can call to read the boards and log steps.

Run it over stdio, as Claude Code does (see .mcp.json at the repository root): `python -m stepboard_mcp`.
"""

import logging
from datetime import date, datetime, timedelta
from typing import Annotated, Literal
from zoneinfo import ZoneInfo

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import ToolAnnotations
from pydantic import Field

from stepboard_mcp.api import ApiError, StepboardApi
from stepboard_mcp.config import Config

EASTERN = ZoneInfo("America/New_York")  # the app's day ends at midnight Eastern
MAX_DAILY_STEPS = 100_000

INSTRUCTIONS = """\
Tools for one family's step leaderboard. Weeks run Monday to Sunday and days end at midnight Eastern time.
Logging steps for a day that already has a total replaces it; it doesn't add to it.
"""


def today_eastern() -> date:
    return datetime.now(EASTERN).date()


def parse_day(text: str | None, field: str) -> date | None:
    if not text:
        return None
    try:
        return date.fromisoformat(text.strip())
    except ValueError:
        raise ToolError(f"{field} must be a date written YYYY-MM-DD, such as {today_eastern().isoformat()}.")


def find_member(members: list[dict], name: str) -> dict:
    """The member called `name`: an exact match (ignoring case), or else the only name starting with it."""
    wanted = name.strip().casefold()
    exact = [m for m in members if m["name"].casefold() == wanted]
    candidates = exact or [m for m in members if m["name"].casefold().startswith(wanted)]
    if len(candidates) == 1:
        return candidates[0]
    names = ", ".join(m["name"] for m in members) or "none yet"
    if not candidates:
        raise ToolError(f'No member called "{name}". Members: {names}.')
    raise ToolError(f'"{name}" could be {", ".join(m["name"] for m in candidates)}. Which one?')


def describe_board(board: dict) -> str:
    """A board as text, like the app's digests: who leads, then each row with any change since the last period."""
    standings = board["standings"]
    if not standings:
        return f"{board['title']}\nNo one has joined yet."
    leaders = [s for s in standings if s["rank"] == 1]
    if leaders[0]["steps"] == 0:
        headline = "No steps logged yet."
    elif len(leaders) == 1:
        headline = f"Leader: {leaders[0]['name']} with {leaders[0]['steps']:,} steps."
    else:
        headline = f"Tied for first: {' and '.join(s['name'] for s in leaders)}, {leaders[0]['steps']:,} steps each."
    lines = [board["title"], headline]
    for s in standings:
        row = f"{s['medal'] or str(s['rank']) + '.'} {s['name']} — {s['steps']:,}"
        if board["has_comparison"]:
            if s["prev_rank"] is None:
                row += " (new)"
            else:
                move = s["prev_rank"] - s["rank"]
                arrow = f"up {move}" if move > 0 else f"down {-move}" if move < 0 else "same place"
                row += f" ({arrow}, {s['step_change']:+,} steps)"
        lines.append(row)
    lines += [c["text"] for c in board["callouts"]]
    return "\n".join(lines)


def build_server(config: Config, api: StepboardApi | None = None) -> MCPServer:
    api = api or StepboardApi(config.api_url)
    server = MCPServer(
        name="stepboard",
        title="Family Step Leaderboard",
        instructions=INSTRUCTIONS + f"Family: {config.family}. App: {config.api_url}.",
    )

    def family() -> dict:
        try:
            return api.find_family(config.family)
        except ApiError as error:
            raise ToolError(str(error))

    @server.tool(annotations=ToolAnnotations(title="Leaderboard", read_only_hint=True, open_world_hint=True))
    def get_leaderboard(
        board: Annotated[
            Literal["weekly", "all_time"],
            Field(description="weekly: Monday through today (or as_of). all_time: everything since the family started."),
        ] = "weekly",
        as_of: Annotated[
            str | None, Field(description="Last day to count, YYYY-MM-DD. Leave out for today (Eastern).")
        ] = None,
    ) -> str:
        """Who's winning: the family's standings with medals, changes since the last period, and callouts."""
        day = parse_day(as_of, "as_of")
        try:
            fam = family()
            data = api.weekly_leaderboard(fam["id"], day) if board == "weekly" else api.alltime_leaderboard(fam["id"], day)
        except ApiError as error:
            raise ToolError(str(error))
        return describe_board(data)

    @server.tool(annotations=ToolAnnotations(title="Family members", read_only_hint=True, open_world_hint=True))
    def list_members() -> str:
        """The family's members, to know who steps can be logged for."""
        fam = family()
        try:
            names = [m["name"] for m in api.list_members(fam["id"])]
        except ApiError as error:
            raise ToolError(str(error))
        return f"{fam['name']} has {len(names)} member{'s' if len(names) != 1 else ''}: {', '.join(names) or 'none yet'}."

    @server.tool(
        annotations=ToolAnnotations(
            title="Log steps",
            read_only_hint=False,
            destructive_hint=True,  # a day's total replaces any earlier total for that day
            idempotent_hint=True,  # logging the same total again changes nothing
            open_world_hint=True,
        )
    )
    def log_steps(
        member: Annotated[str, Field(description="The member's name, as list_members shows it. Not case-sensitive.")],
        steps: Annotated[int, Field(description="The day's total steps.", ge=0, le=MAX_DAILY_STEPS)],
        day: Annotated[
            str | None, Field(description="The day, YYYY-MM-DD. Leave out for today (Eastern). Not in the future.")
        ] = None,
    ) -> str:
        """Record a member's total steps for a day. It replaces any total already logged for that day."""
        when = parse_day(day, "day") or today_eastern()
        try:
            fam = family()
            person = find_member(api.list_members(fam["id"]), member)
            before = api.member_steps(person["id"], start=when, end=when)
            api.log_steps(person["id"], [(when, steps)])
            standings = api.weekly_leaderboard(fam["id"])["standings"]
        except ApiError as error:
            raise ToolError(str(error))

        message = f"Logged {steps:,} steps for {person['name']} on {when:%A, %b} {when.day}"
        if before and before[0]["steps"] != steps:
            message += f", replacing the {before[0]['steps']:,} logged before"
        elif before:
            message += ", which it already was"
        message += "."
        # Their place on this week's board, if the day logged is in this week (Monday onward).
        this_monday = today_eastern() - timedelta(days=today_eastern().weekday())
        mine = next((s for s in standings if s["member_id"] == person["id"]), None)
        if mine and when >= this_monday:
            message += f" This week {person['name']} has {mine['steps']:,} steps, rank {mine['rank']} of {len(standings)}."
        return message

    return server


def main() -> None:
    # httpx logs every request at INFO; on stdio that only adds noise to the client's MCP logs.
    logging.getLogger("httpx").setLevel(logging.WARNING)
    build_server(Config.from_env()).run()  # stdio by default
