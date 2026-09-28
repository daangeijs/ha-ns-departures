"""Constants for NS Departures."""

from datetime import timedelta

DOMAIN = "ns_departures"

CONF_STATION = "station"
CONF_DESTINATIONS = "destinations"
CONF_INCLUDE_VIA = "include_via"

SUBENTRY_TYPE_LINE = "line"

# One request per station per minute; the free tier allows 300 per 5 minutes.
UPDATE_INTERVAL = timedelta(minutes=1)

# How many matching departures to expose in the `upcoming` attribute.
UPCOMING_COUNT = 5
