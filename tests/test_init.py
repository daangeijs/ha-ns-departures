"""Config flow, options, destination subentries and the resulting entities."""

from __future__ import annotations

import pytest
from homeassistant.config_entries import SOURCE_USER, ConfigSubentryData
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from custom_components.ns_departures.api import BASE_URL
from custom_components.ns_departures.const import (
    CONF_DESTINATION,
    CONF_DIRECT_ONLY,
    CONF_SCAN_INTERVAL,
    CONF_STATION,
    DOMAIN,
    SUBENTRY_TYPE_DESTINATION,
)

from .conftest import load_fixture

# Before the first train in trips.json (07:55).
MORNING = "2026-09-29T07:30:00+02:00"


def _entry(*destinations: tuple[str, bool]) -> MockConfigEntry:
    return MockConfigEntry(
        domain=DOMAIN,
        title="Ede-Wageningen",
        unique_id="ED",
        data={CONF_API_KEY: "key", CONF_STATION: "ED"},
        subentries_data=[
            ConfigSubentryData(
                subentry_type=SUBENTRY_TYPE_DESTINATION,
                title="Amsterdam Zuid (direct)" if direct else "Amsterdam Zuid",
                data={CONF_DESTINATION: code, CONF_DIRECT_ONLY: direct},
                unique_id=None,
            )
            for code, direct in destinations
        ],
    )


async def _setup(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()


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
    aioclient_mock.get(f"{BASE_URL}/v2/stations", status=401)
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_API_KEY: "bad"}
    )
    assert result["errors"] == {"base": "invalid_auth"}


@pytest.mark.freeze_time(MORNING)
async def test_destination_sensors(hass: HomeAssistant, ns_api: AiohttpClientMocker) -> None:
    await _setup(hass, _entry(("ASDZ", False)))

    # The next train (07:55) is cancelled; the sensors show it with the reason.
    assert hass.states.get("sensor.amsterdam_zuid_status").state == "cancelled"
    assert hass.states.get("sensor.amsterdam_zuid_message").state == (
        "Rijdt niet Door een seinstoring rijdt deze trein niet."
    )
    departure = hass.states.get("sensor.amsterdam_zuid_departure")
    assert departure.state == "2026-09-29T05:55:00+00:00"
    assert departure.attributes["direction"] == "Den Haag Centraal"
    assert hass.states.get("sensor.amsterdam_zuid_train_direction").state == "Den Haag Centraal"
    assert len(departure.attributes["upcoming"]) == 5
    assert hass.states.get("sensor.amsterdam_zuid_transfers").state == "0"


@pytest.mark.freeze_time("2026-09-29T07:58:00+02:00")
async def test_delay_and_track_change(
    hass: HomeAssistant, ns_api: AiohttpClientMocker
) -> None:
    await _setup(hass, _entry(("ASDZ", False)))
    assert hass.states.get("sensor.amsterdam_zuid_planned_departure").state == "2026-09-29T06:01:00+00:00"
    assert hass.states.get("sensor.amsterdam_zuid_departure").state == "2026-09-29T06:05:00+00:00"
    assert hass.states.get("sensor.amsterdam_zuid_delay").state == "4"
    track = hass.states.get("sensor.amsterdam_zuid_track")
    assert (track.state, track.attributes["planned_track"]) == ("4", "3")
    assert hass.states.get("binary_sensor.amsterdam_zuid_track_changed").state == "on"
    assert hass.states.get("sensor.amsterdam_zuid_status").state == "delayed"
    assert hass.states.get("sensor.amsterdam_zuid_message").state == "None"


@pytest.mark.freeze_time("2026-09-29T08:02:00+02:00")
async def test_direct_only_pages_to_next_direct_train(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    aioclient_mock.get(f"{BASE_URL}/v2/stations", json=load_fixture("stations.json"))
    aioclient_mock.get(
        f"{BASE_URL}/v3/trips",
        params={"dateTime": "2026-09-29T08:13:00+02:00"},
        json=load_fixture("trips_later.json"),
    )
    aioclient_mock.get(f"{BASE_URL}/v3/trips", json=load_fixture("trips_transfers.json"))

    await _setup(hass, _entry(("ASDZ", True)))
    assert hass.states.get("sensor.amsterdam_zuid_direct_planned_departure").state == (
        "2026-09-29T06:25:00+00:00"
    )
    assert hass.states.get("sensor.amsterdam_zuid_direct_transfers").state == "0"


async def test_add_destination(hass: HomeAssistant, ns_api: AiohttpClientMocker) -> None:
    entry = _entry()
    await _setup(hass, entry)

    result = await hass.config_entries.subentries.async_init(
        (entry.entry_id, SUBENTRY_TYPE_DESTINATION), context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {CONF_DESTINATION: "ED", CONF_DIRECT_ONLY: False}
    )
    assert result["errors"] == {CONF_DESTINATION: "same_station"}

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {CONF_DESTINATION: "ASDZ", CONF_DIRECT_ONLY: True}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Amsterdam Zuid (direct)"
    await hass.async_block_till_done()
    assert hass.states.get("sensor.amsterdam_zuid_direct_departure") is not None


async def test_options(hass: HomeAssistant, ns_api: AiohttpClientMocker) -> None:
    entry = _entry(("ASDZ", False))
    await _setup(hass, entry)

    result = await hass.config_entries.options.async_init(entry.entry_id)
    # One destination, every 60 seconds.
    assert result["description_placeholders"]["requests"] == "1"
    assert result["description_placeholders"]["usage"] == "5"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {CONF_SCAN_INTERVAL: 30}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()
    assert entry.options == {CONF_SCAN_INTERVAL: 30}


async def test_options_rate_limit(hass: HomeAssistant, ns_api: AiohttpClientMocker) -> None:
    # 16 destinations: 16 requests every 15 s is 320 per 5 minutes.
    entry = _entry(*[("ASDZ", False)] * 16)
    await _setup(hass, entry)

    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {CONF_SCAN_INTERVAL: 15}
    )
    assert result["errors"] == {CONF_SCAN_INTERVAL: "rate_limit"}

