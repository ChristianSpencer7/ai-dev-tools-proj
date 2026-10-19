"""Weekly and monthly digests: saved for the Messages page, and posted to Discord when a webhook is set."""

from datetime import date

from leaderboard.boards import alltime_board, weekly_board
from leaderboard.discord import post_to_discord
from leaderboard.models import Family, Message

# The monthly digest shows all-time totals (docs/plan.md, "Messages").
BOARD_FOR_KIND = {
    Message.Kind.WEEKLY: weekly_board,
    Message.Kind.MONTHLY: alltime_board,
}


def send_digest(family: Family, kind: str, as_of: date) -> Message:
    """Builds the digest text, posts it to Discord if configured, and saves it.

    post_to_discord never raises, so the message is saved whatever happens with Discord.
    """
    text = BOARD_FOR_KIND[kind](family, as_of).text()
    return Message.objects.create(family=family, kind=kind, text=text, discord_status=post_to_discord(text))
