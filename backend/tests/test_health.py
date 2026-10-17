import pytest


@pytest.mark.django_db
def test_health_checks_the_database(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"ok": True}


def test_health_has_no_trailing_slash(client):
    # Paths match openapi.yaml exactly; Django must not redirect /health/ to /health.
    assert client.get("/health/").status_code == 404


def test_health_is_get_only(client):
    assert client.post("/health").status_code == 405
