"""Claude Code PostToolUse hook: after an edit to the API contract or the code behind it, run the contract tests.

Runs after every Edit and Write (registered in .claude/settings.json), but only does anything when the file is
openapi.yaml or one of the backend files that define the API. If the contract tests fail, it exits 2: the edit has
already happened, but Claude sees the failure straight away and can fix the drift, instead of finding out in CI.
Standard library only; the tests run in the backend's own Python environment.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

BLOCK = 2  # for PostToolUse: show stderr to Claude
TIMEOUT_SECONDS = 150
WATCHED = {
    "openapi.yaml",
    "backend/leaderboard/urls.py",
    "backend/leaderboard/views.py",
    "backend/leaderboard/serializers.py",
}
CONTRACT_TESTS = ["tests/integration/test_contract.py", "tests/integration/test_contract_responses.py"]


def project_dir() -> Path:
    return Path(os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()).resolve()


def backend_python(root: Path) -> Path | None:
    """STEPBOARD_BACKEND_PYTHON, or the repository's .venv (Windows or macOS/Linux layout)."""
    if os.environ.get("STEPBOARD_BACKEND_PYTHON"):
        chosen = Path(os.environ["STEPBOARD_BACKEND_PYTHON"])
        return chosen if chosen.exists() else None
    for candidate in (root / ".venv" / "Scripts" / "python.exe", root / ".venv" / "bin" / "python"):
        if candidate.exists():
            return candidate
    return None


def main() -> int:
    try:
        event = json.load(sys.stdin)
    except json.JSONDecodeError:
        print("contract_check: the hook input wasn't JSON; nothing checked.", file=sys.stderr)
        return 1
    file_path = (event.get("tool_input") or {}).get("file_path")
    root = project_dir()
    try:
        path = Path(file_path).resolve().relative_to(root).as_posix() if file_path else None
    except ValueError:
        path = None
    if path not in WATCHED:
        return 0

    python = backend_python(root)
    if python is None:
        print("contract_check: no backend environment found (.venv, or STEPBOARD_BACKEND_PYTHON); contract tests not run.", file=sys.stderr)
        return 1
    env = {k: v for k, v in os.environ.items() if k != "DATABASE_URL"}  # the tests' own SQLite database
    try:
        result = subprocess.run(
            [str(python), "-m", "pytest", *CONTRACT_TESTS, "-q", "-p", "no:cacheprovider"],
            cwd=root / "backend", env=env, capture_output=True, text=True, timeout=TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired:
        print(f"contract_check: the contract tests took over {TIMEOUT_SECONDS}s; not checked.", file=sys.stderr)
        return 1
    if result.returncode == 0:
        return 0

    # The lines that say what's wrong: pytest's assertion messages, then its summary.
    lines = result.stdout.splitlines()
    details = [line[1:].strip() for line in lines if line.startswith("E ")][:12]
    summary = lines[-1] if lines else "(no output)"
    print(
        f"Contract check after editing {path}: openapi.yaml and the backend now disagree ({summary}).\n"
        + "\n".join(details)
        + "\nIf you're changing both, this is expected until the other side is updated (contract first: "
        "openapi.yaml, then serializers.py, views.py and urls.py). Otherwise, fix it before moving on.",
        file=sys.stderr,
    )
    return BLOCK


if __name__ == "__main__":
    sys.exit(main())
