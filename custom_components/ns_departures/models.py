"""Data models for NS Departures.

Pure Python with no Home Assistant imports, so the parsing and matching
logic can be unit tested without a Home Assistant installation.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Any


class DepartureStatus(StrEnum):
    """Simplified status of a departure."""

    ON_TIME = "on_time"
    DELAYED = "delayed"
    CANCELLED = "cancelled"


@dataclass(frozen=True, slots=True)
class Station:
    """An NS station."""

    code: str
    uic: str
    name: str
    medium_name: str
    has_departures: bool

    @classmethod
    def from_api(cls, data: dict[str, Any]) -> Station:
        names = data["namen"]
        return cls(
            code=data["code"],
            uic=data["UICCode"],
            name=names["lang"],
            medium_name=names["middel"],
            has_departures=data.get("heeftVertrektijden", False),
        )


@dataclass(frozen=True, slots=True)
class Departure:
    """A single departure from the departure board."""

    direction: str
    train_category: str
    train_number: str
    operator: str
    planned: datetime
    actual: datetime
    planned_track: str | None
    actual_track: str | None
    cancelled: bool
    route_uics: tuple[str, ...]
    route_names: tuple[str, ...]
    messages: tuple[str, ...]

    @classmethod
    def from_api(cls, data: dict[str, Any]) -> Departure:
        product = data.get("product", {})
        planned = datetime.fromisoformat(data["plannedDateTime"])
        actual_raw = data.get("actualDateTime")
        planned_track = data.get("plannedTrack")
        route = data.get("routeStations", [])
        return cls(
            direction=data["direction"],
            train_category=data.get("trainCategory", ""),
            train_number=product.get("number", ""),
            operator=product.get("operatorName", ""),
            planned=planned,
            actual=datetime.fromisoformat(actual_raw) if actual_raw else planned,
            planned_track=planned_track,
            actual_track=data.get("actualTrack") or planned_track,
            cancelled=data.get("cancelled", False),
            route_uics=tuple(s["uicCode"] for s in route),
            route_names=tuple(s["mediumName"] for s in route),
            messages=tuple(
                m["message"] for m in data.get("messages", []) if m.get("message")
            ),
        )

    @property
    def delay_minutes(self) -> int:
        """Delay in whole minutes; never negative."""
        return max(0, round((self.actual - self.planned).total_seconds() / 60))

    @property
    def track_changed(self) -> bool:
        return (
            self.planned_track is not None
            and self.actual_track is not None
            and self.planned_track != self.actual_track
        )

    @property
    def status(self) -> DepartureStatus:
        if self.cancelled:
            return DepartureStatus.CANCELLED
        if self.delay_minutes > 0:
            return DepartureStatus.DELAYED
        return DepartureStatus.ON_TIME

    @property
    def message(self) -> str | None:
        """All NS remarks for this departure, e.g. the reason it is cancelled."""
        return " ".join(self.messages) or None

    def as_dict(self) -> dict[str, Any]:
        """Compact representation for the `upcoming` attribute."""
        return {
            "planned": self.planned.isoformat(),
            "actual": self.actual.isoformat(),
            "delay": self.delay_minutes,
            "track": self.actual_track,
            "track_changed": self.track_changed,
            "direction": self.direction,
            "train": f"{self.train_category} {self.train_number}".strip(),
            "status": self.status.value,
            "message": self.message,
        }


@dataclass(frozen=True, slots=True)
class Line:
    """A set of destinations a user follows from their station.

    A departure matches when its final destination is one of the chosen
    stations, or, with `include_via`, when it calls at one of them on the way.
    """

    names: frozenset[str]
    uics: frozenset[str]
    include_via: bool

    @classmethod
    def from_codes(
        cls, codes: list[str], stations: dict[str, Station], include_via: bool
    ) -> Line:
        chosen = [stations[code] for code in codes if code in stations]
        return cls(
            names=frozenset(
                name for s in chosen for name in (s.name, s.medium_name)
            ),
            uics=frozenset(s.uic for s in chosen),
            include_via=include_via,
        )

    def matches(self, departure: Departure) -> bool:
        if departure.direction in self.names:
            return True
        return self.include_via and not self.uics.isdisjoint(departure.route_uics)

    def filter(self, departures: list[Departure]) -> list[Departure]:
        return [d for d in departures if self.matches(d)]
