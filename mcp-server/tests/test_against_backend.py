"""The MCP tools against the real Django app: a temporary database, seeded, served by `runserver`.

Needs the backend installed in a Python environment: this one (as in CI: `pip install -e ../backend`), or the one
named by STEPBOARD_BACKEND_PYTHON (locally: the repository's .venv). Skipped, with the reason, if neither has it,
except when STEPBOARD_REQUIRE_BACKEND=1 (CI), where a skip would hide that these tests never ran.
"""

import asyncio
import os
import socket
import subprocess
import sys
import time
from pathlib import Path

import httpx
import pytest
from mcp import Client, StdioServerParameters

from stepboard_mcp.config import Config
from stepboard_mcp.server import build_server

BACKEND = Path(__file__).resolve().parents[2] / "backend"
BACKEND_PYTHON = os.environ.get("STEPBOARD_BACKEND_PYTHON") or sys.executable


def backend_available() -> bool:
    check = subprocess.run([BACKEND_PYTHON, "-c", "import django, rest_framework"], capture_output=True)
    return check.returncode == 0 and (BACKEND / "manage.py").exists()


MISSING_BACKEND = f"the backend isn't installed for {BACKEND_PYTHON}; pip install -e ../backend or set STEPBOARD_BACKEND_PYTHON"
REQUIRED = os.environ.get("STEPBOARD_REQUIRE_BACKEND") == "1"

pytestmark = pytest.mark.skipif(not REQUIRED and not backend_available(), reason=MISSING_BACKEND)


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="module")
def app_url(tmp_path_factory):
    """The real app on a fresh, seeded SQLite database, for the duration of this file."""
    if not backend_available():
        pytest.fail(MISSING_BACKEND)
    database = tmp_path_factory.mktemp("backend") / "test.sqlite3"
    env = {**os.environ, "DATABASE_URL": f"sqlite:///{database.as_posix()}", "DISCORD_WEBHOOK_URL": "", "DJANGO_DEBUG": "1"}
    manage = [BACKEND_PYTHON, "manage.py"]
    for command in (["migrate", "-v", "0"], ["seed_demo"]):
        subprocess.run(manage + command, cwd=BACKEND, env=env, check=True, capture_output=True)
    port = free_port()
    process = subprocess.Popen(manage + ["runserver", f"127.0.0.1:{port}", "--noreload"], cwd=BACKEND, env=env,
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    url = f"http://127.0.0.1:{port}"
    try:
        for _ in range(60):
            try:
                if httpx.get(f"{url}/health", timeout=2).status_code == 200:
                    break
            except httpx.HTTPError:
                time.sleep(0.5)
        else:
            pytest.fail("the backend didn't start")
        yield url
    finally:
        process.terminate()
        process.wait(timeout=10)


def weekly_leader(url: str) -> str:
    family = next(f for f in httpx.get(f"{url}/families").json() if f["name"] == "Demo Family")
    return httpx.get(f"{url}/families/{family['id']}/leaderboards/weekly").json()["standings"][0]["name"]


def call(client_target, tool, args=None):
    async def go():
        async with Client(client_target, read_timeout_seconds=30) as client:
            result = await client.call_tool(tool, args or {})
            return " ".join(c.text for c in result.content if hasattr(c, "text")), result.is_error
    return asyncio.run(go())


def test_who_is_winning_and_logging_steps(app_url):
    """The backlog's done check: answer "who's winning this week?", then log steps for a member."""
    server = build_server(Config(api_url=app_url, family="Demo Family"))

    text, is_error = call(server, "get_leaderboard")
    assert not is_error
    assert text.splitlines()[0].startswith("📊 Week So Far") or text.splitlines()[0].startswith("🏆 Weekly Steps")
    assert text.splitlines()[1].startswith("Leader: ")

    assert call(server, "list_members") == ("Demo Family has 4 members: Alex, Dad, Mom, Sam.", False)

    text, is_error = call(server, "log_steps", {"member": "sam", "steps": 100_000})
    assert not is_error and text.startswith("Logged 100,000 steps for Sam on ") and "replacing" in text
    assert weekly_leader(app_url) == "Sam"  # the app itself shows the change
    assert "Leader: Sam" in call(server, "get_leaderboard")[0]


def test_the_apps_checks_still_apply(app_url):
    server = build_server(Config(api_url=app_url, family="Demo Family"))
    text, is_error = call(server, "log_steps", {"member": "Dad", "steps": 1, "day": "2099-01-01"})
    assert is_error and "These days haven't happened yet: 2099-01-01." in text


def test_over_stdio_as_claude_code_runs_it(app_url):
    """Starts the server as its own program, the way .mcp.json has Claude Code start it."""
    params = StdioServerParameters(
        command=sys.executable, args=["-m", "stepboard_mcp"],
        env={**os.environ, "STEPBOARD_API_URL": app_url, "STEPBOARD_FAMILY": "Demo Family"},
    )
    text, is_error = call(params, "get_leaderboard", {"board": "all_time"})
    assert not is_error and text.startswith("🏅 All-time Steps")
