"""Config flow for NS Departures.

The config entry holds the API key and the departure station. Every
destination the user follows is a subentry of that station.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigEntryState,
    ConfigFlow,
    ConfigFlowResult,
    ConfigSubentryFlow,
    OptionsFlow,
    SubentryFlowResult,
)
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    BooleanSelector,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .api import NSAuthError, NSClient, NSConnectionError
from .const import (
    CONF_DESTINATION,
    CONF_DIRECT_ONLY,
    CONF_SCAN_INTERVAL,
    CONF_STATION,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    MAX_SCAN_INTERVAL,
    MIN_SCAN_INTERVAL,
    SUBENTRY_TYPE_DESTINATION,
)
from .coordinator import NSConfigEntry
from .models import Station

PORTAL_URL = "https://apiportal.ns.nl"
API_KEY_SELECTOR = TextSelector(TextSelectorConfig(type=TextSelectorType.PASSWORD))

# The free NS tier allows this many requests per 5 minutes per API key.
RATE_LIMIT = 300


def _station_selector(stations: list[Station]) -> SelectSelector:
    return SelectSelector(
        SelectSelectorConfig(
            options=[
                SelectOptionDict(value=s.code, label=s.name)
                for s in stations
                if s.has_departures
            ],
            mode=SelectSelectorMode.DROPDOWN,
            sort=True,
        )
    )


class NSDeparturesConfigFlow(ConfigFlow, domain=DOMAIN):
    """Ask for the API key, then the station to show departures for."""

    VERSION = 1

    def __init__(self) -> None:
        self._api_key: str | None = None
        self._stations: list[Station] = []

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> NSOptionsFlow:
        return NSOptionsFlow()

    @classmethod
    @callback
    def async_get_supported_subentry_types(
        cls, config_entry: ConfigEntry
    ) -> dict[str, type[ConfigSubentryFlow]]:
        return {SUBENTRY_TYPE_DESTINATION: DestinationSubentryFlow}

    async def _async_fetch_stations(self, api_key: str) -> str | None:
        """Validate the key by loading the station list; return an error key."""
        client = NSClient(async_get_clientsession(self.hass), api_key)
        try:
            self._stations = await client.stations()
        except NSAuthError:
            return "invalid_auth"
        except NSConnectionError:
            return "cannot_connect"
        return None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            if not (error := await self._async_fetch_stations(user_input[CONF_API_KEY])):
                self._api_key = user_input[CONF_API_KEY]
                return await self.async_step_station()
            errors["base"] = error

        # Adding a second station should not require pasting the key again.
        existing = self._async_current_entries()
        default_key = existing[0].data[CONF_API_KEY] if existing else vol.UNDEFINED
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {vol.Required(CONF_API_KEY, default=default_key): API_KEY_SELECTOR}
            ),
            description_placeholders={"portal_url": PORTAL_URL},
            errors=errors,
        )

    async def async_step_station(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            station = next(s for s in self._stations if s.code == user_input[CONF_STATION])
            await self.async_set_unique_id(station.code)
            self._abort_if_unique_id_configured()
            return self.async_create_entry(
                title=station.name,
                data={CONF_API_KEY: self._api_key, CONF_STATION: station.code},
            )

        return self.async_show_form(
            step_id="station",
            data_schema=vol.Schema(
                {vol.Required(CONF_STATION): _station_selector(self._stations)}
            ),
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            if not (error := await self._async_fetch_stations(user_input[CONF_API_KEY])):
                return self.async_update_reload_and_abort(
                    self._get_reauth_entry(),
                    data_updates={CONF_API_KEY: user_input[CONF_API_KEY]},
                )
            errors["base"] = error

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema({vol.Required(CONF_API_KEY): API_KEY_SELECTOR}),
            errors=errors,
        )


def _requests_per_update(entry: ConfigEntry) -> int:
    """One request per followed destination."""
    return sum(
        1 for s in entry.subentries.values() if s.subentry_type == SUBENTRY_TYPE_DESTINATION
    )


def _key_usage(hass: HomeAssistant, entry: ConfigEntry, interval: float) -> int:
    """Requests per 5 minutes for all stations sharing this entry's API key,
    with `entry` polling every `interval` seconds."""
    total = 0.0
    for other in hass.config_entries.async_entries(DOMAIN):
        if other.data[CONF_API_KEY] != entry.data[CONF_API_KEY]:
            continue
        seconds = (
            interval
            if other.entry_id == entry.entry_id
            else other.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
        )
        total += _requests_per_update(other) * 300 / seconds
    return round(total)


class NSOptionsFlow(OptionsFlow):
    """Set how often this station polls NS."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        interval = self.config_entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
        if user_input is not None:
            interval = int(user_input[CONF_SCAN_INTERVAL])
            if _key_usage(self.hass, self.config_entry, interval) <= RATE_LIMIT:
                return self.async_create_entry(data={CONF_SCAN_INTERVAL: interval})
            errors[CONF_SCAN_INTERVAL] = "rate_limit"

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_SCAN_INTERVAL, default=interval): NumberSelector(
                        NumberSelectorConfig(
                            min=MIN_SCAN_INTERVAL,
                            max=MAX_SCAN_INTERVAL,
                            step=1,
                            unit_of_measurement="s",
                            mode=NumberSelectorMode.BOX,
                        )
                    )
                }
            ),
            description_placeholders={
                "requests": str(_requests_per_update(self.config_entry)),
                "usage": str(_key_usage(self.hass, self.config_entry, interval)),
                "limit": str(RATE_LIMIT),
            },
            errors=errors,
        )


class DestinationSubentryFlow(ConfigSubentryFlow):
    """Follow the next train from the station to one destination."""

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        return await self._async_step_destination("user", user_input)

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        return await self._async_step_destination("reconfigure", user_input)

    async def _async_step_destination(
        self, step_id: str, user_input: dict[str, Any] | None
    ) -> SubentryFlowResult:
        entry: NSConfigEntry = self._get_entry()
        if entry.state is not ConfigEntryState.LOADED:
            return self.async_abort(reason="entry_not_loaded")

        stations = entry.runtime_data.stations
        current = self._get_reconfigure_subentry() if step_id == "reconfigure" else None
        errors: dict[str, str] = {}

        if user_input is not None:
            if user_input[CONF_DESTINATION] == entry.data[CONF_STATION]:
                errors[CONF_DESTINATION] = "same_station"
            elif any(
                s.data == user_input and s is not current
                for s in entry.subentries.values()
            ):
                errors["base"] = "already_followed"
            else:
                title = stations[user_input[CONF_DESTINATION]].name
                if user_input[CONF_DIRECT_ONLY]:
                    title = f"{title} (direct)"
                if current is not None:
                    return self.async_update_and_abort(
                        entry, current, title=title, data=user_input
                    )
                return self.async_create_entry(title=title, data=user_input)

        defaults = user_input or (dict(current.data) if current else {CONF_DIRECT_ONLY: False})
        return self.async_show_form(
            step_id=step_id,
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_DESTINATION,
                        default=defaults.get(CONF_DESTINATION, vol.UNDEFINED),
                    ): _station_selector(list(stations.values())),
                    vol.Required(
                        CONF_DIRECT_ONLY, default=defaults[CONF_DIRECT_ONLY]
                    ): BooleanSelector(),
                }
            ),
            description_placeholders={"station": entry.title},
            errors=errors,
        )
