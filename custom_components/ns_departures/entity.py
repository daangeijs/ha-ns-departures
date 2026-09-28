"""Base entity for a followed line."""

from __future__ import annotations

from homeassistant.config_entries import ConfigSubentry
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import NSDeparturesCoordinator
from .models import Departure, Line


class NSLineEntity(CoordinatorEntity[NSDeparturesCoordinator]):
    """Entity showing the next departure of one followed line.

    Every line is its own device, so its entities group together and are
    named after the line (e.g. `sensor.den_helder_departure`).
    """

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: NSDeparturesCoordinator,
        subentry: ConfigSubentry,
        line: Line,
        key: str,
    ) -> None:
        super().__init__(coordinator)
        self._line = line
        self._attr_translation_key = key
        self._attr_unique_id = f"{subentry.subentry_id}_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, subentry.subentry_id)},
            name=subentry.title,
            manufacturer="NS",
            model=f"Departures from {coordinator.config_entry.title}",
            entry_type=DeviceEntryType.SERVICE,
        )

    @property
    def departures(self) -> list[Departure]:
        return self._line.filter(self.coordinator.data or [])

    @property
    def next_departure(self) -> Departure | None:
        departures = self.departures
        return departures[0] if departures else None
