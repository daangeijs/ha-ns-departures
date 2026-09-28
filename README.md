<img src="custom_components/ns_departures/brand/icon.png" alt="NS" width="96" align="right">

# NS Departures

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg?style=for-the-badge)](https://github.com/hacs/integration)
[![Validate](https://img.shields.io/github/actions/workflow/status/daangeijs/ha-ns-departures/validate.yml?style=for-the-badge&label=validate)](https://github.com/daangeijs/ha-ns-departures/actions/workflows/validate.yml)

This integration shows the next train from your station for Home Assistant, using live data from the
departure board of the Dutch railways (NS). You add a station and then pick the trains you want to follow,
for example "the intercity to Den Helder" or "any train to Rotterdam or Den Haag". Each followed train gets
its own sensors with the departure time, delay, track, and status.

It reads the **departure board**, not the journey planner. You always see the actual next train
that goes to your destination, never a suggested route with transfers.

## Features

- Add one or more departure stations, all from the UI.
- Follow as many trains per station as you like, each with one or more destinations.
- Optionally match trains that call at a destination on the way, not only trains that end there.
- Shows the planned time, the actual time, and the delay in minutes.
- Shows the track and flags track changes clearly.
- Shows when a train is cancelled, along with the reason NS gives.
- Lists the next 5 matching trains in an attribute for dashboards.
- One API call per station per minute, well within the free NS limit.
- Translated into English and Dutch.

## Installation

### Step 1: Get an NS API key (free)

The integration needs an API key from the NS API portal. It's free and takes a few minutes.

1. Go to [apiportal.ns.nl](https://apiportal.ns.nl) and click **Sign up**. Confirm your email address and log in.
2. Open **API Products** and choose **Ns-App**.
3. Click **Subscribe**, give the subscription a name (for example `home-assistant`), and confirm.
4. Go to **Profile**. Under your subscriptions, click **Show** next to the **Primary key** and copy it.

That key is what you paste into Home Assistant. You don't need to pick individual APIs. The Ns-App product
includes the *Reisinformatie API*, which this integration uses.

> The free tier allows 300 requests per 5 minutes. This integration makes 1 request per station per minute,
> so even 10 stations stay well within the limit.

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

### Add a station

[![Open your Home Assistant instance and start setting up a new integration.](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=ns_departures)

1. Go to **Settings → Devices & services → Add integration** and search for **NS Departures**.
2. Paste your API key.
3. Choose your departure station, for example *Ede-Wageningen*.

Want departures from a second station? Add the integration again. It remembers your API key.

### Follow a train

Open the station under **Settings → Devices & services → NS Departures** and click **Follow a train**.

| Field | What it does |
| --- | --- |
| **Name** | Name of the device and its sensors, e.g. `Den Helder` gives `sensor.den_helder_departure`. |
| **Destinations** | One or more stations. The stations currently on the departure board are listed first, and the form also shows which destinations are leaving right now. |
| **Also match trains that call at a destination on the way** | Off: only trains whose **final destination** is one of your picks. On: also trains that **pass through** one, e.g. pick *Utrecht Centraal* to get every train that stops in Utrecht. |

You can change a followed train later with the **⋮** menu next to it, or remove it there.

**Example: Ede-Wageningen, everything towards the Randstad**

| Name | Destinations |
| --- | --- |
| Den Helder | Den Helder |
| Rotterdam | Rotterdam Centraal |
| Den Haag | Den Haag Centraal |
| Randstad | Den Helder, Rotterdam Centraal, Den Haag Centraal *(first of any of the three)* |

## Entities

Every followed train is a device with these entities (shown here for a train named *Den Helder*):

| Entity | Example | Description |
| --- | --- | --- |
| `sensor.den_helder_departure` | `05:48` | Expected departure time, including delay. |
| `sensor.den_helder_planned_departure` | `05:41` | Departure time according to the timetable. |
| `sensor.den_helder_delay` | `7` | Delay in minutes (`0` when on time). |
| `sensor.den_helder_track` | `4` | Track the train actually departs from. |
| `binary_sensor.den_helder_track_changed` | `on` | `on` when the track differs from the planned track. |
| `sensor.den_helder_status` | `delayed` | `on_time`, `delayed` or `cancelled`. |
| `sensor.den_helder_message` | `Rijdt niet door een seinstoring` | Remarks from NS, such as the reason a train is cancelled. *Unknown* when there are none. |

When no matching train is on the departure board (at night, for example), the sensors show *Unknown*.

**Attributes**

- `sensor.*_departure` has `direction`, `train` (e.g. `IC 3084`), `operator`, `route` (stations it calls at),
  and `upcoming`: the next 5 matching trains, each with `planned`, `actual`, `delay`, `track`,
  `track_changed`, `direction`, `train`, `status`, and `message`.
- `sensor.*_track` has `planned_track` and `track_changed`.

A cancelled train stays the "next train" until its departure time has passed, so you see it's not running
instead of it quietly disappearing.

## Examples

### Dashboard card

A Markdown card that shows the planned time, the delay, the track (with a warning on a change), and the
reason for a cancellation:

```yaml
type: markdown
title: Trains from Ede-Wageningen
content: >-
  {% for name in ['den_helder', 'rotterdam', 'den_haag'] %}
  {%- set dep = 'sensor.' ~ name ~ '_departure' %}
  {%- if states(dep) not in ['unknown', 'unavailable'] %}
  {%- set planned = states('sensor.' ~ name ~ '_planned_departure') | as_datetime | as_local %}
  {%- set delay = states('sensor.' ~ name ~ '_delay') | int(0) %}
  {%- set status = states('sensor.' ~ name ~ '_status') %}
  {%- set track = states('sensor.' ~ name ~ '_track') %}
  **{{ state_attr(dep, 'direction') }}** · {{ planned.strftime('%H:%M') }}
  {%- if status == 'cancelled' %} ❌ **Cancelled** – {{ states('sensor.' ~ name ~ '_message') }}
  {%- else %}
  {%- if delay > 0 %} <font color="red">+{{ delay }}</font>{% endif %}
   · track {% if is_state('binary_sensor.' ~ name ~ '_track_changed', 'on') %}<font color="orange">**{{ track }}** (changed, was {{ state_attr('sensor.' ~ name ~ '_track', 'planned_track') }})</font>{% else %}{{ track }}{% endif %}
  {%- endif %}

  {% endif %}
  {%- endfor %}
```

### Notify on a track change or cancellation

```yaml
alias: Train to Den Helder changed
triggers:
  - trigger: state
    entity_id: binary_sensor.den_helder_track_changed
    to: "on"
  - trigger: state
    entity_id: sensor.den_helder_status
    to: cancelled
actions:
  - action: notify.notify
    data:
      title: Train to Den Helder
      message: >-
        {% if is_state('sensor.den_helder_status', 'cancelled') %}
        The {{ as_timestamp(states('sensor.den_helder_planned_departure')) | timestamp_custom('%H:%M') }}
        train is cancelled: {{ states('sensor.den_helder_message') }}
        {% else %}
        Now departs from track {{ states('sensor.den_helder_track') }}
        (was {{ state_attr('sensor.den_helder_track', 'planned_track') }}).
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
