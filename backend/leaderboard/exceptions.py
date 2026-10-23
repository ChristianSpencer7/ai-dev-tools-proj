"""Error responses in the shape openapi.yaml promises and the React API client reads."""

from rest_framework.exceptions import ValidationError
from rest_framework.views import exception_handler

# openapi.yaml's ValidationError response; DRF's default is 400.
VALIDATION_STATUS = 422


def flatten_errors(detail, path: str = "") -> list[str]:
    """Turn DRF's nested {"field": ["message"]} errors into lines like "name: This field is required."."""
    if isinstance(detail, dict):
        return [line for key, value in detail.items() for line in flatten_errors(value, join_path(path, key))]
    if isinstance(detail, list):
        if all(not isinstance(item, (dict, list)) for item in detail):
            return [f"{path}: {item}" if path else str(item) for item in detail]
        return [line for i, item in enumerate(detail) for line in flatten_errors(item, join_path(path, str(i)))]
    return [f"{path}: {detail}" if path else str(detail)]


def join_path(path: str, key: str) -> str:
    if key == "non_field_errors":  # errors about the whole body, not one field
        return path
    return f"{path}.{key}" if path else key


def api_exception_handler(exc, context):
    """Validation errors become 422 with one readable detail string. Other errors keep DRF's {"detail": ...}."""
    response = exception_handler(exc, context)
    if response is not None and isinstance(exc, ValidationError):
        response.status_code = VALIDATION_STATUS
        response.data = {"detail": " ".join(flatten_errors(exc.detail))}  # messages end in periods
    return response
