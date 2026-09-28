"""Parsing of planner trips."""

from custom_components.ns_departures.models import DepartureStatus, Trip

from .conftest import load_fixture


def _trips() -> list[Trip]:
    return [Trip.from_api(t) for t in load_fixture("trips.json")["trips"]]


def test_trip_cancelled_with_reason() -> None:
    trip = _trips()[0]
    assert trip.departure.status is DepartureStatus.CANCELLED
    assert trip.departure.message == "Rijdt niet Door een seinstoring rijdt deze trein niet."


def test_trip_delay_and_track_change() -> None:
    trip = _trips()[1]
    assert trip.departure.delay_minutes == 4
    assert trip.departure.track_changed
    assert trip.departure.direction == "Rotterdam Centraal"
    assert trip.departure.train == "IC 3222"


def test_trip_with_transfer() -> None:
    trip = _trips()[2]
    assert trip.transfers == 1
    assert trip.route == ("Ede-Wageningen", "Utrecht Centraal", "Amsterdam Zuid")
    assert trip.arrival_actual.isoformat() == "2026-09-29T09:04:00+02:00"


def test_missing_actual_values_fall_back_to_planned() -> None:
    data = load_fixture("trips.json")["trips"][3]
    origin = data["legs"][0]["origin"]
    del origin["actualDateTime"], origin["actualTrack"]
    trip = Trip.from_api(data)
    assert trip.departure.actual == trip.departure.planned
    assert trip.departure.actual_track == trip.departure.planned_track
    assert not trip.departure.track_changed
