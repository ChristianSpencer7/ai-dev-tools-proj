import sqlite3
from datetime import date
from pathlib import Path

from stepboard.leaderboard import DayRecord

SCHEMA = """
CREATE TABLE IF NOT EXISTS members (
    discord_id   INTEGER PRIMARY KEY,
    display_name TEXT NOT NULL,
    joined_at    TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS daily_steps (
    member_id  INTEGER NOT NULL REFERENCES members(discord_id),
    day        TEXT NOT NULL,     -- ISO date, Eastern
    steps      INTEGER NOT NULL CHECK (steps >= 0),
    source     TEXT NOT NULL,     -- manual, fitbit, shortcut, android
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (member_id, day)
);
"""


class Database:
    """Small synchronous SQLite wrapper. Queries are tiny, so blocking the loop is fine."""

    def __init__(self, path: Path | str):
        self.conn = sqlite3.connect(path)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")
        self.conn.execute("PRAGMA journal_mode = WAL")  # required by Litestream
        self.conn.executescript(SCHEMA)

    def close(self) -> None:
        self.conn.close()

    def upsert_member(self, discord_id: int, display_name: str) -> None:
        with self.conn:
            self.conn.execute(
                """
                INSERT INTO members (discord_id, display_name) VALUES (?, ?)
                ON CONFLICT (discord_id) DO UPDATE SET display_name = excluded.display_name
                """,
                (discord_id, display_name),
            )

    def members(self) -> dict[int, str]:
        rows = self.conn.execute("SELECT discord_id, display_name FROM members")
        return {row["discord_id"]: row["display_name"] for row in rows}

    def record_steps(self, member_id: int, day: date, steps: int, source: str) -> None:
        """Store a day's steps. A later value for the same day replaces the earlier one."""
        with self.conn:
            self.conn.execute(
                """
                INSERT INTO daily_steps (member_id, day, steps, source) VALUES (?, ?, ?, ?)
                ON CONFLICT (member_id, day) DO UPDATE SET
                    steps = excluded.steps,
                    source = excluded.source,
                    updated_at = datetime('now')
                """,
                (member_id, day.isoformat(), steps, source),
            )

    def totals(self, start: date, end: date) -> dict[int, int]:
        """Total steps per member from start through end, inclusive."""
        rows = self.conn.execute(
            """
            SELECT member_id, SUM(steps) AS total FROM daily_steps
            WHERE day BETWEEN ? AND ? GROUP BY member_id
            """,
            (start.isoformat(), end.isoformat()),
        )
        return {row["member_id"]: row["total"] for row in rows}

    def daily(self, start: date, end: date) -> list[DayRecord]:
        rows = self.conn.execute(
            "SELECT member_id, day, steps FROM daily_steps WHERE day BETWEEN ? AND ? ORDER BY day",
            (start.isoformat(), end.isoformat()),
        )
        return [DayRecord(row["member_id"], date.fromisoformat(row["day"]), row["steps"]) for row in rows]
