"""Where the server finds the app, and which family it works with. Both come from environment variables."""

import os
from dataclasses import dataclass

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
        return cls(
            api_url=(os.environ.get("STEPBOARD_API_URL") or LOCAL_API_URL).rstrip("/"),
            family=os.environ.get("STEPBOARD_FAMILY") or DEFAULT_FAMILY,
        )
