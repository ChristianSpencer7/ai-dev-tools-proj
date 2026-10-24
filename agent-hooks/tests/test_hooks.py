"""The agent hooks, run the way Claude Code runs them: as their own program, with the tool call as JSON on stdin."""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

HOOKS = Path(__file__).resolve().parents[1]
REPO = HOOKS.parent


def run_hook(script, tool_input, tool_name="Edit", project=REPO, extra_env=None, raw=None):
    event = {"hook_event_name": "PreToolUse", "tool_name": tool_name, "tool_input": tool_input, "cwd": str(project)}
    env = {**os.environ, "CLAUDE_PROJECT_DIR": str(project), **(extra_env or {})}
    result = subprocess.run([sys.executable, str(HOOKS / script)], input=raw if raw is not None else json.dumps(event),
                            capture_output=True, text=True, env=env, timeout=200)
    return result.returncode, result.stderr


def guard(path, **kwargs):
    return run_hook("guard_files.py", {"file_path": str(REPO / path)}, **kwargs)


# --- guard_files.py (PreToolUse) -----------------------------------------------------------------


@pytest.mark.parametrize("path", [".env", "backend/.env", ".env.production", "backend/db.sqlite3",
                                  "backend/leaderboard/migrations/0001_initial.py"])
def test_protected_files_are_blocked_with_a_reason(path):
    code, reason = guard(path)
    assert code == 2
    assert reason.startswith("Blocked by agent-hooks/guard_files.py: ")


def test_a_committed_migration_gets_the_fix_in_its_reason():
    _, reason = guard("backend/leaderboard/migrations/0001_initial.py")
    assert "already committed" in reason and "makemigrations" in reason


@pytest.mark.parametrize("path", [".env.example", "backend/leaderboard/models.py", "docs/plan.md",
                                  "backend/leaderboard/migrations/0099_new_change.py",  # a new migration
                                  "backend/leaderboard/migrations/__init__.py"])
def test_everything_else_is_allowed(path):
    assert guard(path) == (0, "")


@pytest.mark.skipif(sys.platform != "win32", reason="backslashes are only path separators on Windows")
def test_windows_style_paths_are_checked_too():
    windows_path = str(REPO / ".env").replace("/", "\\")
    assert run_hook("guard_files.py", {"file_path": windows_path})[0] == 2


def test_files_outside_the_project_are_left_alone(tmp_path):
    assert run_hook("guard_files.py", {"file_path": str(tmp_path / ".env")})[0] == 0


def test_writes_are_guarded_like_edits():
    assert run_hook("guard_files.py", {"file_path": str(REPO / ".env"), "content": "X=1"}, tool_name="Write")[0] == 2


def test_bad_input_is_a_notice_not_a_block():
    code, message = run_hook("guard_files.py", {}, raw="not json")
    assert code == 1 and "wasn't JSON" in message


def shell(command, tool="Bash"):
    return run_hook("guard_files.py", {"command": command}, tool_name=tool)


@pytest.mark.parametrize(
    "command",
    [
        "cat .env",                                                       # reading secrets into the conversation
        "echo DISCORD_WEBHOOK_URL=https://example.com/hook >> .env",
        "cp .env.example .env",
        "grep SECRET backend/.env",
        "sed -i 's/max_length=80/max_length=90/' backend/leaderboard/migrations/0001_initial.py",
        "cd backend && sed -i.bak 's/a/b/' leaderboard/migrations/0002_alter_stepentry_steps_at_most_100000.py",
        "rm backend/leaderboard/migrations/0003_message_as_of.py",
        "python -c \"open('leaderboard/migrations/0001_initial.py', 'w').write('')\"",
        "rm backend/db.sqlite3",
        "echo x > db.sqlite3",
    ],
)
def test_shell_commands_that_touch_protected_files_are_blocked(command):
    code, reason = shell(command)
    assert code == 2 and reason.startswith("Blocked by agent-hooks/guard_files.py: ")


@pytest.mark.parametrize(
    "command",
    [
        "cat .env.example",
        "cat backend/leaderboard/migrations/0001_initial.py",              # reading a migration is fine
        "grep -n AlterField backend/leaderboard/migrations/0002_alter_stepentry_steps_at_most_100000.py 2>&1",
        "python manage.py makemigrations leaderboard",                    # the right way to change the schema
        "sed -i 's/a/b/' backend/leaderboard/migrations/0099_brand_new.py",  # a new, uncommitted migration
        "sqlite3 db.sqlite3 'select count(*) from leaderboard_family'",
        "ls backend > /dev/null",
        "git status --short 2>&1",
        "echo environment",                                               # contains "env" but not .env
        "python -m pytest -q",
    ],
)
def test_ordinary_shell_commands_are_allowed(command):
    assert shell(command) == (0, "")


@pytest.mark.parametrize(
    "command",
    ["Set-Content -Path .env -Value 'X=1'", r"Get-Content backend\.env",
     r"Remove-Item backend\leaderboard\migrations\0001_initial.py"],
)
def test_powershell_commands_are_checked_too(command):
    assert shell(command, tool="PowerShell")[0] == 2


def test_the_shell_reason_names_the_fix():
    _, reason = shell("sed -i 's/x/y/' backend/leaderboard/migrations/0001_initial.py")
    assert "already committed" in reason and "makemigrations" in reason


# --- contract_check.py (PostToolUse) -------------------------------------------------------------

BACKEND_PYTHON = {"STEPBOARD_BACKEND_PYTHON": sys.executable}  # this environment has the backend installed


def contract(path, project=REPO, extra_env=BACKEND_PYTHON):
    return run_hook("contract_check.py", {"file_path": str(project / path)}, project=project, extra_env=extra_env)


def test_other_files_are_not_checked():
    assert contract("docs/plan.md") == (0, "")


def test_a_matching_contract_passes_quietly():
    assert contract("openapi.yaml") == (0, "")


def test_drift_is_reported_to_claude(tmp_path):
    """A copy of the project whose openapi.yaml no longer lists /health, as if an agent had just removed it."""
    shutil.copytree(REPO / "backend", tmp_path / "backend",
                    ignore=shutil.ignore_patterns("__pycache__", "db.sqlite3", "staticfiles", "*.egg-info"))
    spec = (REPO / "openapi.yaml").read_text(encoding="utf-8")
    spec = spec.replace("  /health:\n    get:\n      operationId: health\n", "  /health:\n    x-removed:\n      operationId: health\n")
    (tmp_path / "openapi.yaml").write_text(spec, encoding="utf-8")

    code, message = contract("openapi.yaml", project=tmp_path)
    assert code == 2
    assert message.startswith("Contract check after editing openapi.yaml: openapi.yaml and the backend now disagree")
    assert "GET /health" in message
    assert "contract first" in message


def test_no_backend_environment_is_a_notice(tmp_path):
    code, message = contract("openapi.yaml", extra_env={"STEPBOARD_BACKEND_PYTHON": str(tmp_path / "missing-python")})
    assert code == 1 and "no backend environment" in message
