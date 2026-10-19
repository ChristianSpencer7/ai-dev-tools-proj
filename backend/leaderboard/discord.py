"""Posting a digest to a Discord webhook. Optional: without DISCORD_WEBHOOK_URL nothing is sent."""

import logging

import httpx
from django.conf import settings

from leaderboard.models import Message

log = logging.getLogger(__name__)

DISCORD_MAX_LENGTH = 2_000  # Discord rejects longer messages
TIMEOUT_SECONDS = 10


def fit_for_discord(text: str) -> str:
    if len(text) <= DISCORD_MAX_LENGTH:
        return text
    return text[: DISCORD_MAX_LENGTH - 1] + "…"


def post_to_discord(text: str) -> str:
    """Sends one request to the webhook and returns the discord_status to store. Never raises.

    The webhook URL works like a password (anyone with it can post to the channel), so it is never logged.
    """
    webhook_url = settings.DISCORD_WEBHOOK_URL
    if not webhook_url:
        return Message.DiscordStatus.NOT_CONFIGURED

    payload = {
        "content": fit_for_discord(text),
        # Member names are typed in by users; a member called "@everyone" must not ping the whole server.
        "allowed_mentions": {"parse": []},
    }
    try:
        response = httpx.post(webhook_url, json=payload, timeout=TIMEOUT_SECONDS)
        response.raise_for_status()
    except Exception as error:  # timeouts, network errors, Discord errors, a malformed URL: the digest is kept either way
        status_code = getattr(getattr(error, "response", None), "status_code", None)
        # Only the error type and status: httpx's messages include the URL.
        log.warning("Discord webhook post failed: %s%s", type(error).__name__, f" (HTTP {status_code})" if status_code else "")
        return Message.DiscordStatus.FAILED
    return Message.DiscordStatus.SENT
