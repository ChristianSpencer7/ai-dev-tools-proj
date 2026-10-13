"""Weekly and monthly digests: saved for the Messages page, posted to Discord when configured."""

import logging
from datetime import date
from typing import Literal

import httpx
from sqlalchemy.orm import Session

from stepboard import db
from stepboard.reports import alltime_board, weekly_board

log = logging.getLogger(__name__)

DigestKind = Literal["weekly", "monthly"]


def post_to_discord(webhook_url: str | None, text: str) -> str:
    """One HTTP request to a Discord webhook. Returns the discord_status to store."""
    if not webhook_url:
        return "not_configured"
    try:
        response = httpx.post(webhook_url, json={"content": text}, timeout=10)
        response.raise_for_status()
    except httpx.HTTPError:
        log.exception("Discord webhook post failed")
        return "failed"
    return "sent"


def send_digest(
    session: Session,
    family: db.Family,
    kind: DigestKind,
    as_of: date,
    webhook_url: str | None,
) -> db.Message:
    board = weekly_board(session, family, as_of) if kind == "weekly" else alltime_board(session, family, as_of)
    text = board.text()
    message = db.Message(
        family_id=family.id,
        kind=kind,
        text=text,
        discord_status=post_to_discord(webhook_url, text),
    )
    session.add(message)
    session.commit()
    return message
