"""Constants for NS Departures."""

DOMAIN = "ns_departures"

CONF_STATION = "station"
CONF_DESTINATION = "destination"
CONF_DIRECT_ONLY = "direct_only"

SUBENTRY_TYPE_DESTINATION = "destination"

CONF_SCAN_INTERVAL = "scan_interval"

# Each followed destination makes one request per interval. The free NS tier
# allows 300 requests per 5 minutes per key.
DEFAULT_SCAN_INTERVAL = 60
MIN_SCAN_INTERVAL = 15
MAX_SCAN_INTERVAL = 3600

# How many planner pages to search for the next matching train (each page
# holds about 5 trips, so this reaches well into the next day).
MAX_TRIP_PAGES = 6

# Number of options in the `upcoming` attribute.
UPCOMING_COUNT = 5
