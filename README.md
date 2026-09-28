<img src="custom_components/ns_departures/brand/icon.png" alt="NS" width="96" align="right">

# NS Departures

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg?style=for-the-badge)](https://github.com/hacs/integration)
[![Validate](https://img.shields.io/github/actions/workflow/status/daangeijs/ha-ns-departures/validate.yml?style=for-the-badge&label=validate)](https://github.com/daangeijs/ha-ns-departures/actions/workflows/validate.yml)

This Home Assistant integration shows live train departures from Dutch railway (NS) stations. For every station
you add, you get the full departure board, like the station page on ns.nl. On top of that you can follow
destinations: for each one, sensors show the next train that gets you there, including delay, track changes,
and cancellations.

## Features

- Departure board for each station: every upcoming train, and the first train to each destination.
- Follow as many destinations per station as you like.
- The next train to a destination comes from the NS journey planner, the same one as on ns.nl. It includes
  trains that need a transfer, or you can limit it to direct trains.
- Always shows the very next train, even when that one leaves tomorrow morning.
- Planned time, expected time, and delay in minutes.
- Track, with a separate sensor that turns on when the track changes.
- Status (on time, delayed, cancelled) and the NS message, such as the reason a train is cancelled.
- Adjustable update interval, with a check that you stay within the NS limit.
- Everything is set up from the UI. Translated into English and Dutch.

## Installation

### Step 1: Get an NS API key (free)

The integration needs your own API key from the NS API portal. It's free and takes a few minutes.

1. Go to [apiportal.ns.nl](https://apiportal.ns.nl) and click **Sign up**. Confirm your email address and log in.
2. Open **API Products** and choose **Ns-App**.
3. Click **Subscribe**, give the subscription a name (for example `home-assistant`), and confirm.
4. Go to **Profile**. Under your subscriptions, click **Show** next to the **Primary key** and copy it.

That key is what you paste into Home Assistant. You don't need to pick individual APIs. The Ns-App product
includes the *Reisinformatie API*, which this integration uses.

### Step 2: Install the integration

**With [HACS](https://hacs.xyz) (recommended)**

This repository is not in the HACS default store yet, so add it as a custom repository:

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=daangeijs&repository=ha-ns-departures&category=integration)

Or do it by hand:

1. In Home Assistant, open **HACS**.
2. Click the three dots in the top right and choose **Custom repositories**.
3. Enter `https://github.com/daangeijs/ha-ns-departures`, choose type **Integration**, and click **Add**.
4. Search for **NS Departures**, open it, and click **Download**.
5. Restart Home Assistant.

**Manually**

Download the [latest release](https://github.com/daangeijs/ha-ns-departures/releases), copy the
`custom_components/ns_departures` folder into your Home Assistant `config/custom_components` folder, and
restart Home Assistant.

## Configuration

Setup has three parts: your API key, a station, and the destinations you want to follow from that station.

### 1. API key and station

[![Open your Home Assistant instance and start setting up a new integration.](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=ns_departures)

1. Go to **Settings → Devices & services → Add integration** and search for **NS Departures**.
2. Paste your API key.
3. Choose the station you want to see departures for.

The station is added right away, with a **Departures** sensor that holds the full departure board.
To add another station, add the integration again. It remembers your API key.

### 2. Follow destinations

Open the station under **Settings → Devices & services → NS Departures** and click **Follow a destination**.

| Field | What it does |
| --- | --- |
| **Destination** | The station you want to travel to. |
| **Direct trains only** | Off: the next train on the fastest route, which may include a transfer, as on ns.nl. On: only trains that get there without a transfer. |

Each destination becomes its own device with the sensors listed below. You can follow the same destination
twice, once with and once without **Direct trains only**. Change or remove a destination with the **⋮** menu
next to it.

### 3. Update interval (optional)

Open the station and click **Configure** to set how often it updates. The default is every 60 seconds.

NS allows **300 requests per 5 minutes** per API key. Every update of a station uses 1 request for the
departure board, plus 1 request for each destination you follow. Some examples:

| Stations × destinations | Interval | Requests per 5 minutes |
| --- | --- | --- |
| 1 station, 3 destinations | 60 s | 20 |
| 1 station, 3 destinations | 15 s | 80 |
| 3 stations, 5 destinations each | 30 s | 180 |

The form shows how many requests all stations using your key make together. If a shorter interval would push
you over the limit, it tells you so. Late at night a destination can occasionally need a few extra requests,
because the integration searches ahead until it finds the next train.

## Entities

### Station

| Entity | Description |
| --- | --- |
| `sensor.<station>_departures` | Expected time of the next train leaving the station. |

Attributes:

- `departures`: the next 20 trains, each with `planned`, `actual`, `delay`, `track`, `planned_track`,
  `track_changed`, `direction`, `train`, `status`, and `message`.
- `next_by_destination`: the first train to each destination on the board, keyed by destination, with the same
  fields.

### Followed destination

| Entity | Example | Description |
| --- | --- | --- |
| `sensor.<destination>_departure` | `08:05` | Expected departure time from your station, including delay. |
| `sensor.<destination>_planned_departure` | `08:01` | Departure time according to the timetable. |
| `sensor.<destination>_delay` | `4` | Delay in minutes (`0` when on time). |
| `sensor.<destination>_track` | `4` | Track the train actually departs from. |
| `binary_sensor.<destination>_track_changed` | `on` | `on` when the track differs from the planned track. |
| `sensor.<destination>_status` | `delayed` | `on_time`, `delayed` or `cancelled`. |
| `sensor.<destination>_message` | `None` | Message from NS, such as the reason a train is cancelled. `None` when there is no message. |
| `sensor.<destination>_arrival` | `08:53` | Expected arrival time at the destination. |
| `sensor.<destination>_transfers` | `0` | Number of transfers. |

Attributes of `sensor.<destination>_departure`: `direction` (where the train is heading), `train`
(e.g. `IC 3222`), `transfers`, `route` (your station, any transfer stations, and the destination), and
`upcoming` (the next 5 options, with the same fields as above plus `arrival`).

With **Direct trains only**, the device name and entity IDs end in `_direct`, for example
`sensor.<destination>_direct_departure`.

A cancelled train stays the "next train" until its departure time has passed, so you see that it doesn't run
and why, instead of it quietly disappearing.

## Examples

Replace `station` and `destination` in the entity IDs with your own.

### Dashboard: full departure board

```yaml
type: markdown
title: Departures
content: |
  | Time | | To | Track |
  |:--|:--|:--|:--|
  {% for d in state_attr('sensor.station_departures', 'departures')[:10] %}
  {%- set time = as_timestamp(d.planned) | timestamp_custom('%H:%M') %}
  {%- set info = '❌' if d.status == 'cancelled' else ('+' ~ d.delay if d.delay else '') %}
  {%- set track = '**' ~ d.track ~ '** ⚠️' if d.track_changed else d.track %}
  | {{ time }} | {{ info }} | {{ d.direction }} | {{ track }} |
  {% endfor %}
```

### Dashboard: next train to a destination

```yaml
type: entities
title: Next train
entities:
  - entity: sensor.destination_planned_departure
    name: Departs
  - entity: sensor.destination_delay
    name: Delay
  - entity: sensor.destination_track
    name: Track
  - entity: binary_sensor.destination_track_changed
    name: Track changed
  - entity: sensor.destination_status
    name: Status
  - entity: sensor.destination_message
    name: Message
```

### Notify on a track change or cancellation

```yaml
alias: Train track changed or cancelled
triggers:
  - trigger: state
    entity_id: binary_sensor.destination_track_changed
    to: "on"
  - trigger: state
    entity_id: sensor.destination_status
    to: cancelled
actions:
  - action: notify.notify
    data:
      title: Your train
      message: >-
        {% set planned = as_timestamp(states('sensor.destination_planned_departure')) | timestamp_custom('%H:%M') %}
        {% if is_state('sensor.destination_status', 'cancelled') %}
        The {{ planned }} train is cancelled: {{ states('sensor.destination_message') }}
        {% else %}
        The {{ planned }} train now leaves from track {{ states('sensor.destination_track') }}
        (was {{ state_attr('sensor.destination_track', 'planned_track') }}).
        {% endif %}
```

## Minimum required version

- Home Assistant 2025.9.0
- Home Assistant 2026.3.0 or newer to show the NS icon in the UI

## Language translations

English and Dutch are included. Corrections and new languages are welcome: edit or add a file in
`custom_components/ns_departures/translations` and open a pull request. If you're unsure how, open an issue
and paste your changes there.

## Disclaimer

This is not an official NS product. Departure data comes from the
[NS API portal](https://apiportal.ns.nl) and falls under its terms of use.
The NS name and logo are trademarks of Nederlandse Spoorwegen and are used here only to identify
the data source.

## License

[MIT](LICENSE)
