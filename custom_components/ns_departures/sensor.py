"""Sensors for the next departure of each followed line."""

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
from homeassistant.const import UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType

from .const import CONF_DESTINATIONS, CONF_INCLUDE_VIA, SUBENTRY_TYPE_LINE, UPCOMING_COUNT
from .coordinator import NSConfigEntry
from .entity import NSLineEntity
from .models import Departure, DepartureStatus, Line

MAX_STATE_LENGTH = 255


@dataclass(frozen=True, kw_only=True)
class NSSensorDescription(SensorEntityDescription):
    value_fn: Callable[[Departure], StateType | datetime]
    attrs_fn: Callable[[Departure], dict[str, Any]] | None = None


SENSORS: tuple[NSSensorDescription, ...] = (
    NSSensorDescription(
        key="departure",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda d: d.actual,
        attrs_fn=lambda d: {
            "direction": d.direction,
            "train": f"{d.train_category} {d.train_number}".strip(),
            "operator": d.operator,
            "route": list(d.route_names),
        },
    ),
    NSSensorDescription(
        key="planned_departure",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda d: d.planned,
    ),
    NSSensorDescription(
        key="delay",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        value_fn=lambda d: d.delay_minutes,
    ),
    NSSensorDescription(
        key="track",
        value_fn=lambda d: d.actual_track,
        attrs_fn=lambda d: {
            "planned_track": d.planned_track,
            "track_changed": d.track_changed,
        },
    ),
    NSSensorDescription(
        key="status",
        device_class=SensorDeviceClass.ENUM,
        options=[s.value for s in DepartureStatus],
        value_fn=lambda d: d.status.value,
    ),
    NSSensorDescription(
        key="message",
        value_fn=lambda d: d.message[:MAX_STATE_LENGTH] if d.message else None,
    ),
)


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
            [
                NSLineSensor(data.coordinator, subentry, line, description)
                for description in SENSORS
            ],
            config_subentry_id=subentry_id,
        )


class NSLineSensor(NSLineEntity, SensorEntity):
    entity_description: NSSensorDescription

    def __init__(self, coordinator, subentry, line, description: NSSensorDescription) -> None:
        super().__init__(coordinator, subentry, line, description.key)
        self.entity_description = description

    @property
    def native_value(self) -> StateType | datetime:
        departure = self.next_departure
        return self.entity_description.value_fn(departure) if departure else None

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        departure = self.next_departure
        attrs_fn = self.entity_description.attrs_fn
        if departure is None or attrs_fn is None:
            return None
        attrs = attrs_fn(departure)
        if self.entity_description.key == "departure":
            attrs["upcoming"] = [d.as_dict() for d in self.departures[:UPCOMING_COUNT]]
        return attrs
