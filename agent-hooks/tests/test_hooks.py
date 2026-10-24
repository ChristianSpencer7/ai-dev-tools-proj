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
