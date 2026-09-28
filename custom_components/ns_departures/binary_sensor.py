"""Binary sensor that flags a track change for the next train to a destination."""

from __future__ import annotations

from typing import Any

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import NSConfigEntry
from .entity import FollowedEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: NSConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    for subentry_id, coordinator in entry.runtime_data.trips.items():
        async_add_entities(
            [TrackChangedSensor(coordinator, entry.subentries[subentry_id], "track_changed")],
            config_subentry_id=subentry_id,
        )


class TrackChangedSensor(FollowedEntity, BinarySensorEntity):
    @property
    def is_on(self) -> bool | None:
        upcoming = self.upcoming
        return upcoming[0].departure.track_changed if upcoming else None

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        upcoming = self.upcoming
        if not upcoming:
            return None
        departure = upcoming[0].departure
        return {
            "planned_track": departure.planned_track,
            "actual_track": departure.actual_track,
        }
