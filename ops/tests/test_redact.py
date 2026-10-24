"""ops/redact.py: what's replaced, what's kept. Cases come from real server output (ops/diagnosis/)."""

import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from redact import redact  # noqa: E402

SERVER = frozenset({"159.89.228.242"})


@pytest.mark.parametrize(
    ("line", "expected"),
    [
        # Visitors: replaced, in every form the logs use
        ('"remote_ip":"81.2.69.142"', '"remote_ip":"<ip>"'),
        ('"remote":"23.178.112.211:33955"', '"remote":"<ip>:33955"'),  # Caddy, with a port (missed by the first version)
        ('"client_ip":"2a00:1450:4009:81f::200e"', '"client_ip":"<ip>"'),
        ("[2606:4700::6810:84e5]:443", "[<ip>]:443"),
        ('"GET / HTTP/1.1" 200 408 "-" "curl/8.5.0" "81.2.69.142"', '"GET / HTTP/1.1" 200 408 "-" "curl/8.5.0" "<ip>"'),
        ("8.8.8.8, 100.64.1.1", "<ip>, <ip>"),
        ("http://81.2.69.142/x", "http://<ip>/x"),
        # Kept: Docker's network, loopback, the server itself
        ("172.18.0.5 - - GET /health", "172.18.0.5 - - GET /health"),
        ("10.0.0.2 and 192.168.1.20", "10.0.0.2 and 192.168.1.20"),
        ("127.0.0.1 ::1 and listening on ::", "127.0.0.1 ::1 and listening on ::"),
        ('"curl/8.5.0" "159.89.228.242"', '"curl/8.5.0" "159.89.228.242"'),
        # Not addresses at all: versions, times, timestamps (the first version replaced the browser versions)
        ("Chrome/130.0.0.0 Safari/537.36 OPR/115.0.0.0", "Chrome/130.0.0.0 Safari/537.36 OPR/115.0.0.0"),
        ("nginx/1.30.6 PostgreSQL 16.15", "nginx/1.30.6 PostgreSQL 16.15"),
        ("at 08:01:02, ts 1792740447.9445271", "at 08:01:02, ts 1792740447.9445271"),
        ("2026-10-24T08:57:44.686246588Z", "2026-10-24T08:57:44.686246588Z"),
        # Secrets
        ("posting to https://discord.com/api/webhooks/123456/abc-DEF_ghi failed", "posting to <discord-webhook-url> failed"),
        ("https://discordapp.com/api/webhooks/1/x", "<discord-webhook-url>"),
        ("password=hunter2 secret: abc123 TOKEN=xyz", "password=<redacted> secret: <redacted> TOKEN=<redacted>"),
    ],
)
def test_redact(line, expected):
    assert redact(line, SERVER) == expected


def test_as_a_pipe_with_keep():
    script = Path(__file__).resolve().parents[1] / "redact.py"
    result = subprocess.run([sys.executable, str(script), "--keep", "159.89.228.242"], input="159.89.228.242 81.2.69.142\n",
                            capture_output=True, text=True, check=True)
    assert result.stdout == "159.89.228.242 <ip>\n"
