"""Claude Code PreToolUse hook: stops an AI agent changing files the project's rules protect.

Runs before every Edit, Write, Bash and PowerShell call (registered in .claude/settings.json). Claude Code sends the
tool call as JSON on stdin; exit code 2 blocks it, and what this prints to stderr is the reason Claude sees.
Standard library only.

Protected:
- .env files: they hold secrets, so agents may not change or read them (.env.example is fine)
- SQLite database files: change data through the app or migrations, not the file (reading is fine)
- a migration that's already committed: AGENTS.md says never edit one; add a new migration instead (reading is fine)

For shell commands this is a pattern check on the command's text: it catches the usual ways of changing a file
(sed -i, redirection, tee, rm, mv, cp, Set-Content, ...), but it isn't a sandbox. See docs/permissions.md.
"""

import json
import os
import re
import subprocess
import sys
from pathlib import Path, PurePosixPath

BLOCK = 2
MIGRATIONS = "backend/leaderboard/migrations/"
SHELL_TOOLS = {"Bash", "PowerShell"}

# A .env file named in a command: .env or .env.<anything>, as a whole word, except .env.example.
ENV_FILE = re.compile(r"(?<![\w.-])\.env(?:\.[\w-]+)?(?![\w.-])")
DATABASE_FILE = re.compile(r"[\w./\\-]*\.sqlite3\b|\bdb\.sqlite3\b")
MIGRATION_FILE = re.compile(r"(\d{4}_\w+\.py)\b")
# Ways a command changes a file. Redirection is checked after removing the harmless kinds (see harmless()).
CHANGES_A_FILE = re.compile(
    r"\bsed\b[^|;&]*\s-[a-zA-Z]*i|\bperl\b[^|;&]*\s-[a-zA-Z]*i|>|\btee\b|\brm\b|\bmv\b|\bcp\b|\btruncate\b|\bdd\b"
    r"|\b(Set|Add|Clear)-Content\b|\bOut-File\b|\b(Remove|Move|Copy|New|Rename)-Item\b"
    r"|\.write_text\(|\.write_bytes\(|open\([^)]*['\"][wa]",
    re.IGNORECASE,
)
HARMLESS_REDIRECTS = re.compile(r"\d?>&\d|\d?>\s*/dev/null|\d?>\s*\$null|\d?>\s*NUL\b", re.IGNORECASE)

ENV_REASON = "{path} holds secrets (DJANGO_SECRET_KEY, DISCORD_WEBHOOK_URL), so agents don't change or read it. Ask the user to change it, or edit .env.example for documentation."
DATABASE_REASON = "{path} is a database file. Change data through the app or its admin, and the schema through a migration."
MIGRATION_REASON = (
    "{path} is a migration that's already committed, and other databases may have applied it "
    "(AGENTS.md: never edit a pushed migration). Change the model, then run "
    "`python manage.py makemigrations` in backend/ to add a new migration instead."
)


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


def is_env_file(name: str) -> bool:
    return name == ".env" or (name.startswith(".env.") and name != ".env.example")


def is_committed_migration(path: str, root: Path) -> bool:
    name = PurePosixPath(path).name
    return path.startswith(MIGRATIONS) and name != "__init__.py" and name.endswith(".py") and committed(path, root)


def file_reason(path: str, root: Path) -> str | None:
    """Edit and Write: the file they'd change."""
    name = PurePosixPath(path).name
    if is_env_file(name):
        return ENV_REASON.format(path=path)
    if name.endswith((".sqlite3", ".db")):
        return DATABASE_REASON.format(path=path)
    if is_committed_migration(path, root):
        return MIGRATION_REASON.format(path=path)
    return None


def changes_a_file(command: str) -> bool:
    return bool(CHANGES_A_FILE.search(HARMLESS_REDIRECTS.sub(" ", command)))


def command_reason(command: str, root: Path) -> str | None:
    """Bash and PowerShell: protected files the command names, and whether it changes them."""
    for match in ENV_FILE.finditer(command):
        if match.group(0) != ".env.example":
            return ENV_REASON.format(path=match.group(0))
    if not changes_a_file(command):
        return None  # reading a database or a migration is fine
    database = DATABASE_FILE.search(command)
    if database:
        return DATABASE_REASON.format(path=database.group(0))
    for name in MIGRATION_FILE.findall(command):
        path = MIGRATIONS + name
        if is_committed_migration(path, root):
            return MIGRATION_REASON.format(path=path)
    return None


def main() -> int:
    try:
        event = json.load(sys.stdin)
    except json.JSONDecodeError:
        print("guard_files: the hook input wasn't JSON; nothing checked.", file=sys.stderr)
        return 1  # a non-blocking error: the call goes ahead, and the user sees a notice
    tool_input = event.get("tool_input") or {}
    root = project_dir()
    if event.get("tool_name") in SHELL_TOOLS:
        reason = command_reason(tool_input.get("command") or "", root)
    else:
        path = relative_path(tool_input["file_path"], root) if tool_input.get("file_path") else None
        reason = file_reason(path, root) if path else None  # outside the project: not this hook's business
    if reason:
        print(f"Blocked by agent-hooks/guard_files.py: {reason}", file=sys.stderr)
        return BLOCK
    return 0


if __name__ == "__main__":
    sys.exit(main())
