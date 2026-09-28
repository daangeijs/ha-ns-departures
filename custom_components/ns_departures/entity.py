"""Devices and the base entity shared by the platforms."""

from __future__ import annotations

from homeassistant.config_entries import ConfigSubentry
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import NSConfigEntry, TripsCoordinator
from .models import Trip


def station_device(entry: NSConfigEntry) -> DeviceInfo:
    """The station itself, holding the departure board sensor."""
    return DeviceInfo(
        identifiers={(DOMAIN, entry.entry_id)},
        name=entry.title,
        manufacturer="NS",
        model="Departure board",
        entry_type=DeviceEntryType.SERVICE,
    )


def destination_device(entry: NSConfigEntry, subentry: ConfigSubentry) -> DeviceInfo:
    """A followed destination, e.g. `Amsterdam Zuid`."""
    return DeviceInfo(
        identifiers={(DOMAIN, subentry.subentry_id)},
        name=subentry.title,
        manufacturer="NS",
        model=f"Next train from {entry.title} to {subentry.title}",
        entry_type=DeviceEntryType.SERVICE,
        via_device=(DOMAIN, entry.entry_id),
    )


class FollowedEntity(CoordinatorEntity[TripsCoordinator]):
    """Entity for the next train to a followed destination."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: TripsCoordinator,
        subentry: ConfigSubentry,
        key: str,
    ) -> None:
        super().__init__(coordinator)
        self._attr_translation_key = key
        self._attr_unique_id = f"{subentry.subentry_id}_{key}"
        self._attr_device_info = destination_device(coordinator.config_entry, subentry)

    @property
    def upcoming(self) -> list[Trip]:
        return self.coordinator.upcoming
