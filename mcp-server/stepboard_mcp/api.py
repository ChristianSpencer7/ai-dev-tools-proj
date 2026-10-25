"""A small client for the app's HTTP API: only the operations the tools need, with the paths in openapi.yaml."""

from datetime import date
from typing import Any

import httpx

TIMEOUT_SECONDS = 10


class ApiError(Exception):
    """Anything that went wrong talking to the app, in words the assistant can pass on."""

    def __init__(self, message: str, status: int | None = None):
        super().__init__(message)
        self.status = status


class StepboardApi:
    def __init__(self, base_url: str, invite_code: str, client: httpx.Client | None = None):
        self.base_url = base_url.rstrip("/")
        self.invite_code = invite_code  # sent as X-Family-Code with every request: the family's password
        # Tests pass a client with a fake transport; normally this talks to the real app.
        self.client = client or httpx.Client(timeout=TIMEOUT_SECONDS)

    def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        headers = {**kwargs.pop("headers", {}), "X-Family-Code": self.invite_code}
        try:
            response = self.client.request(method, f"{self.base_url}{path}", headers=headers, **kwargs)
        except httpx.HTTPError as error:
            raise ApiError(f"Can't reach the app at {self.base_url} ({type(error).__name__}). Is it running?") from error
        if response.is_success:
            return response.json()
        try:
            detail = response.json().get("detail")  # the app's errors are {"detail": "..."} (openapi.yaml)
        except ValueError:
            detail = None
        raise ApiError(detail or f"The app answered {response.status_code} for {method} {path}", response.status_code)

    # --- Families and members ----------------------------------------------------------------------

    def current_family(self) -> dict:
        """The family the invite code opens (GET /family). The code itself is never put in a message."""
        try:
            return self._request("GET", "/family")
        except ApiError as error:
            if error.status == 403:
                raise ApiError(
                    "The invite code in STEPBOARD_INVITE_CODE opens no family. Check the MCP server's settings: "
                    "someone in the family may have made a new code.",
                    403,
                ) from error
            raise

    def list_members(self, family_id: int) -> list[dict]:
        return self._request("GET", f"/families/{family_id}/members")

    # --- Boards ------------------------------------------------------------------------------------

    def weekly_leaderboard(self, family_id: int, as_of: date | None = None) -> dict:
        return self._request("GET", f"/families/{family_id}/leaderboards/weekly", params=_as_of(as_of))

    def alltime_leaderboard(self, family_id: int, as_of: date | None = None) -> dict:
        return self._request("GET", f"/families/{family_id}/leaderboards/all-time", params=_as_of(as_of))

    # --- Steps -------------------------------------------------------------------------------------

    def member_steps(self, member_id: int, start: date | None = None, end: date | None = None) -> list[dict]:
        params = {key: day.isoformat() for key, day in {"from": start, "to": end}.items() if day}
        return self._request("GET", f"/members/{member_id}/steps", params=params)

    def log_steps(self, member_id: int, entries: list[tuple[date, int]], source: str = "manual") -> list[dict]:
        """Each entry is a day's total; logging a day again replaces it. All entries are saved or none."""
        body = {
            "member_id": member_id,
            "source": source,
            "entries": [{"day": day.isoformat(), "steps": steps} for day, steps in entries],
        }
        return self._request("POST", "/steps", json=body)


def _as_of(as_of: date | None) -> dict:
    return {"as_of": as_of.isoformat()} if as_of else {}
