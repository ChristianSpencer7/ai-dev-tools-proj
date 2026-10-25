"""Weekly and monthly digests: saved for the Messages page, and posted to Discord when a webhook is set."""

import logging
from dataclasses import dataclass, field
from datetime import date

from django.db import transaction

from leaderboard.boards import alltime_board, weekly_board
from leaderboard.discord import post_to_discord
from leaderboard.models import Family, Message
from leaderboard.seed import DEMO_INVITE_CODE

log = logging.getLogger(__name__)

# The monthly digest shows all-time totals (docs/plan.md, "Messages").
BOARD_FOR_KIND = {
    Message.Kind.WEEKLY: weekly_board,
    Message.Kind.MONTHLY: alltime_board,
}


def send_digest(family: Family, kind: str, as_of: date) -> Message:
    """Builds the digest text, posts it to Discord if configured, and saves it.

    post_to_discord never raises, so the message is saved whatever happens with Discord. The Demo Family's digests
    are never posted: its code is public, so anyone can send one, and the webhook is a real family's channel.
    """
    text = BOARD_FOR_KIND[kind](family, as_of).text()
    if family.invite_code == DEMO_INVITE_CODE:
        discord_status = Message.DiscordStatus.NOT_CONFIGURED
    else:
        discord_status = post_to_discord(text)
    return Message.objects.create(family=family, kind=kind, as_of=as_of, text=text, discord_status=discord_status)


@dataclass
class ScheduledRun:
    """What send_scheduled_digests did, family by family."""

    sent: list[Message] = field(default_factory=list)
    skipped: list[tuple[Family, str]] = field(default_factory=list)  # (family, reason)
    failed: list[tuple[Family, str]] = field(default_factory=list)  # (family, error type)


def send_scheduled_digests(kind: str, as_of: date, include_demo: bool = False) -> ScheduledRun:
    """Sends one digest of this kind to every family that should get one. Safe to run twice.

    Skips the Demo Family unless include_demo (and even then its digest is only saved, never posted: see
    send_digest), families that hadn't started by as_of, and families that already have this digest.
    One family's failure is logged and doesn't stop the others.
    """
    run = ScheduledRun()
    for family in Family.objects.order_by("id"):
        if family.invite_code == DEMO_INVITE_CODE and not include_demo:
            run.skipped.append((family, "demo"))
        elif family.start_date > as_of:
            run.skipped.append((family, "not started yet"))
        elif family.messages.filter(kind=kind, as_of=as_of).exists():
            run.skipped.append((family, "already sent"))
        else:
            try:
                with transaction.atomic():
                    run.sent.append(send_digest(family, kind, as_of))
            except Exception as error:
                log.exception("The %s digest for %s (family %s) failed", kind, family.name, family.id)
                run.failed.append((family, type(error).__name__))
    return run
