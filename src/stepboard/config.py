import os
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

# Everyone's day ends at midnight Eastern.
EASTERN = ZoneInfo("America/New_York")

REQUIRED = ("DISCORD_TOKEN", "DISCORD_GUILD_ID", "LAUNCH_DAY")


def today_eastern() -> date:
    return datetime.now(EASTERN).date()


@dataclass(frozen=True)
class Settings:
    discord_token: str
    guild_id: int
    launch_day: date
    database_path: Path
    port: int

    @classmethod
    def from_env(cls) -> "Settings":
        load_dotenv()
        missing = [name for name in REQUIRED if not os.environ.get(name)]
        if missing:
            raise SystemExit(f"Missing settings: {', '.join(missing)} (see .env.example)")
        return cls(
            discord_token=os.environ["DISCORD_TOKEN"],
            guild_id=int(os.environ["DISCORD_GUILD_ID"]),
            launch_day=date.fromisoformat(os.environ["LAUNCH_DAY"]),
            database_path=Path(os.environ.get("DATABASE_PATH", "stepboard.db")),
            port=int(os.environ.get("PORT", "8000")),
        )
