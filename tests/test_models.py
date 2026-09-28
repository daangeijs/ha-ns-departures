"""Parsing of departure board items and planner trips."""

from custom_components.ns_departures.models import Departure, DepartureStatus, Trip

from .conftest import load_fixture


def _board() -> list[Departure]:
    return [
        Departure.from_board(d)
        for d in load_fixture("departures.json")["payload"]["departures"]
    ]


def _trips() -> list[Trip]:
    return [Trip.from_api(t) for t in load_fixture("trips.json")["trips"]]


def test_board_delay_and_track_change() -> None:
    departure = _board()[0]
    assert departure.delay_minutes == 7
    assert departure.status is DepartureStatus.DELAYED
    assert (departure.planned_track, departure.actual_track) == ("3", "4")
    assert departure.track_changed


def test_board_cancelled_with_reason() -> None:
    departure = _board()[1]
    assert departure.status is DepartureStatus.CANCELLED
    assert departure.message == "Rijdt niet door een seinstoring"


def test_board_on_time() -> None:
    departure = _board()[2]
    assert departure.status is DepartureStatus.ON_TIME
    assert departure.message is None


def test_missing_actual_values_fall_back_to_planned() -> None:
    departure = Departure.from_board(
        {
            "direction": "Nijmegen",
            "plannedDateTime": "2026-09-28T23:50:00+0200",
            "plannedTrack": "4",
        }
    )
    assert departure.actual == departure.planned
    assert departure.actual_track == "4"
    assert not departure.track_changed


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
