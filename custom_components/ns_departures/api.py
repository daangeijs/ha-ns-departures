"""Minimal client for the NS Reisinformatie API."""

from __future__ import annotations

from typing import Any

import aiohttp

from .models import Departure, Station

BASE_URL = "https://gateway.apiportal.ns.nl/reisinformatie-api/api/v2"
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
        data = await self._get("stations")
        return [Station.from_api(item) for item in data["payload"]]

    async def departures(self, station_code: str) -> list[Departure]:
        data = await self._get(
            "departures", {"station": station_code, "maxJourneys": 40}
        )
        return [Departure.from_api(item) for item in data["payload"]["departures"]]
