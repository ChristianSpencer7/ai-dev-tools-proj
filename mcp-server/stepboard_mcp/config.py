"""Where the server finds the app, and which family it works with. Both come from environment variables."""

import os
from dataclasses import dataclass, field
from urllib.parse import urlsplit

LOCAL_API_URL = "http://localhost:8000"  # `python manage.py runserver`
DEMO_INVITE_CODE = "DEMO"  # the Demo Family's code, public on purpose


@dataclass(frozen=True)
class Config:
    # The app's API. Local by default: log_steps changes data and the API has no logins, so pointing at the
    # live site (https://159-89-228-242.sslip.io/api) has to be a deliberate choice.
    api_url: str
    # The one family the tools read and write: the family this invite code opens. A family's code is its password
    # (openapi.yaml, FamilyCode), so it's a secret like the webhook URL: kept out of repr() and so out of logs and
    # tracebacks, and never put in the assistant's instructions. Members are found by name within the family, so
    # the assistant can't log steps into another family by accident.
    invite_code: str = field(repr=False)

    @classmethod
    def from_env(cls) -> "Config":
        api_url = (os.environ.get("STEPBOARD_API_URL") or LOCAL_API_URL).rstrip("/")
        check_api_url(api_url)
        code = (os.environ.get("STEPBOARD_INVITE_CODE") or DEMO_INVITE_CODE).strip().upper()
        return cls(api_url=api_url, invite_code=code)


LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1"}


def check_api_url(url: str) -> None:
    """HTTPS, or plain HTTP only to this machine: names and step totals shouldn't cross a network unencrypted."""
    parts = urlsplit(url)
    if parts.scheme == "https" and parts.hostname:
        return
    if parts.scheme == "http" and parts.hostname in LOCAL_HOSTS:
        return
    raise ValueError(
        f"STEPBOARD_API_URL must be an https:// address, or http:// to this machine (localhost); got {url!r}."
    )
