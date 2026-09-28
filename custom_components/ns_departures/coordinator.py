"""Polls the departure board of one station."""

from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import TYPE_CHECKING

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import NSAuthError, NSClient, NSConnectionError
from .const import CONF_STATION, DOMAIN, UPDATE_INTERVAL
from .models import Departure, Station

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry

_LOGGER = logging.getLogger(__name__)


@dataclass
class NSData:
    """Runtime data stored on the config entry."""

    client: NSClient
    coordinator: NSDeparturesCoordinator
    stations: dict[str, Station]


type NSConfigEntry = ConfigEntry[NSData]


class NSDeparturesCoordinator(DataUpdateCoordinator[list[Departure]]):
    """Fetches all departures for a station; lines filter them locally."""

    config_entry: NSConfigEntry

    def __init__(
        self, hass: HomeAssistant, entry: NSConfigEntry, client: NSClient
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=f"{DOMAIN} {entry.data[CONF_STATION]}",
            update_interval=UPDATE_INTERVAL,
        )
        self._client = client

    async def _async_update_data(self) -> list[Departure]:
        try:
            return await self._client.departures(
                self.config_entry.data[CONF_STATION]
            )
        except NSAuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except NSConnectionError as err:
            raise UpdateFailed(str(err)) from err
