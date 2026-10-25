"""Unexpected errors, through the HTTP API: a 500 must leave its cause in the logs (ops/diagnosis/README.md, finding 5).

In the database drill on production, the logs showed only "500" lines: with DEBUG off, Django sends request errors
to email (mail_admins), and none is set up. settings.LOGGING sends them to the console, which is the container's log.
"""

import io
import logging
from unittest import mock

import pytest
from django.db import OperationalError
from django.test import Client

pytestmark = pytest.mark.django_db


@pytest.fixture
def console():
    """What the django.request logger's console handler writes, as the container's log would show it."""
    handlers = [h for h in logging.getLogger("django.request").handlers if type(h) is logging.StreamHandler]
    assert handlers, "django.request has no console handler: a 500's cause would only go to (unset) admin email"
    captured = io.StringIO()
    old = [h.setStream(captured) for h in handlers]
    yield captured
    for handler, stream in zip(handlers, old):
        handler.setStream(stream)


def test_a_500_logs_its_cause_and_traceback(console):
    client = Client(raise_request_exception=False)
    down = OperationalError('connection to server at "db", port 5432 failed: Connection refused')
    with mock.patch("leaderboard.access.Family.objects.filter", side_effect=down):
        response = client.get("/family", headers={"X-Family-Code": "DEMO"})
    assert response.status_code == 500
    log = console.getvalue()
    assert "ERROR django.request: Internal Server Error: /family" in log
    assert 'OperationalError: connection to server at "db", port 5432 failed: Connection refused' in log
    assert "Traceback (most recent call last)" in log


def test_client_errors_are_not_logged_as_errors(console):
    """A 401, 404 or 422 is the client's mistake, not the server's: no error lines for those."""
    client = Client()
    assert client.get("/families/999").status_code == 401  # no code
    assert client.get("/families/999", headers={"X-Family-Code": "SPEN23"}).status_code == 404
    assert client.post("/families", {"name": ""}, content_type="application/json").status_code == 422
    assert "ERROR" not in console.getvalue()
