"""The invite code as the family's password, through the HTTP API (leaderboard/access.py, openapi.yaml FamilyCode).

These use plain_client, which sends no code unless a test gives one, so they test the checks the everyday test
client skips. The whole journey is in test_workflows.py; the 401/403/429 bodies are checked in
test_contract_responses.py.
"""

from datetime import date

import pytest
from django.conf import settings

from leaderboard.admin import FamilyForm
from leaderboard.invites import CODE_LENGTH, INVITE_ALPHABET
from leaderboard.models import Family, Member
from test_contract import METHODS, contract

pytestmark = pytest.mark.django_db

DAY = "2026-10-01"


@pytest.fixture
def spencers():
    family = Family.objects.create(name="Spencers", start_date=date(2026, 9, 1), invite_code="SPEN23")
    return family, Member.objects.create(family=family, name="Chris")


@pytest.fixture
def neighbors():
    family = Family.objects.create(name="Neighbors", start_date=date(2026, 9, 1), invite_code="NEIG45")
    return family, Member.objects.create(family=family, name="Pat")


def send(client, method, url, code=None, body=None, **extra):
    headers = {"X-Family-Code": code} if code else None
    if method == "get":
        return client.get(url, headers=headers, **extra)
    return client.post(url, body if body is not None else {}, content_type="application/json", headers=headers, **extra)


# --- The contract's security is what the backend does --------------------------------------------


def test_every_operation_needs_a_code_exactly_when_openapi_yaml_says(plain_client, spencers):
    """A new endpoint that forgets the check, or an open one that starts asking for a code, fails here."""
    family, member = spencers
    spec = contract()
    default = spec.get("security", [])
    bodies = {"/families": {"name": "Spencers"}, "/families/join": {"invite_code": "SPEN23", "name": "Sam"},
              "/steps": {"member_id": member.id, "entries": [{"day": DAY, "steps": 1}]},
              "/families/{family_id}/digests": {"kind": "weekly"}}
    wrong = []
    for path, item in spec["paths"].items():
        url = path.replace("{family_id}", str(family.id)).replace("{member_id}", str(member.id))
        for method, operation in item.items():
            if method not in METHODS:
                continue
            needs_code = operation.get("security", default) != []
            status = send(plain_client, method, url, body=bodies.get(path)).status_code
            if needs_code != (status == 401):
                wrong.append(f"{method.upper()} {path}: openapi.yaml says {'a code' if needs_code else 'no code'}, got {status}")
    assert not wrong, "\n".join(wrong)


# --- Right code, wrong code ----------------------------------------------------------------------


def test_the_right_code_in_any_case_opens_the_family(plain_client, spencers):
    family, _ = spencers
    for code in ["SPEN23", "spen23", "  Spen23 "]:
        assert send(plain_client, "get", f"/families/{family.id}/members", code).status_code == 200


def test_another_familys_code_opens_nothing_of_this_one(plain_client, spencers, neighbors):
    (family, member), (_, pat) = spencers, neighbors
    for method, url, body in [
        ("get", f"/families/{family.id}", None),
        ("get", f"/families/{family.id}/leaderboards/weekly", None),
        ("get", f"/members/{member.id}/steps", None),
        ("post", "/steps", {"member_id": member.id, "entries": [{"day": DAY, "steps": 99_999}]}),
        ("post", f"/families/{family.id}/digests", {"kind": "weekly"}),
        ("post", f"/families/{family.id}/invite-code", {}),
    ]:
        response = send(plain_client, method, url, "NEIG45", body)
        assert (response.status_code, response.json()) == (403, {"detail": "That invite code isn't this family's"}), url
    assert not member.steps.exists()  # the Neighbors couldn't log steps for Chris
    assert Family.objects.get(pk=family.id).invite_code == "SPEN23"  # nor change the Spencers' code


def test_no_code_is_401_with_a_message_saying_what_is_needed(plain_client, spencers):
    family, _ = spencers
    response = send(plain_client, "get", f"/families/{family.id}")
    assert (response.status_code, response.json()) == (
        401, {"detail": "This needs the family's invite code, in the X-Family-Code header"}
    )


def test_the_family_for_a_code_that_opens_none(plain_client, spencers):
    response = send(plain_client, "get", "/family", "WRONG2")
    assert (response.status_code, response.json()) == (403, {"detail": "No family has that invite code"})


# --- A new code ----------------------------------------------------------------------------------


def test_a_new_code_replaces_the_old_one(plain_client, spencers):
    family, member = spencers
    response = send(plain_client, "post", f"/families/{family.id}/invite-code", "SPEN23")
    assert response.status_code == 200
    new = response.json()
    assert set(new) == {"id", "name", "start_date", "invite_code"}
    assert new["invite_code"] != "SPEN23"
    assert len(new["invite_code"]) == CODE_LENGTH and set(new["invite_code"]) <= set(INVITE_ALPHABET)
    assert send(plain_client, "get", f"/members/{member.id}/steps", "SPEN23").status_code == 403
    assert send(plain_client, "get", f"/members/{member.id}/steps", new["invite_code"]).status_code == 200
    assert Member.objects.filter(family=family).count() == 1  # members stay members


def test_the_demo_familys_code_cant_be_changed(plain_client):
    demo = Family.objects.create(name="Demo Family", start_date=date(2026, 9, 1), invite_code="DEMO")
    response = send(plain_client, "post", f"/families/{demo.id}/invite-code", "DEMO")
    assert (response.status_code, response.json()) == (
        422, {"detail": "The Demo Family's invite code can't be changed: it's public on purpose."}
    )
    assert Family.objects.get(pk=demo.id).invite_code == "DEMO"


# --- The limit on wrong codes --------------------------------------------------------------------


def test_too_many_wrong_codes_and_even_the_right_one_waits(plain_client, spencers):
    family, _ = spencers
    url = f"/families/{family.id}/members"
    for _ in range(settings.WRONG_CODE_LIMIT):
        assert send(plain_client, "get", url, "WRONG2").status_code == 403
    response = send(plain_client, "get", url, "SPEN23")
    assert (response.status_code, response.json()) == (429, {"detail": "Too many wrong invite codes; try again in a minute"})


def test_wrong_codes_when_joining_count_too(plain_client, spencers):
    for _ in range(settings.WRONG_CODE_LIMIT):
        assert send(plain_client, "post", "/families/join", body={"invite_code": "WRONG2", "name": "Guess"}).status_code == 404
    assert send(plain_client, "post", "/families/join", body={"invite_code": "SPEN23", "name": "Sam"}).status_code == 429


def test_one_visitors_wrong_codes_dont_block_another(plain_client, spencers):
    """Behind Caddy, every request reaches Django from the same address; X-Forwarded-For says who it was."""
    family, _ = spencers
    url = f"/families/{family.id}/members"
    guesser = {"HTTP_X_FORWARDED_FOR": "81.2.69.142"}
    for _ in range(settings.WRONG_CODE_LIMIT):
        send(plain_client, "get", url, "WRONG2", **guesser)
    assert send(plain_client, "get", url, "SPEN23", **guesser).status_code == 429
    assert send(plain_client, "get", url, "SPEN23", HTTP_X_FORWARDED_FOR="81.2.69.143").status_code == 200


def test_private_addresses_in_x_forwarded_for_are_skipped(plain_client, spencers):
    """The visitor is the last public address: one a visitor adds in front, or a proxy's after, doesn't count."""
    family, _ = spencers
    url = f"/families/{family.id}/members"
    for _ in range(settings.WRONG_CODE_LIMIT):
        send(plain_client, "get", url, "WRONG2", HTTP_X_FORWARDED_FOR="81.2.69.142, 172.18.0.5")
    assert send(plain_client, "get", url, "SPEN23", HTTP_X_FORWARDED_FOR="81.2.69.142").status_code == 429
    assert send(plain_client, "get", url, "SPEN23", HTTP_X_FORWARDED_FOR="8.8.8.8, 81.2.69.143").status_code == 200


def test_the_right_code_doesnt_count(plain_client, spencers):
    family, _ = spencers
    for _ in range(settings.WRONG_CODE_LIMIT + 5):
        assert send(plain_client, "get", f"/families/{family.id}/members", "SPEN23").status_code == 200


# --- The admin saves only usable codes -----------------------------------------------------------


@pytest.mark.parametrize(("typed", "saved"), [("abc234", "ABC234"), (" spen23 ", "SPEN23"), ("demo", "DEMO")])
def test_the_admin_saves_codes_in_capitals(typed, saved):
    form = FamilyForm(data={"name": "Spencers", "start_date": "2026-10-01", "invite_code": typed})
    assert form.is_valid(), form.errors
    assert form.cleaned_data["invite_code"] == saved


@pytest.mark.parametrize("typed", ["ABC23", "ABCD234", "ABC10I", "ABC 23"])
def test_the_admin_refuses_codes_that_couldnt_be_generated(typed):
    form = FamilyForm(data={"name": "Spencers", "start_date": "2026-10-01", "invite_code": typed})
    assert not form.is_valid()
    assert "invite_code" in form.errors
