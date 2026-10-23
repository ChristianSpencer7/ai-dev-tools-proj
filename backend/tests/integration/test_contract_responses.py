"""Every operation's real responses must match openapi.yaml: a documented status code, and a body that fits
the documented schema with no fields the schema doesn't list.

test_contract.py checks the routes; this file checks what they return, which is what the React app relies on.
"""

from datetime import date

import pytest
from jsonschema import Draft202012Validator
from referencing import Registry, Resource
from referencing.jsonschema import DRAFT202012

from leaderboard.models import Family, Member, StepEntry
from leaderboard.seed import seed_demo_family
from test_contract import METHODS, contract

pytestmark = pytest.mark.django_db

SPEC_URI = "urn:openapi"  # the name the validator knows openapi.yaml by, so "#/components/..." links resolve
SEEDED_ON = date(2026, 10, 14)


def pointer(*parts: str) -> str:
    """A JSON pointer into openapi.yaml, escaping "/" in path names: /paths/~1families/get/..."""
    return "/" + "/".join(str(p).replace("~", "~0").replace("/", "~1") for p in parts)


def documented_response(path: str, method: str, status: int) -> str | None:
    """The JSON pointer to the response object openapi.yaml documents, or None if it doesn't."""
    responses = contract()["paths"][path][method]["responses"]
    if str(status) not in responses:
        return None
    response = responses[str(status)]
    if "$ref" in response:  # e.g. #/components/responses/NotFound
        return response["$ref"].removeprefix("#")
    return pointer("paths", path, method, "responses", status)


def resolve(ref_or_schema: dict) -> dict:
    target = ref_or_schema
    while "$ref" in target:
        node = contract()
        for part in target["$ref"].removeprefix("#/").split("/"):
            node = node[part.replace("~1", "/").replace("~0", "~")]
        target = node
    return target


def undeclared_fields(value, schema: dict, where: str = "body") -> list[str]:
    """Fields in the response that the schema doesn't list (schemas allow extras unless told otherwise)."""
    schema = resolve(schema)
    if "allOf" in schema:  # e.g. Family = FamilySummary + invite_code
        merged = {"type": "object", "properties": {}}
        for part in schema["allOf"]:
            merged["properties"].update(resolve(part).get("properties", {}))
        schema = merged
    if isinstance(value, list) and "items" in schema:
        return [f for i, item in enumerate(value) for f in undeclared_fields(item, schema["items"], f"{where}[{i}]")]
    if isinstance(value, dict) and "properties" in schema:
        problems = [f"{where}.{key}" for key in value if key not in schema["properties"]]
        for key, sub in schema["properties"].items():
            if key in value:
                problems += undeclared_fields(value[key], sub, f"{where}.{key}")
        return problems
    return []


VALIDATOR_REGISTRY = Registry().with_resource(SPEC_URI, Resource.from_contents(contract(), default_specification=DRAFT202012))


def check_against_contract(path: str, method: str, response) -> None:
    status = response.status_code
    documented = documented_response(path, method, status)
    assert documented, (
        f"{method.upper()} {path} returned {status}, which openapi.yaml doesn't document "
        f"(it lists {sorted(contract()['paths'][path][method]['responses'])}). Update openapi.yaml first."
    )
    content = resolve({"$ref": "#" + documented}).get("content", {}).get("application/json")
    if not content:
        return
    body = response.json()
    schema_pointer = documented + "/content/application~1json/schema"
    validator = Draft202012Validator(
        {"$ref": f"{SPEC_URI}#{schema_pointer}"},
        registry=VALIDATOR_REGISTRY,
        format_checker=Draft202012Validator.FORMAT_CHECKER,  # dates must be real YYYY-MM-DD dates
    )
    errors = [f"{'.'.join(map(str, e.absolute_path)) or 'body'}: {e.message}" for e in validator.iter_errors(body)]
    assert not errors, f"{method.upper()} {path} ({status}) doesn't match openapi.yaml: {errors}"
    extra = undeclared_fields(body, content["schema"])
    assert not extra, f"{method.upper()} {path} ({status}) returns fields openapi.yaml doesn't list: {extra}"


# --- The calls: every documented operation, with its success and error cases -------------------------


@pytest.fixture
def ids(client):
    """A seeded demo family plus a joined member with steps and a saved digest."""
    family = seed_demo_family(SEEDED_ON)
    member = Member.objects.filter(family=family).first()
    client.post(f"/families/{family.id}/digests", {"kind": "weekly"}, content_type="application/json")
    return {"family": family.id, "member": member.id}


def calls(ids: dict) -> list[tuple[str, str, dict]]:
    """(contract path, method, request) for each case. The request's "url" fills in the path's parameters."""
    f, m = ids["family"], ids["member"]
    json = {"content_type": "application/json"}
    return [
        ("/health", "get", {"url": "/health"}),
        ("/families", "get", {"url": "/families"}),
        ("/families", "post", {"url": "/families", "data": {"name": "Spencers"}, **json}),
        ("/families", "post", {"url": "/families", "data": {"name": ""}, **json}),
        ("/families/join", "post", {"url": "/families/join", "data": {"invite_code": "demo", "name": "Chris"}, **json}),
        ("/families/join", "post", {"url": "/families/join", "data": {"invite_code": "NOPE", "name": "Chris"}, **json}),
        ("/families/join", "post", {"url": "/families/join", "data": {"invite_code": "DEMO"}, **json}),
        ("/families/{family_id}", "get", {"url": f"/families/{f}"}),
        ("/families/{family_id}", "get", {"url": "/families/999"}),
        ("/families/{family_id}/members", "get", {"url": f"/families/{f}/members"}),
        ("/families/{family_id}/members", "get", {"url": "/families/999/members"}),
        ("/members/{member_id}/steps", "get", {"url": f"/members/{m}/steps", "data": {"to": SEEDED_ON.isoformat()}}),
        ("/members/{member_id}/steps", "get", {"url": "/members/999/steps"}),
        ("/members/{member_id}/steps", "get", {"url": f"/members/{m}/steps", "data": {"to": "soon"}}),
        ("/steps", "post", {"url": "/steps", "data": {"member_id": m, "entries": [{"day": "2026-10-01", "steps": 5000}]}, **json}),
        ("/steps", "post", {"url": "/steps", "data": {"member_id": 999, "entries": [{"day": "2026-10-01", "steps": 1}]}, **json}),
        ("/steps", "post", {"url": "/steps", "data": {"member_id": m, "entries": []}, **json}),
        ("/families/{family_id}/leaderboards/weekly", "get", {"url": f"/families/{f}/leaderboards/weekly", "data": {"as_of": "2026-10-11"}}),
        ("/families/{family_id}/leaderboards/weekly", "get", {"url": "/families/999/leaderboards/weekly"}),
        ("/families/{family_id}/leaderboards/weekly", "get", {"url": f"/families/{f}/leaderboards/weekly", "data": {"as_of": "soon"}}),
        ("/families/{family_id}/leaderboards/all-time", "get", {"url": f"/families/{f}/leaderboards/all-time", "data": {"as_of": "2026-10-14"}}),
        ("/families/{family_id}/leaderboards/all-time", "get", {"url": "/families/999/leaderboards/all-time"}),
        ("/families/{family_id}/leaderboards/all-time", "get", {"url": f"/families/{f}/leaderboards/all-time", "data": {"as_of": "soon"}}),
        ("/families/{family_id}/messages", "get", {"url": f"/families/{f}/messages"}),
        ("/families/{family_id}/messages", "get", {"url": "/families/999/messages"}),
        ("/families/{family_id}/digests", "post", {"url": f"/families/{f}/digests", "data": {"kind": "monthly"}, **json}),
        ("/families/{family_id}/digests", "post", {"url": "/families/999/digests", "data": {"kind": "weekly"}, **json}),
        ("/families/{family_id}/digests", "post", {"url": f"/families/{f}/digests", "data": {"kind": "daily"}, **json}),
    ]


def test_every_response_matches_openapi_yaml(client, ids):
    problems, seen = [], set()
    for path, method, request in calls(ids):
        request = dict(request)
        url = request.pop("url")
        response = getattr(client, method)(url, **request)
        seen.add((path, method, response.status_code))
        try:
            check_against_contract(path, method, response)
        except AssertionError as error:
            problems.append(str(error).split("\nassert")[0])
    assert not problems, "\n".join(problems)

    # Every documented operation was called, and every response it documents was produced at least once.
    documented = {
        (path, method, int(status))
        for path, item in contract()["paths"].items()
        for method, op in item.items() if method in METHODS
        for status in op["responses"]
    }
    assert documented <= seen, f"Not exercised here; add a call: {sorted(documented - seen)}"


def test_the_check_rejects_a_wrong_body(client, ids):
    """A sanity check of the checker itself, on a hand-made bad response."""

    class Fake:
        status_code = 200

        @staticmethod
        def json():
            return [{"id": 1, "family": 3, "name": "Dad"}]  # family instead of family_id

    with pytest.raises(AssertionError, match="family_id"):
        check_against_contract("/families/{family_id}/members", "get", Fake())
