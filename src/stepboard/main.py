"""Runs the Discord bot and the web endpoint together on one event loop."""

import asyncio
import contextlib
import logging

import uvicorn

from stepboard.api import create_api
from stepboard.bot import StepBot
from stepboard.config import Settings
from stepboard.db import Database


async def run() -> None:
    settings = Settings.from_env()
    db = Database(settings.database_path)
    bot = StepBot(db, settings)
    server = uvicorn.Server(
        uvicorn.Config(create_api(db), host="0.0.0.0", port=settings.port, log_level="info")
    )

    async with bot:
        bot_task = asyncio.create_task(bot.start(settings.discord_token))
        # If the bot stops (bad token, lost connection it can't recover from), stop the server too.
        bot_task.add_done_callback(lambda _: setattr(server, "should_exit", True))
        try:
            await server.serve()  # returns on Ctrl+C / SIGTERM
        finally:
            await bot.close()
            with contextlib.suppress(asyncio.CancelledError):
                await bot_task
            db.close()


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    asyncio.run(run())
