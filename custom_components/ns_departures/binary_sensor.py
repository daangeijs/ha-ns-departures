"""Binary sensor that flags a track change for the next departure."""

from __future__ import annotations

from typing import Any

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import CONF_DESTINATIONS, CONF_INCLUDE_VIA, SUBENTRY_TYPE_LINE
from .coordinator import NSConfigEntry
from .entity import NSLineEntity
from .models import Line


async def async_setup_entry(
    hass: HomeAssistant,
    entry: NSConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    data = entry.runtime_data
    for subentry_id, subentry in entry.subentries.items():
        if subentry.subentry_type != SUBENTRY_TYPE_LINE:
            continue
        line = Line.from_codes(
            subentry.data[CONF_DESTINATIONS],
            data.stations,
            subentry.data.get(CONF_INCLUDE_VIA, False),
        )
        async_add_entities(
            [NSTrackChangedSensor(data.coordinator, subentry, line, "track_changed")],
            config_subentry_id=subentry_id,
        )


class NSTrackChangedSensor(NSLineEntity, BinarySensorEntity):
    @property
    def is_on(self) -> bool | None:
        departure = self.next_departure
        return departure.track_changed if departure else None

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        departure = self.next_departure
        if departure is None:
            return None
        return {
            "planned_track": departure.planned_track,
            "actual_track": departure.actual_track,
        }
