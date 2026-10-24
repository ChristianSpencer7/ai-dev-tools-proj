"""Where the server finds the app, and which family it works with. Both come from environment variables."""

import os
from dataclasses import dataclass
from urllib.parse import urlsplit

LOCAL_API_URL = "http://localhost:8000"  # `python manage.py runserver`
DEFAULT_FAMILY = "Demo Family"


@dataclass(frozen=True)
class Config:
    # The app's API. Local by default: log_steps changes data and the API has no logins, so pointing at the
    # live site (https://159-89-228-242.sslip.io/api) has to be a deliberate choice.
    api_url: str
    # The one family the tools read and write. Members are found by name within it, so the assistant can't
    # log steps into another family by accident.
    family: str

    @classmethod
    def from_env(cls) -> "Config":
        api_url = (os.environ.get("STEPBOARD_API_URL") or LOCAL_API_URL).rstrip("/")
        check_api_url(api_url)
        return cls(api_url=api_url, family=os.environ.get("STEPBOARD_FAMILY") or DEFAULT_FAMILY)


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
