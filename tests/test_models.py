"""Parsing and line matching."""

from custom_components.ns_departures.models import (
    Departure,
    DepartureStatus,
    Line,
    Station,
)

from .conftest import load_fixture


def _departures() -> list[Departure]:
    return [
        Departure.from_api(d)
        for d in load_fixture("departures.json")["payload"]["departures"]
    ]


def _stations() -> dict[str, Station]:
    stations = [Station.from_api(s) for s in load_fixture("stations.json")["payload"]]
    return {s.code: s for s in stations}


def test_delay_and_track_change() -> None:
    departure = _departures()[0]
    assert departure.delay_minutes == 7
    assert departure.status is DepartureStatus.DELAYED
    assert departure.planned_track == "3"
    assert departure.actual_track == "4"
    assert departure.track_changed


def test_cancelled_with_reason() -> None:
    departure = _departures()[1]
    assert departure.status is DepartureStatus.CANCELLED
    assert departure.message == "Rijdt niet door een seinstoring"
    assert not departure.track_changed


def test_on_time() -> None:
    departure = _departures()[2]
    assert departure.status is DepartureStatus.ON_TIME
    assert departure.delay_minutes == 0
    assert departure.message is None


def test_missing_actual_values_fall_back_to_planned() -> None:
    departure = Departure.from_api(
        {
            "direction": "Nijmegen",
            "plannedDateTime": "2026-09-28T23:50:00+0200",
            "plannedTrack": "4",
        }
    )
    assert departure.actual == departure.planned
    assert departure.actual_track == "4"
    assert not departure.track_changed


def test_line_matches_final_destination_only() -> None:
    line = Line.from_codes(["ASD"], _stations(), include_via=False)
    matched = line.filter(_departures())
    assert [d.direction for d in matched] == ["Amsterdam Centraal"] * 2


def test_line_with_multiple_destinations() -> None:
    line = Line.from_codes(["NM", "AMF"], _stations(), include_via=False)
    directions = {d.direction for d in line.filter(_departures())}
    assert directions == {"Nijmegen", "Amersfoort Centraal"}


def test_line_include_via() -> None:
    stations = _stations()
    assert not Line.from_codes(["UT"], stations, include_via=False).filter(_departures())
    via = Line.from_codes(["UT"], stations, include_via=True).filter(_departures())
    assert {d.direction for d in via} == {"Amsterdam Centraal"}


def test_unknown_station_code_is_ignored() -> None:
    line = Line.from_codes(["GONE"], _stations(), include_via=True)
    assert line.filter(_departures()) == []
