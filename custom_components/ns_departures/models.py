"""Data models for NS Departures.

Pure Python with no Home Assistant imports, so the parsing logic can be
unit tested without a Home Assistant installation.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime
from enum import StrEnum
from typing import Any


class DepartureStatus(StrEnum):
    """Simplified status of a departure."""

    ON_TIME = "on_time"
    DELAYED = "delayed"
    CANCELLED = "cancelled"


def _parse_time(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value) if value else None


@dataclass(frozen=True, slots=True)
class Station:
    """An NS station."""

    code: str
    name: str
    has_departures: bool

    @classmethod
    def from_api(cls, data: dict[str, Any]) -> Station:
        return cls(
            code=data["code"],
            name=data["namen"]["lang"],
            has_departures=data.get("heeftVertrektijden", False),
        )


@dataclass(frozen=True, slots=True)
class Departure:
    """The train you board at your station: the first leg of a trip."""

    direction: str
    train_category: str
    train_number: str
    planned: datetime
    actual: datetime
    planned_track: str | None
    actual_track: str | None
    cancelled: bool
    messages: tuple[str, ...]

    @classmethod
    def from_leg(cls, leg: dict[str, Any], trip_messages: tuple[str, ...]) -> Departure:
        """Parse the first leg of a /trips result."""
        product = leg.get("product", {})
        origin = leg["origin"]
        planned = datetime.fromisoformat(origin["plannedDateTime"])
        planned_track = origin.get("plannedTrack")
        leg_messages = tuple(
            m["text"] for m in leg.get("messages", []) if m.get("text")
        )
        return cls(
            direction=leg.get("direction", ""),
            train_category=product.get("categoryCode", ""),
            train_number=product.get("number", ""),
            planned=planned,
            actual=_parse_time(origin.get("actualDateTime")) or planned,
            planned_track=planned_track,
            actual_track=origin.get("actualTrack") or planned_track,
            cancelled=leg.get("cancelled", False),
            messages=trip_messages + leg_messages,
        )

    @property
    def train(self) -> str:
        return f"{self.train_category} {self.train_number}".strip()

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
        """All NS remarks, e.g. the reason a train is cancelled."""
        return " ".join(dict.fromkeys(self.messages)) or None

    def as_dict(self) -> dict[str, Any]:
        return {
            "planned": self.planned.isoformat(),
            "actual": self.actual.isoformat(),
            "delay": self.delay_minutes,
            "track": self.actual_track,
            "planned_track": self.planned_track,
            "track_changed": self.track_changed,
            "direction": self.direction,
            "train": self.train,
            "status": self.status.value,
            "message": self.message,
        }


@dataclass(frozen=True, slots=True)
class Trip:
    """A journey to the followed destination, as advised by the NS planner."""

    departure: Departure
    arrival_planned: datetime
    arrival_actual: datetime
    transfers: int
    route: tuple[str, ...]

    @classmethod
    def from_api(cls, data: dict[str, Any]) -> Trip:
        legs = data["legs"]
        primary = data.get("primaryMessage") or {}
        trip_messages = tuple(
            text
            for text in (primary.get("title"), (primary.get("message") or {}).get("text"))
            if text
        )
        departure = Departure.from_leg(legs[0], trip_messages)
        if data.get("status") == "CANCELLED" and not departure.cancelled:
            departure = replace(departure, cancelled=True)
        destination = legs[-1]["destination"]
        arrival_planned = datetime.fromisoformat(destination["plannedDateTime"])
        return cls(
            departure=departure,
            arrival_planned=arrival_planned,
            arrival_actual=_parse_time(destination.get("actualDateTime"))
            or arrival_planned,
            transfers=data.get("transfers", len(legs) - 1),
            # Origin, every transfer station, then the destination.
            route=tuple(
                [legs[0]["origin"]["name"]] + [leg["destination"]["name"] for leg in legs]
            ),
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            **self.departure.as_dict(),
            "arrival": self.arrival_actual.isoformat(),
            "transfers": self.transfers,
            "route": list(self.route),
        }

