"""NS Departures: follow the next train to chosen destinations from a station."""

from __future__ import annotations

from homeassistant.const import CONF_API_KEY, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import NSAuthError, NSClient, NSConnectionError
from .coordinator import NSConfigEntry, NSData, NSDeparturesCoordinator

PLATFORMS = [Platform.BINARY_SENSOR, Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: NSConfigEntry) -> bool:
    client = NSClient(async_get_clientsession(hass), entry.data[CONF_API_KEY])
    try:
        stations = await client.stations()
    except NSAuthError as err:
        raise ConfigEntryAuthFailed(str(err)) from err
    except NSConnectionError as err:
        raise ConfigEntryNotReady(str(err)) from err

    coordinator = NSDeparturesCoordinator(hass, entry, client)
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = NSData(
        client=client,
        coordinator=coordinator,
        stations={s.code: s for s in stations},
    )
    # Adding, changing or removing a followed line reloads the entry.
    entry.async_on_unload(entry.add_update_listener(_async_reload))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: NSConfigEntry) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def _async_reload(hass: HomeAssistant, entry: NSConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)
