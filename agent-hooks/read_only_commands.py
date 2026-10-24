"""Claude Code PreToolUse hook for the read-only leaderboard-rules-reviewer subagent: only read-only shell commands.

Registered in the subagent's own front matter (.claude/agents/leaderboard-rules-reviewer.md), so it applies only while
that subagent runs. A subagent's tool list can't limit Bash to particular commands, so this hook does: every part of
a command (split at &&, ||, ; and |) must be on the allowlist below, and writing redirections and command
substitution are refused. Exit code 2 blocks the command; stderr is the reason the subagent sees. Standard library only.
"""

import json
import re
import shlex
import sys

BLOCK = 2

ALLOWED_PROGRAMS = {"cat", "head", "tail", "grep", "rg", "ls", "wc", "sort", "uniq", "diff", "pwd", "cd", "echo", "true"}
GIT_READ_ONLY = {"diff", "log", "show", "status", "blame", "ls-files", "rev-parse", "grep", "merge-base", "branch"}
MANAGE_READ_ONLY = {"check", "showmigrations", "sqlmigrate"}
HARMLESS_REDIRECTS = re.compile(r"\d?>&\d|\d?>\s*/dev/null")
SEPARATORS = re.compile(r"&&|\|\||;|\|")


def python_part_allowed(args: list[str]) -> bool:
    """Tests and Django's read-only checks: python -m pytest ..., python manage.py check, makemigrations --check."""
    if args[:2] == ["-m", "pytest"]:
        return True
    if args[:1] == ["manage.py"] and len(args) > 1:
        if args[1] in MANAGE_READ_ONLY:
            return True
        return args[1] == "makemigrations" and "--check" in args and "--dry-run" in args
    return False


def part_allowed(part: str) -> bool:
    try:
        words = shlex.split(part, posix=True)
    except ValueError:
        return False
    if not words:
        return True
    program, args = words[0].replace("\\", "/").rsplit("/", 1)[-1], words[1:]
    program = program.removesuffix(".exe")
    if program in ALLOWED_PROGRAMS:
        return True
    if program == "find":
        return not any(a in {"-delete", "-exec", "-execdir", "-ok", "-fprint", "-fprintf", "-fls"} for a in args)
    if program == "sed":
        return "-i" not in args and not any(a.startswith(("-i", "--in-place")) for a in args)
    if program == "git":
        sub = next((a for a in args if not a.startswith("-")), "")
        if sub == "branch":
            return all(a in {"branch", "--show-current", "-a", "--list", "-v"} for a in args)
        return sub in GIT_READ_ONLY
    if program == "pytest":
        return True
    if program in {"python", "python3", "py"}:
        return python_part_allowed(args)
    return False


def reason_to_block(command: str) -> str | None:
    if "$(" in command or "`" in command:
        return "command substitution ($(...) or backticks) isn't allowed"
    if ">" in HARMLESS_REDIRECTS.sub(" ", command):
        return "redirecting output into a file isn't allowed"
    for part in SEPARATORS.split(command):
        if not part_allowed(part.strip()):
            return f"`{part.strip()}` isn't on its list of read-only commands"
    return None


def main() -> int:
    try:
        event = json.load(sys.stdin)
    except json.JSONDecodeError:
        print("read_only_commands: the hook input wasn't JSON.", file=sys.stderr)
        return BLOCK  # this hook's job is to keep the reviewer read-only, so when unsure, block
    command = (event.get("tool_input") or {}).get("command") or ""
    reason = reason_to_block(command)
    if reason:
        print(
            f"Blocked by agent-hooks/read_only_commands.py: the leaderboard-rules-reviewer is read-only, and {reason}. "
            "It may run git diff/log/show/status, grep, cat, ls, find, sed without -i, pytest, and manage.py check. "
            "Report what you'd change as a finding instead.",
            file=sys.stderr,
        )
        return BLOCK
    return 0


if __name__ == "__main__":
    sys.exit(main())
