"""Claude Code PreToolUse hook: stops an AI agent editing files the project's rules protect.

Runs before every Edit and Write (registered in .claude/settings.json). Claude Code sends the tool call as JSON on
stdin; exit code 2 blocks it, and what this prints to stderr is the reason Claude sees. Standard library only.

Blocked:
- .env files: they hold secrets (.env.example is fine)
- SQLite database files: change data through the app or migrations, not the file
- a migration that's already committed: AGENTS.md says never edit one; add a new migration instead
"""

import json
import os
import subprocess
import sys
from pathlib import Path, PurePosixPath

BLOCK = 2
MIGRATIONS = "backend/leaderboard/migrations/"


def project_dir() -> Path:
    return Path(os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()).resolve()


def relative_path(file_path: str, root: Path) -> str | None:
    """The path relative to the project, with forward slashes; None if it's outside the project."""
    try:
        return Path(file_path).resolve().relative_to(root).as_posix()
    except ValueError:
        return None


def committed(path: str, root: Path) -> bool:
    """Whether the file exists in the last commit (so other copies of the repository may already have it)."""
    result = subprocess.run(["git", "cat-file", "-e", f"HEAD:{path}"], cwd=root, capture_output=True)
    return result.returncode == 0


def reason_to_block(path: str, root: Path) -> str | None:
    name = PurePosixPath(path).name
    if name == ".env" or (name.startswith(".env.") and name != ".env.example"):
        return f"{path} holds secrets (DJANGO_SECRET_KEY, DISCORD_WEBHOOK_URL), so agents don't edit it. Ask the user to change it, or edit .env.example for documentation."
    if name.endswith((".sqlite3", ".db")):
        return f"{path} is a database file. Change data through the app or its admin, and the schema through a migration."
    if path.startswith(MIGRATIONS) and name != "__init__.py" and name.endswith(".py") and committed(path, root):
        return (
            f"{path} is a migration that's already committed, and other databases may have applied it "
            "(AGENTS.md: never edit a pushed migration). Change the model, then run "
            "`python manage.py makemigrations` in backend/ to add a new migration instead."
        )
    return None


def main() -> int:
    try:
        event = json.load(sys.stdin)
    except json.JSONDecodeError:
        print("guard_files: the hook input wasn't JSON; nothing checked.", file=sys.stderr)
        return 1  # a non-blocking error: the edit goes ahead, and the user sees a notice
    file_path = (event.get("tool_input") or {}).get("file_path")
    if not file_path:
        return 0
    root = project_dir()
    path = relative_path(file_path, root)
    if path is None:
        return 0  # outside the project: not this hook's business
    reason = reason_to_block(path, root)
    if reason:
        print(f"Blocked by agent-hooks/guard_files.py: {reason}", file=sys.stderr)
        return BLOCK
    return 0


if __name__ == "__main__":
    sys.exit(main())
