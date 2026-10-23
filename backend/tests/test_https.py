"""HTTPS behind a proxy (DJANGO_HTTPS=1): plain HTTP is redirected, except the container's own health check."""

import pytest
from django.conf import settings
from django.test import Client, override_settings

pytestmark = pytest.mark.django_db

BEHIND_HTTPS_PROXY = override_settings(
    SECURE_SSL_REDIRECT=True,
    SECURE_PROXY_SSL_HEADER=("HTTP_X_FORWARDED_PROTO", "https"),
    ALLOWED_HOSTS=["stepboard.example.com", "localhost"],
)


@BEHIND_HTTPS_PROXY
def test_plain_http_is_redirected_to_https():
    response = Client(HTTP_HOST="stepboard.example.com").get("/families")
    assert response.status_code == 301
    assert response["Location"] == "https://stepboard.example.com/families"


@BEHIND_HTTPS_PROXY
def test_requests_the_proxy_marks_as_https_are_served():
    """The proxy (Caddy, then nginx) passes X-Forwarded-Proto: https; without it every request would loop."""
    response = Client(HTTP_HOST="stepboard.example.com", HTTP_X_FORWARDED_PROTO="https").get("/families")
    assert response.status_code == 200


@BEHIND_HTTPS_PROXY
def test_the_health_check_is_not_redirected():
    """docker compose's health check calls http://localhost:8000/health directly, without the proxy."""
    response = Client(HTTP_HOST="localhost").get("/health")
    assert (response.status_code, response.json()) == (200, {"ok": True})


def test_https_protections_are_off_locally():
    """docker compose on a laptop runs with DEBUG off over plain HTTP; it must not redirect to HTTPS."""
    assert not settings.SECURE_SSL_REDIRECT
    assert not settings.SESSION_COOKIE_SECURE
    assert settings.SECURE_PROXY_SSL_HEADER is None
