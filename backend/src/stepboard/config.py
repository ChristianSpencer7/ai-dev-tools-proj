import os
from dataclasses import dataclass
from datetime import date, datetime
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

# Everyone's day ends at midnight Eastern.
EASTERN = ZoneInfo("America/New_York")


def today_eastern() -> date:
    return datetime.now(EASTERN).date()


@dataclass(frozen=True)
class Settings:
    database_url: str
    discord_webhook_url: str | None

    @classmethod
    def from_env(cls) -> "Settings":
        load_dotenv()
        return cls(
            database_url=os.environ.get("DATABASE_URL", "sqlite:///stepboard.db"),
            discord_webhook_url=os.environ.get("DISCORD_WEBHOOK_URL") or None,
        )
