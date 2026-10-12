import logging
from datetime import date, timedelta
from typing import Literal

import discord
from discord import app_commands
from discord.ext import commands

from stepboard.config import Settings, today_eastern
from stepboard.db import Database
from stepboard.reports import alltime_report, weekly_report

log = logging.getLogger(__name__)

MAX_DAILY_STEPS = 100_000


def parse_day(text: str | None, today: date) -> date:
    """Accepts 'today', 'yesterday', or YYYY-MM-DD. Defaults to today."""
    if text is None or text.strip().lower() == "today":
        return today
    if text.strip().lower() == "yesterday":
        return today - timedelta(days=1)
    return date.fromisoformat(text.strip())


class StepBot(commands.Bot):
    def __init__(self, db: Database, settings: Settings):
        super().__init__(command_prefix=commands.when_mentioned, intents=discord.Intents.default())
        self.db = db
        self.settings = settings
        self.tree.add_command(log_command)
        self.tree.add_command(leaderboard_command)

    async def setup_hook(self) -> None:
        # Syncing to one server makes new commands show up immediately.
        guild = discord.Object(id=self.settings.guild_id)
        self.tree.copy_global_to(guild=guild)
        await self.tree.sync(guild=guild)

    async def on_ready(self) -> None:
        log.info("Logged in as %s", self.user)


@app_commands.command(name="log", description="Record your steps for a day by hand")
@app_commands.describe(
    steps="Total steps for the day",
    day="today, yesterday, or YYYY-MM-DD (default: today)",
)
async def log_command(
    interaction: discord.Interaction[StepBot],
    steps: app_commands.Range[int, 0, MAX_DAILY_STEPS],
    day: str | None = None,
) -> None:
    bot = interaction.client
    today = today_eastern()
    try:
        target = parse_day(day, today)
    except ValueError:
        await interaction.response.send_message(
            "I couldn't read that day. Use today, yesterday, or YYYY-MM-DD.", ephemeral=True
        )
        return
    if target > today:
        await interaction.response.send_message("That day hasn't happened yet.", ephemeral=True)
        return

    bot.db.upsert_member(interaction.user.id, interaction.user.display_name)
    bot.db.record_steps(interaction.user.id, target, steps, source="manual")

    message = f"Logged {steps:,} steps for {target:%A, %b} {target.day}."
    if target < bot.settings.launch_day:
        message += " That's before launch day, so it won't count toward the leaderboards."
    await interaction.response.send_message(message, ephemeral=True)


@app_commands.command(name="leaderboard", description="Show the current standings")
@app_commands.describe(board="Which leaderboard to show (default: this week)")
async def leaderboard_command(
    interaction: discord.Interaction[StepBot],
    board: Literal["week", "all-time"] = "week",
) -> None:
    bot = interaction.client
    today = today_eastern()
    if board == "week":
        text = weekly_report(bot.db, today, bot.settings.launch_day)
    else:
        text = alltime_report(bot.db, today, bot.settings.launch_day)
    await interaction.response.send_message(text)
