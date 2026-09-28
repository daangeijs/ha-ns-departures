"""Minimal client for the NS Reisinformatie API."""

from __future__ import annotations

from datetime import datetime
from typing import Any

import aiohttp

from .models import Station, Trip

BASE_URL = "https://gateway.apiportal.ns.nl/reisinformatie-api/api"
TIMEOUT = aiohttp.ClientTimeout(total=15)


class NSError(Exception):
    """Base error for the NS API."""


class NSAuthError(NSError):
    """The API key was rejected."""


class NSConnectionError(NSError):
    """The API could not be reached or returned an error."""


class NSClient:
    """Talks to the NS Reisinformatie API with a subscription key."""

    def __init__(self, session: aiohttp.ClientSession, api_key: str) -> None:
        self._session = session
        self._api_key = api_key

    async def _get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        try:
            async with self._session.get(
                f"{BASE_URL}/{path}",
                params=params,
                headers={"Ocp-Apim-Subscription-Key": self._api_key},
                timeout=TIMEOUT,
            ) as resp:
                if resp.status in (401, 403):
                    raise NSAuthError(f"API key rejected (HTTP {resp.status})")
                resp.raise_for_status()
                return await resp.json()
        except (aiohttp.ClientError, TimeoutError) as err:
            raise NSConnectionError(str(err) or type(err).__name__) from err

    async def stations(self) -> list[Station]:
        data = await self._get("v2/stations")
        return [Station.from_api(item) for item in data["payload"]]

    async def trips(
        self, from_code: str, to_code: str, after: datetime | None = None
    ) -> list[Trip]:
        """Planner advice, departing from `after` (default: now)."""
        params = {"fromStation": from_code, "toStation": to_code}
        if after is not None:
            params["dateTime"] = after.isoformat()
        data = await self._get("v3/trips", params)
        return [Trip.from_api(item) for item in data.get("trips", [])]
