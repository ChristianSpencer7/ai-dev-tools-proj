"""Every operation's real responses must match openapi.yaml: a documented status code, and a body that fits
the documented schema with no fields the schema doesn't list.

test_contract.py checks the routes; this file checks what they return, which is what the React app relies on.
"""

from datetime import date

import pytest
from django.conf import settings
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

WRONG = "WRONG2"  # a well-formed code no family has


@pytest.fixture
def ids(client):
    """A seeded demo family (code DEMO) with a member, steps and a saved digest; and an ordinary family, Spencers."""
    family = seed_demo_family(SEEDED_ON)
    member = Member.objects.filter(family=family).first()
    client.post(f"/families/{family.id}/digests", {"kind": "weekly"}, content_type="application/json")
    other = Family.objects.create(name="Spencers", start_date=SEEDED_ON, invite_code="SPEN23")
    return {"family": family.id, "member": member.id, "code": family.invite_code, "other": other.id, "other_code": "SPEN23"}


def calls(ids: dict) -> list[tuple[str, str, dict]]:
    """(contract path, method, request) for each case, in order. The request's "url" fills in the path's parameters,
    and "code" is sent as X-Family-Code. Wrong codes count toward the limit, so the 11 that count come first,
    then enough more to reach the limit, then the 429s."""
    f, m, ok, o = ids["family"], ids["member"], ids["code"], ids["other"]
    json = {"content_type": "application/json"}
    steps = lambda member, entries=None: {"member_id": member, "entries": [{"day": "2026-10-01", "steps": 5000}] if entries is None else entries}  # noqa: E731
    family_paths = [  # (contract path, method, url, body for a POST)
        ("/families/{family_id}", "get", f"/families/{f}", None),
        ("/families/{family_id}/members", "get", f"/families/{f}/members", None),
        ("/families/{family_id}/leaderboards/weekly", "get", f"/families/{f}/leaderboards/weekly", None),
        ("/families/{family_id}/leaderboards/all-time", "get", f"/families/{f}/leaderboards/all-time", None),
        ("/families/{family_id}/messages", "get", f"/families/{f}/messages", None),
        ("/families/{family_id}/digests", "post", f"/families/{f}/digests", {"kind": "weekly"}),
        ("/families/{family_id}/invite-code", "post", f"/families/{f}/invite-code", {}),
    ]
    member_paths = [
        ("/members/{member_id}/steps", "get", f"/members/{m}/steps", None),
        ("/steps", "post", "/steps", steps(m)),
    ]

    def call(path, method, url, body=None, code=None, **extra):
        request = {"url": url, **extra}
        if body is not None:
            request.update(data=body, **json)
        if code:
            request["code"] = code
        return (path, method, request)

    result = [
        # Open: no code needed
        call("/health", "get", "/health"),
        call("/families", "post", "/families", {"name": "Spencers"}),
        call("/families", "post", "/families", {"name": ""}),
        call("/families/join", "post", "/families/join", {"invite_code": "demo", "name": "Chris"}),
        call("/families/join", "post", "/families/join", {"invite_code": "NOPE", "name": "Chris"}),  # a wrong code: 1
        call("/families/join", "post", "/families/join", {"invite_code": "DEMO"}),
        # GET /family
        call("/family", "get", "/family", code="demo"),
        call("/family", "get", "/family"),
        call("/family", "get", "/family", code=WRONG),  # 2
        # Successes and the usual errors, with the right code
        call("/families/{family_id}", "get", f"/families/{f}", code=ok),
        call("/families/{family_id}/members", "get", f"/families/{f}/members", code=ok),
        call("/members/{member_id}/steps", "get", f"/members/{m}/steps", code=ok, data={"to": SEEDED_ON.isoformat()}),
        call("/members/{member_id}/steps", "get", f"/members/{m}/steps", code=ok, data={"to": "soon"}),
        call("/steps", "post", "/steps", steps(m), code=ok),
        call("/steps", "post", "/steps", steps(m, []), code=ok),
        call("/families/{family_id}/leaderboards/weekly", "get", f"/families/{f}/leaderboards/weekly", code=ok, data={"as_of": "2026-10-11"}),
        call("/families/{family_id}/leaderboards/weekly", "get", f"/families/{f}/leaderboards/weekly", code=ok, data={"as_of": "soon"}),
        call("/families/{family_id}/leaderboards/all-time", "get", f"/families/{f}/leaderboards/all-time", code=ok, data={"as_of": "2026-10-14"}),
        call("/families/{family_id}/leaderboards/all-time", "get", f"/families/{f}/leaderboards/all-time", code=ok, data={"as_of": "soon"}),
        call("/families/{family_id}/messages", "get", f"/families/{f}/messages", code=ok),
        call("/families/{family_id}/digests", "post", f"/families/{f}/digests", {"kind": "monthly"}, code=ok),
        call("/families/{family_id}/digests", "post", f"/families/{f}/digests", {"kind": "daily"}, code=ok),
        call("/families/{family_id}/invite-code", "post", f"/families/{o}/invite-code", {}, code=ids["other_code"]),
        call("/families/{family_id}/invite-code", "post", f"/families/{f}/invite-code", {}, code=ok),  # the demo's: 422
        # Unknown family or member, with a well-formed code
        *[call(p, meth, url.replace(f"/families/{f}", "/families/999"), body, code=ok) for p, meth, url, body in family_paths],
        call("/members/{member_id}/steps", "get", "/members/999/steps", code=ok),
        call("/steps", "post", "/steps", steps(999), code=ok),
        # No code: 401
        *[call(p, meth, url, body) for p, meth, url, body in family_paths + member_paths],
        # Another family's code: 403 (wrong codes 3 to 11)
        *[call(p, meth, url, body, code=WRONG) for p, meth, url, body in family_paths + member_paths],
    ]
    # Wrong codes so far: 11. Make it the limit, then every operation that counts them answers 429.
    result += [call("/family", "get", "/family", code=WRONG) for _ in range(settings.WRONG_CODE_LIMIT - 11)]
    result += [call(p, meth, url, body, code=ok) for p, meth, url, body in family_paths + member_paths]
    result += [
        call("/family", "get", "/family", code=ok),
        call("/families/join", "post", "/families/join", {"invite_code": "DEMO", "name": "Late"}),
    ]
    return result


def test_every_response_matches_openapi_yaml(plain_client, ids):
    problems, seen = [], set()
    for path, method, request in calls(ids):
        request = dict(request)
        url = request.pop("url")
        code = request.pop("code", None)
        headers = {"X-Family-Code": code} if code else None
        response = getattr(plain_client, method)(url, headers=headers, **request)
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
