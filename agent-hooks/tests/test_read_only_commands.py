"""The reviewer subagent's read-only hook, run the way Claude Code runs it, plus checks on the subagent's definition."""

import json
import re
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

HOOKS = Path(__file__).resolve().parents[1]
REPO = HOOKS.parent
AGENT = REPO / ".claude" / "agents" / "leaderboard-rules-reviewer.md"


def run(command):
    event = {"hook_event_name": "PreToolUse", "tool_name": "Bash", "tool_input": {"command": command}}
    result = subprocess.run([sys.executable, str(HOOKS / "read_only_commands.py")], input=json.dumps(event),
                            capture_output=True, text=True, timeout=30)
    return result.returncode, result.stderr


@pytest.mark.parametrize(
    "command",
    [
        "git diff origin/main...HEAD --stat",
        "git log --oneline -5 && git status --short",
        "git show HEAD:backend/leaderboard/views.py | grep -n get_family",
        "git branch --show-current",
        "cat backend/leaderboard/ranking.py",
        "grep -rn 'date.today' backend/leaderboard",
        "find backend -name '*.py' -newer docs/plan.md",
        "sed -n '1,40p' backend/leaderboard/views.py",
        "cd backend && python -m pytest tests/integration/test_steps.py -q 2>&1",
        "cd backend && ../.venv/Scripts/python -m pytest -q",
        "cd backend && ../.venv/bin/python manage.py makemigrations --check --dry-run",
        "cd backend && python manage.py check",
        "ls backend/leaderboard | wc -l",
    ],
)
def test_reading_and_testing_is_allowed(command):
    assert run(command) == (0, "")


@pytest.mark.parametrize(
    ("command", "why"),
    [
        ("sed -i 's/a/b/' backend/leaderboard/views.py", "read-only commands"),
        ("echo x > backend/leaderboard/views.py", "redirecting output"),
        ("cat views.py >> notes.txt", "redirecting output"),
        ("rm backend/db.sqlite3", "read-only commands"),
        ("git commit -am 'fix'", "read-only commands"),
        ("git checkout -- backend/leaderboard/views.py", "read-only commands"),
        ("git branch -D main", "read-only commands"),
        ("python -c \"open('x', 'w').write('y')\"", "read-only commands"),
        ("cd backend && python manage.py migrate", "read-only commands"),
        ("cd backend && python manage.py makemigrations", "read-only commands"),
        ("find . -name '*.pyc' -delete", "read-only commands"),
        ("git log && touch x", "read-only commands"),
        ("cat $(echo views.py)", "command substitution"),
        ("pip install requests", "read-only commands"),
    ],
)
def test_anything_that_could_change_files_is_blocked(command, why):
    code, reason = run(command)
    assert code == 2
    assert reason.startswith("Blocked by agent-hooks/read_only_commands.py: the leaderboard-rules-reviewer is read-only")
    assert why in reason


def test_bad_input_blocks():
    result = subprocess.run([sys.executable, str(HOOKS / "read_only_commands.py")], input="not json",
                            capture_output=True, text=True, timeout=30)
    assert result.returncode == 2


# --- The subagent's definition -------------------------------------------------------------------


def front_matter():
    text = AGENT.read_text(encoding="utf-8")
    return yaml.safe_load(re.match(r"^---\n(.*?)\n---\n", text, re.S).group(1))


def test_the_reviewer_cannot_edit_or_write():
    tools = {t.strip() for t in front_matter()["tools"].split(",")}
    assert tools == {"Read", "Grep", "Glob", "Bash"}


def test_its_bash_calls_go_through_the_read_only_hook():
    hooks = front_matter()["hooks"]["PreToolUse"]
    assert hooks[0]["matcher"] == "Bash"
    assert "agent-hooks/read_only_commands.py" in hooks[0]["hooks"][0]["command"]


def test_every_file_it_points_to_exists():
    text = AGENT.read_text(encoding="utf-8")
    for path in ["product-spec.md", "AGENTS.md", "leaderboard/dates.py", "ranking.py", "queries.py",
                 "tests/integration/test_contract_responses.py", "tests/conftest.py", "test_workflows.py"]:
        assert path in text
    for path in ["product-spec.md", "AGENTS.md", "backend/leaderboard/dates.py", "backend/leaderboard/ranking.py",
                 "backend/leaderboard/queries.py", "backend/tests/integration/test_contract_responses.py",
                 "backend/tests/conftest.py", "backend/tests/integration/test_workflows.py"]:
        assert (REPO / path).exists(), path
