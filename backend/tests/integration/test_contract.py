"""openapi.yaml is the contract: the backend must serve exactly the routes it lists, and nothing else.

The schema drf-spectacular generates from the URL routes is compared with openapi.yaml. Change openapi.yaml
first, then the code (AGENTS.md).
"""

import contextlib
import io
from functools import cache
from pathlib import Path

import yaml
from drf_spectacular.generators import SchemaGenerator

# The repository root's openapi.yaml, found by looking upward, so moving this file doesn't break it.
SPEC_PATH = next(p / "openapi.yaml" for p in Path(__file__).resolve().parents if (p / "openapi.yaml").exists())
METHODS = {"get", "post", "put", "patch", "delete"}


@cache
def contract() -> dict:
    return yaml.safe_load(SPEC_PATH.read_text(encoding="utf-8"))


@cache
def served() -> dict:
    """The backend's routes as an OpenAPI schema, generated from the URL configuration."""
    # Our views don't declare response types, so drf-spectacular prints "unable to guess serializer"
    # warnings. They don't affect paths, methods or parameters, which are all these tests compare.
    with contextlib.redirect_stderr(io.StringIO()):
        return SchemaGenerator().get_schema(request=None, public=True)


def operations(schema: dict) -> set[str]:
    return {f"{method.upper()} {path}" for path, item in schema["paths"].items() for method in item if method in METHODS}


def resolve(schema: dict, obj: dict) -> dict:
    """Follows a {"$ref": "#/components/..."} link inside the same document."""
    if "$ref" not in obj:
        return obj
    target = schema
    for part in obj["$ref"].removeprefix("#/").split("/"):
        target = target[part]
    return target


def path_parameters(schema: dict) -> dict[str, list[str]]:
    """The path parameter names of every operation, e.g. {"GET /families/{family_id}": ["family_id"]}."""
    result = {}
    for path, item in schema["paths"].items():
        shared = item.get("parameters", [])  # openapi.yaml lists some parameters once for the whole path
        for method, operation in item.items():
            if method not in METHODS:
                continue
            params = [resolve(schema, p) for p in [*shared, *operation.get("parameters", [])]]
            result[f"{method.upper()} {path}"] = sorted(p["name"] for p in params if p["in"] == "path")
    return result


def test_the_backend_serves_exactly_the_routes_in_openapi_yaml():
    in_contract, in_backend = operations(contract()), operations(served())
    missing = sorted(in_contract - in_backend)
    extra = sorted(in_backend - in_contract)
    assert not missing and not extra, (
        "The backend and openapi.yaml disagree. Update openapi.yaml first, then the code.\n"
        f"  In openapi.yaml but not in the backend: {missing or 'none'}\n"
        f"  In the backend but not in openapi.yaml: {extra or 'none'}"
    )


def test_path_parameters_match():
    in_contract, in_backend = path_parameters(contract()), path_parameters(served())
    different = {
        operation: {"openapi.yaml": in_contract[operation], "backend": in_backend[operation]}
        for operation in in_contract.keys() & in_backend.keys()
        if in_contract[operation] != in_backend[operation]
    }
    assert not different, f"Path parameter names differ: {different}"


def test_the_contract_is_well_formed():
    spec = contract()
    assert spec["openapi"].startswith("3.1")
    operation_ids = [op["operationId"] for item in spec["paths"].values() for m, op in item.items() if m in METHODS]
    assert len(operation_ids) == len(set(operation_ids)), "Every operationId must be unique"
    assert len(operation_ids) == len(operations(spec))
