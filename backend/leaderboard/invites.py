"""Invite codes: short, random, and easy to read aloud or type from a text message."""

import secrets

from leaderboard.models import Family

# No 0/O or 1/I, so a code read aloud or squinted at can't be mistaken for another.
INVITE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
CODE_LENGTH = 6  # 32**6 ≈ 1 billion codes
MAX_ATTEMPTS = 10


def new_invite_code() -> str:
    """A random code. Uses secrets, not random, so codes can't be predicted."""
    return "".join(secrets.choice(INVITE_ALPHABET) for _ in range(CODE_LENGTH))


def unique_invite_code() -> str:
    """A code no family has yet. Collisions are rare; the unique constraint still guards a race."""
    for _ in range(MAX_ATTEMPTS):
        code = new_invite_code()
        if not Family.objects.filter(invite_code=code).exists():
            return code
    raise RuntimeError(f"No unused invite code after {MAX_ATTEMPTS} tries")
