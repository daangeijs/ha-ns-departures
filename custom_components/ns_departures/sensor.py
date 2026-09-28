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

from .const import BOARD_COUNT, UPCOMING_COUNT
from .coordinator import DepartureBoardCoordinator, NSConfigEntry, TripsCoordinator
from .entity import FollowedEntity, station_device
from .models import DepartureStatus, Trip

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
    async_add_entities([DepartureBoardSensor(data.board)])
    for subentry_id, coordinator in data.trips.items():
        subentry = entry.subentries[subentry_id]
        async_add_entities(
            [TripSensor(coordinator, subentry, d) for d in TRIP_SENSORS],
            config_subentry_id=subentry_id,
        )


class DepartureBoardSensor(CoordinatorEntity[DepartureBoardCoordinator], SensorEntity):
    """Next departure from the station, with the full board as attribute."""

    _attr_has_entity_name = True
    _attr_translation_key = "departures"
    _attr_device_class = SensorDeviceClass.TIMESTAMP

    def __init__(self, coordinator: DepartureBoardCoordinator) -> None:
        super().__init__(coordinator)
        entry = coordinator.config_entry
        self._attr_unique_id = f"{entry.entry_id}_departures"
        self._attr_device_info = station_device(entry)

    @property
    def native_value(self) -> datetime | None:
        upcoming = self.coordinator.upcoming
        return upcoming[0].actual if upcoming else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {
            "departures": [d.as_dict() for d in self.coordinator.upcoming[:BOARD_COUNT]],
            "next_by_destination": {
                direction: d.as_dict()
                for direction, d in self.coordinator.next_by_destination.items()
            },
        }


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
