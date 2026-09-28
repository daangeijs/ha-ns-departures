"""Config flow for NS Departures.

The config entry holds the API key and the departure station. Each train
the user wants to follow is a `line` subentry with its own destinations.
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
    SubentryFlowResult,
)
from homeassistant.const import CONF_API_KEY, CONF_NAME
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    BooleanSelector,
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
    CONF_DESTINATIONS,
    CONF_INCLUDE_VIA,
    CONF_STATION,
    DOMAIN,
    SUBENTRY_TYPE_LINE,
)
from .coordinator import NSConfigEntry
from .models import Station

API_KEY_SELECTOR = TextSelector(TextSelectorConfig(type=TextSelectorType.PASSWORD))


class NSDeparturesConfigFlow(ConfigFlow, domain=DOMAIN):
    """Ask for the API key, then the station to show departures for."""

    VERSION = 1

    def __init__(self) -> None:
        self._api_key: str | None = None
        self._stations: list[Station] = []

    @classmethod
    @callback
    def async_get_supported_subentry_types(
        cls, config_entry: ConfigEntry
    ) -> dict[str, type[ConfigSubentryFlow]]:
        return {SUBENTRY_TYPE_LINE: LineSubentryFlow}

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
            errors=errors,
        )

    async def async_step_station(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        stations = {s.code: s for s in self._stations if s.has_departures}
        if user_input is not None:
            station = stations[user_input[CONF_STATION]]
            await self.async_set_unique_id(station.code)
            self._abort_if_unique_id_configured()
            return self.async_create_entry(
                title=station.name,
                data={CONF_API_KEY: self._api_key, CONF_STATION: station.code},
            )

        return self.async_show_form(
            step_id="station",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_STATION): SelectSelector(
                        SelectSelectorConfig(
                            options=[
                                SelectOptionDict(value=s.code, label=s.name)
                                for s in stations.values()
                            ],
                            mode=SelectSelectorMode.DROPDOWN,
                            sort=True,
                        )
                    )
                }
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


class LineSubentryFlow(ConfigSubentryFlow):
    """Add or change a followed line: a name plus one or more destinations."""

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        return await self._async_step_line("user", user_input)

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        return await self._async_step_line("reconfigure", user_input)

    async def _async_step_line(
        self, step_id: str, user_input: dict[str, Any] | None
    ) -> SubentryFlowResult:
        entry: NSConfigEntry = self._get_entry()
        if entry.state is not ConfigEntryState.LOADED:
            return self.async_abort(reason="entry_not_loaded")

        reconfiguring = step_id == "reconfigure"
        errors: dict[str, str] = {}
        if user_input is not None:
            if not user_input[CONF_DESTINATIONS]:
                errors[CONF_DESTINATIONS] = "no_destinations"
            else:
                title = user_input.pop(CONF_NAME)
                if reconfiguring:
                    return self.async_update_and_abort(
                        entry, self._get_reconfigure_subentry(), title=title, data=user_input
                    )
                return self.async_create_entry(title=title, data=user_input)

        if reconfiguring:
            subentry = self._get_reconfigure_subentry()
            defaults = {CONF_NAME: subentry.title, **subentry.data}
        else:
            defaults = {CONF_DESTINATIONS: [], CONF_INCLUDE_VIA: False}
        if user_input is not None:
            defaults = {**defaults, **user_input}

        return self.async_show_form(
            step_id=step_id,
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_NAME, default=defaults.get(CONF_NAME, vol.UNDEFINED)
                    ): str,
                    vol.Required(
                        CONF_DESTINATIONS, default=defaults[CONF_DESTINATIONS]
                    ): SelectSelector(
                        SelectSelectorConfig(
                            options=_destination_options(entry),
                            multiple=True,
                            mode=SelectSelectorMode.DROPDOWN,
                        )
                    ),
                    vol.Required(
                        CONF_INCLUDE_VIA, default=defaults[CONF_INCLUDE_VIA]
                    ): BooleanSelector(),
                }
            ),
            description_placeholders={
                "station": entry.title,
                "departing": ", ".join(_departing_names(entry)) or "-",
            },
            errors=errors,
        )


def _departing_names(entry: NSConfigEntry) -> list[str]:
    """Destinations currently on the departure board, in departure order."""
    data = entry.runtime_data.coordinator.data or []
    return list(dict.fromkeys(d.direction for d in data))


def _destination_options(entry: NSConfigEntry) -> list[SelectOptionDict]:
    """All stations, with those currently on the departure board listed first."""
    stations = entry.runtime_data.stations
    by_name = {s.name: s for s in stations.values()}
    departing = [by_name[n] for n in _departing_names(entry) if n in by_name]
    departing_codes = {s.code for s in departing}
    others = sorted(
        (s for s in stations.values() if s.code not in departing_codes),
        key=lambda s: s.name,
    )
    return [SelectOptionDict(value=s.code, label=s.name) for s in departing + others]
