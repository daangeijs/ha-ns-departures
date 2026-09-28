"""Sensors for the departure board and each followed destination."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.config_entries import ConfigSubentry
from homeassistant.const import UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import BOARD_COUNT, BOARD_ROWS, UPCOMING_COUNT
from .coordinator import DepartureBoardCoordinator, NSConfigEntry, TripsCoordinator
from .entity import FollowedEntity, station_device
from .models import Departure, DepartureStatus, Trip

MAX_STATE_LENGTH = 255
NO_MESSAGE = "None"


@dataclass(frozen=True, kw_only=True)
class NSTripSensorDescription(SensorEntityDescription):
    value_fn: Callable[[Trip], StateType | datetime]
    attrs_fn: Callable[[Trip], dict[str, Any]] | None = None


TRIP_SENSORS: tuple[NSTripSensorDescription, ...] = (
    NSTripSensorDescription(
        key="departure",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda t: t.departure.actual,
        attrs_fn=lambda t: {
            "direction": t.departure.direction,
            "train": t.departure.train,
            "transfers": t.transfers,
            "route": list(t.route),
        },
    ),
    NSTripSensorDescription(
        key="direction",
        value_fn=lambda t: t.departure.direction,
        attrs_fn=lambda t: {"train": t.departure.train},
    ),
    NSTripSensorDescription(
        key="planned_departure",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda t: t.departure.planned,
    ),
    NSTripSensorDescription(
        key="delay",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        value_fn=lambda t: t.departure.delay_minutes,
    ),
    NSTripSensorDescription(
        key="track",
        value_fn=lambda t: t.departure.actual_track,
        attrs_fn=lambda t: {
            "planned_track": t.departure.planned_track,
            "track_changed": t.departure.track_changed,
        },
    ),
    NSTripSensorDescription(
        key="status",
        device_class=SensorDeviceClass.ENUM,
        options=[s.value for s in DepartureStatus],
        value_fn=lambda t: t.departure.status.value,
    ),
    NSTripSensorDescription(
        key="message",
        value_fn=lambda t: (t.departure.message or NO_MESSAGE)[:MAX_STATE_LENGTH],
    ),
    NSTripSensorDescription(
        key="arrival",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda t: t.arrival_actual,
    ),
    NSTripSensorDescription(
        key="transfers",
        value_fn=lambda t: t.transfers,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: NSConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    data = entry.runtime_data
    async_add_entities(
        [
            DepartureBoardSensor(data.board),
            *(BoardRowSensor(data.board, i) for i in range(BOARD_ROWS)),
        ]
    )
    for subentry_id, coordinator in data.trips.items():
        subentry = entry.subentries[subentry_id]
        async_add_entities(
            [TripSensor(coordinator, subentry, d) for d in TRIP_SENSORS],
            config_subentry_id=subentry_id,
        )


# Words used in the readable departure text. Entity states cannot be
# translated by Home Assistant, so pick them from the configured language.
WORDS = {
    "en": {"track": "track", "was": "was", "cancelled": "cancelled"},
    "nl": {"track": "spoor", "was": "was", "cancelled": "rijdt niet"},
}


def departure_text(departure: Departure, language: str) -> str:
    """One departure board row, e.g. `08:01 +4 Rotterdam Centraal · track 4 (was 3)`."""
    words = WORDS.get(language.split("-")[0], WORDS["en"])
    parts = [departure.planned.strftime("%H:%M")]
    if departure.delay_minutes and not departure.cancelled:
        parts.append(f"+{departure.delay_minutes}")
    parts.append(departure.direction)
    text = " ".join(parts)
    if departure.cancelled:
        return f"{text} · {words['cancelled']}"
    if departure.actual_track:
        text += f" · {words['track']} {departure.actual_track}"
        if departure.track_changed:
            text += f" ({words['was']} {departure.planned_track})"
    return text


class BoardEntity(CoordinatorEntity[DepartureBoardCoordinator], SensorEntity):
    _attr_has_entity_name = True

    def __init__(self, coordinator: DepartureBoardCoordinator, key: str) -> None:
        super().__init__(coordinator)
        entry = coordinator.config_entry
        self._attr_unique_id = f"{entry.entry_id}_{key}"
        self._attr_device_info = station_device(entry)


class DepartureBoardSensor(BoardEntity):
    """Number of upcoming trains, with the full board as attributes."""

    _attr_translation_key = "departure_board"

    def __init__(self, coordinator: DepartureBoardCoordinator) -> None:
        super().__init__(coordinator, "departures")

    @property
    def native_value(self) -> int:
        return len(self.coordinator.upcoming[:BOARD_COUNT])

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {
            "departures": [d.as_dict() for d in self.coordinator.upcoming[:BOARD_COUNT]],
            "next_by_destination": {
                direction: d.as_dict()
                for direction, d in self.coordinator.next_by_destination.items()
            },
        }


class BoardRowSensor(BoardEntity):
    """The n-th upcoming train, as a readable line like on the station screens."""

    _attr_translation_key = "board_row"

    def __init__(self, coordinator: DepartureBoardCoordinator, index: int) -> None:
        super().__init__(coordinator, f"departure_{index + 1}")
        self._index = index
        self._attr_translation_placeholders = {"number": str(index + 1)}

    @property
    def _departure(self) -> Departure | None:
        upcoming = self.coordinator.upcoming
        return upcoming[self._index] if self._index < len(upcoming) else None

    @property
    def native_value(self) -> str | None:
        departure = self._departure
        return departure_text(departure, self.hass.config.language) if departure else None

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        departure = self._departure
        return departure.as_dict() if departure else None


class TripSensor(FollowedEntity, SensorEntity):
    """One detail of the next train to a followed destination."""

    entity_description: NSTripSensorDescription

    def __init__(
        self,
        coordinator: TripsCoordinator,
        subentry: ConfigSubentry,
        description: NSTripSensorDescription,
    ) -> None:
        super().__init__(coordinator, subentry, description.key)
        self.entity_description = description

    @property
    def native_value(self) -> StateType | datetime:
        upcoming = self.upcoming
        if not upcoming:
            return NO_MESSAGE if self.entity_description.key == "message" else None
        return self.entity_description.value_fn(upcoming[0])

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        upcoming = self.upcoming
        attrs_fn = self.entity_description.attrs_fn
        if not upcoming or attrs_fn is None:
            return None
        attrs = attrs_fn(upcoming[0])
        if self.entity_description.key == "departure":
            attrs["upcoming"] = [t.as_dict() for t in upcoming[:UPCOMING_COUNT]]
        return attrs
