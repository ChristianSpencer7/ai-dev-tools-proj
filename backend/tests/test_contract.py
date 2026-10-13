"""openapi.yaml is the contract. The backend must serve exactly the paths and methods it lists."""

from pathlib import Path

import yaml

from stepboard.api import create_app

SPEC = Path(__file__).resolve().parents[2] / "openapi.yaml"
METHODS = {"get", "post", "put", "patch", "delete"}


def operations(paths: dict) -> set[tuple[str, str]]:
    return {(path, method) for path, item in paths.items() for method in item if method in METHODS}


def test_backend_matches_openapi_yaml(settings):
    spec = yaml.safe_load(SPEC.read_text(encoding="utf-8"))
    served = create_app(settings).openapi()
    assert operations(served["paths"]) == operations(spec["paths"])
