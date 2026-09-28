"""Coordinators polling the NS API."""

from __future__ import annotations

from collections.abc import Awaitable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import logging
from typing import TYPE_CHECKING

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .api import NSAuthError, NSClient, NSConnectionError
from .const import (
    CONF_DESTINATION,
    CONF_DIRECT_ONLY,
    CONF_SCAN_INTERVAL,
    CONF_STATION,
    DEFAULT_SCAN_INTERVAL,
    MAX_TRIP_PAGES,
)
from .models import Station, Trip

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry, ConfigSubentry

_LOGGER = logging.getLogger(__name__)


@dataclass
class NSData:
    """Runtime data stored on the config entry."""

    client: NSClient
    stations: dict[str, Station]
    trips: dict[str, TripsCoordinator] = field(default_factory=dict)


type NSConfigEntry = ConfigEntry[NSData]


def _update_interval(entry: NSConfigEntry) -> timedelta:
    return timedelta(seconds=entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL))


async def _fetch[T](request: Awaitable[T]) -> T:
    try:
        return await request
    except NSAuthError as err:
        raise ConfigEntryAuthFailed(str(err)) from err
    except NSConnectionError as err:
        raise UpdateFailed(str(err)) from err


class TripsCoordinator(DataUpdateCoordinator[list[Trip]]):
    """Planner advice from the station to one followed destination."""

    config_entry: NSConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        entry: NSConfigEntry,
        client: NSClient,
        subentry: ConfigSubentry,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=f"NS trips {entry.data[CONF_STATION]} to {subentry.data[CONF_DESTINATION]}",
            update_interval=_update_interval(entry),
        )
        self._client = client
        self._destination = subentry.data[CONF_DESTINATION]
        self._direct_only = subentry.data.get(CONF_DIRECT_ONLY, False)

    async def _async_update_data(self) -> list[Trip]:
        """Fetch trips, paging forward until one matches.

        With "direct only", or late at night, the first page can contain no
        usable trip. Search later pages so the sensors always show the very
        next train, even if that is tomorrow morning.
        """
        station = self.config_entry.data[CONF_STATION]
        now = dt_util.utcnow()
        after: datetime | None = None
        for _ in range(MAX_TRIP_PAGES):
            page = await _fetch(self._client.trips(station, self._destination, after))
            if not page:
                break
            matching = [
                t
                for t in page
                if t.departure.actual >= now
                and (not self._direct_only or t.transfers == 0)
            ]
            if matching:
                return matching
            after = max(t.departure.planned for t in page) + timedelta(minutes=1)
        return []

    @property
    def upcoming(self) -> list[Trip]:
        """Trips whose train has not left yet."""
        now = dt_util.utcnow()
        return [t for t in self.data or [] if t.departure.actual >= now]
