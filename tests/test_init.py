"""Config flow, line subentries and the resulting entities."""

from __future__ import annotations

from homeassistant.config_entries import SOURCE_USER, ConfigSubentryData
from homeassistant.const import CONF_API_KEY, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from custom_components.ns_departures.api import BASE_URL
from custom_components.ns_departures.const import (
    CONF_DESTINATIONS,
    CONF_INCLUDE_VIA,
    CONF_STATION,
    DOMAIN,
    SUBENTRY_TYPE_LINE,
)


def _entry(*lines: tuple[str, list[str]]) -> MockConfigEntry:
    return MockConfigEntry(
        domain=DOMAIN,
        title="Ede-Wageningen",
        unique_id="ED",
        data={CONF_API_KEY: "key", CONF_STATION: "ED"},
        subentries_data=[
            ConfigSubentryData(
                subentry_type=SUBENTRY_TYPE_LINE,
                title=title,
                data={CONF_DESTINATIONS: codes, CONF_INCLUDE_VIA: False},
                unique_id=None,
            )
            for title, codes in lines
        ],
    )


async def test_user_flow(hass: HomeAssistant, ns_api: AiohttpClientMocker) -> None:
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_API_KEY: "key"}
    )
    assert result["step_id"] == "station"
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_STATION: "ED"}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Ede-Wageningen"
    assert result["data"] == {CONF_API_KEY: "key", CONF_STATION: "ED"}


async def test_user_flow_invalid_key(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    aioclient_mock.get(f"{BASE_URL}/stations", status=401)
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_API_KEY: "bad"}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}


async def test_entities(hass: HomeAssistant, ns_api: AiohttpClientMocker) -> None:
    entry = _entry(("Amsterdam", ["ASD"]), ("Nijmegen", ["NM"]))
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # Delayed train with a track change.
    assert hass.states.get("sensor.amsterdam_departure").state == "2026-09-28T21:47:00+00:00"
    assert hass.states.get("sensor.amsterdam_planned_departure").state == "2026-09-28T21:40:00+00:00"
    assert hass.states.get("sensor.amsterdam_delay").state == "7"
    track = hass.states.get("sensor.amsterdam_track")
    assert track.state == "4"
    assert track.attributes["planned_track"] == "3"
    assert track.attributes["track_changed"] is True
    assert hass.states.get("binary_sensor.amsterdam_track_changed").state == "on"
    assert hass.states.get("sensor.amsterdam_status").state == "delayed"
    upcoming = hass.states.get("sensor.amsterdam_departure").attributes["upcoming"]
    assert len(upcoming) == 2

    # Cancelled train with its reason.
    assert hass.states.get("sensor.nijmegen_status").state == "cancelled"
    assert hass.states.get("sensor.nijmegen_message").state == "Rijdt niet door een seinstoring"
    assert hass.states.get("binary_sensor.nijmegen_track_changed").state == "off"


async def test_add_line_subentry(hass: HomeAssistant, ns_api: AiohttpClientMocker) -> None:
    entry = _entry()
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.subentries.async_init(
        (entry.entry_id, SUBENTRY_TYPE_LINE), context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert "Amsterdam Centraal" in result["description_placeholders"]["departing"]

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {CONF_NAME: "Richting Amersfoort", CONF_DESTINATIONS: [], CONF_INCLUDE_VIA: False},
    )
    assert result["errors"] == {CONF_DESTINATIONS: "no_destinations"}

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {CONF_NAME: "Richting Amersfoort", CONF_DESTINATIONS: ["AMF"], CONF_INCLUDE_VIA: False},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()

    assert hass.states.get("sensor.richting_amersfoort_status").state == "on_time"
    assert hass.states.get("sensor.richting_amersfoort_track").state == "1"


async def test_no_matching_train(hass: HomeAssistant, ns_api: AiohttpClientMocker) -> None:
    entry = _entry(("Den Helder", ["HDR"]))
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert hass.states.get("sensor.den_helder_departure").state == "unknown"
    assert hass.states.get("binary_sensor.den_helder_track_changed").state == "unknown"
