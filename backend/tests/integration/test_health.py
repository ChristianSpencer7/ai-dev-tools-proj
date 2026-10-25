import pytest


@pytest.mark.django_db
def test_health_checks_the_database(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"ok": True}


def test_health_has_no_trailing_slash(client):
    # Paths match openapi.yaml exactly; Django must not redirect /health/ to /health.
    assert client.get("/health/").status_code == 404


@pytest.mark.django_db
def test_health_answers_head_too(plain_client):
    """Uptime monitors such as UptimeRobot often send HEAD; a 405 there made the live site look down (ops/runbook.md)."""
    response = plain_client.head("/health")  # no family code needed, like GET
    assert response.status_code == 200
    assert response.content == b""


def test_health_refuses_writes(client):
    assert client.post("/health").status_code == 405
