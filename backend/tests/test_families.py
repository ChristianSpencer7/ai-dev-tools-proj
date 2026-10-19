"""Families, members and joining by invite code, through the HTTP API."""

from datetime import date

import pytest
from django.contrib.auth.models import User
from django.test import Client

from leaderboard.dates import today_eastern
from leaderboard.invites import INVITE_ALPHABET
from leaderboard.models import Family, Member

pytestmark = pytest.mark.django_db


def post(client, url, data):
    return client.post(url, data, content_type="application/json")


@pytest.fixture
def family(client):
    return post(client, "/families", {"name": "Spencers"}).json()


def test_create_join_and_unknown_code(client):
    """The backlog's done check: create a family, join it with a lowercase code, 404 for an unknown code."""
    family = post(client, "/families", {"name": "Spencers"}).json()

    joined = post(client, "/families/join", {"invite_code": family["invite_code"].lower(), "name": "Chris"})
    assert joined.status_code == 201
    assert joined.json() == {"id": joined.json()["id"], "family_id": family["id"], "name": "Chris"}

    unknown = post(client, "/families/join", {"invite_code": "NOPE", "name": "Chris"})
    assert unknown.status_code == 404
    assert unknown.json() == {"detail": "No family has that invite code"}


def test_create_family_defaults(client):
    response = post(client, "/families", {"name": "  Spencers  "})
    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "Spencers"
    assert body["start_date"] == today_eastern().isoformat()
    assert len(body["invite_code"]) == 6
    assert set(body["invite_code"]) <= set(INVITE_ALPHABET)


def test_create_family_with_start_date(client):
    body = post(client, "/families", {"name": "Spencers", "start_date": "2026-10-01"}).json()
    assert body["start_date"] == "2026-10-01"
    assert Family.objects.get(pk=body["id"]).start_date == date(2026, 10, 1)


def test_clients_cannot_choose_the_invite_code(client):
    body = post(client, "/families", {"name": "Spencers", "invite_code": "MINE00"}).json()
    assert body["invite_code"] != "MINE00"


def test_family_list_leaves_out_invite_codes(client, family):
    post(client, "/families", {"name": "Grandparents"})
    listed = client.get("/families").json()
    assert [f["name"] for f in listed] == ["Spencers", "Grandparents"]
    assert all(set(f) == {"id", "name", "start_date"} for f in listed)


def test_get_family(client, family):
    assert client.get(f"/families/{family['id']}").json() == family


def test_unknown_family(client):
    for url in ["/families/999", "/families/999/members"]:
        response = client.get(url)
        assert response.status_code == 404
        assert response.json() == {"detail": "Family not found"}


def test_members_are_ordered_by_name_and_stay_in_their_family(client, family):
    for name in ["Sam", "Alex", "Mom"]:
        post(client, "/families/join", {"invite_code": family["invite_code"], "name": name})
    other = post(client, "/families", {"name": "Neighbors"}).json()
    post(client, "/families/join", {"invite_code": other["invite_code"], "name": "Stranger"})

    members = client.get(f"/families/{family['id']}/members").json()
    assert [m["name"] for m in members] == ["Alex", "Mom", "Sam"]
    assert {m["family_id"] for m in members} == {family["id"]}


@pytest.mark.parametrize(
    ("url", "data", "detail"),
    [
        ("/families", {"name": "   "}, "name: This field may not be blank."),
        ("/families", {"name": "x" * 81}, "name: Ensure this field has no more than 80 characters."),
        ("/families", {}, "name: This field is required."),
        ("/families/join", {"invite_code": "DEMO", "name": "x" * 41}, "name: Ensure this field has no more than 40 characters."),
        ("/families/join", {"invite_code": "DEMO"}, "name: This field is required."),
    ],
)
def test_validation_errors_are_422_with_a_detail_message(client, url, data, detail):
    response = post(client, url, data)
    assert response.status_code == 422
    assert response.json() == {"detail": detail}
    assert not Family.objects.exists() and not Member.objects.exists()  # nothing saved


def test_wrong_method(client):
    assert client.get("/families/join").status_code == 405
    assert client.post("/families/1/members").status_code == 405


def test_admin_login_does_not_trigger_csrf_checks():
    """A browser logged into the admin can still use the API (no DRF session auth)."""
    browser = Client(enforce_csrf_checks=True)
    browser.force_login(User.objects.create_superuser("admin", "", "pass"))
    assert post(browser, "/families", {"name": "Spencers"}).status_code == 201
