# V1.7 controller activity and linked equipment

Run `python migrate_controller_activity.py` before deploying the API/UI changes.
It preserves existing sensor types and adds `grow_light`, `feeding_pump` and
`drainage_pump`, optional device links, private activity history with indexes,
and private exclusive output bindings. It can be rerun safely. Existing devices
are not relinked automatically. No firmware or physical equipment is changed.

In Admin/Super Admin Sensors or assigned Technician device registration, choose
Grow light, Feeding pump or Drainage pump; select a Command Device **on the same
farm** and an available reported output. Register shared E/F drainage once.
Each equipment record has its own serial, name, location, condition and optional
cleaning/servicing/inspection/calibration schedules. No schedules means exactly
“No scheduled maintenance”. Completed work advances that device's actual due date.

| Type | Reported output | Meaning |
| --- | --- | --- |
| Grow light | `lights.E`, `lights.F`, `lights.P` | Rack light relay state |
| Feeding pump | `fertigation.pump_on` | D12 |
| Drainage pump | `drainage.ef.pump_on` | Shared E/F D11 |
| Drainage pump | `drainage.p.pump_on` | P D10 |

An output has one exclusive equipment record, including concurrent registrations.
Reassign or remove the equipment before deleting/retyping its parent controller.
Linked equipment cannot ingest numeric readings or bypass validation through the
legacy sensor editor. Editing maintenance does not overwrite telemetry readings.

## ESP32 protocol

Use the existing production API base URL, farm-specific `x-sensor-key` and HTTPS.
The existing `/command-devices/{serial}/poll` and `/ack` contracts are unchanged.
Poll every 2 seconds, prioritising poll/ACK work above event uploads. Check the
**top-level** `valid_for_ms` and avoid blocking the poller with long upload/retry
loops. No browser Origin header is needed from ESP32; CORS is a browser policy.

The registration form's **Add V1.7 rack commands** adds only missing commands,
preserving existing IDs and hyphen aliases:
`E_ON`, `E_OFF`, `F_ON`, `F_OFF`, `P_ON`, `P_OFF`, `ALL_ON`, `ALL_OFF`, `FERT_STATUS`.
These enable/disable rack feeding settings, including while grid power is absent.
They are not manual relay start commands. Send them using the configured command
ID through the existing command selector. ACK success is command acceptance;
actual equipment state is always taken from the reported snapshot.

Post each V1.7 full snapshot to the existing endpoint:

```http
POST /command-devices/{serial}/events
Content-Type: application/json
x-sensor-key: FARM_SPECIFIC_KEY
```

Accepted types: `controller.status`, `fertigation.racks_changed`, `lights.changed`,
`fertigation.started`, `fertigation.stopped`, `fertigation.feeding_started`,
`fertigation.feeding_stopped`, `fertigation.state_changed`, `fertigation.paused`,
`fertigation.resumed`, `drainage.started`, `drainage.stopped`, `grid.changed`,
`rtc.changed`, `command.rejected`. Existing `calibration.*` events remain separate.
Every activity event must contain the full V1.7 `lights`, `fertigation`, `drainage`,
RTC/grid, uptime and boot-session fields. The schema is also in FastAPI OpenAPI.
`command_id` can be empty/null for autonomous activity; otherwise it must refer to
a dispatched command for this board/boot. `command.rejected` requires a reason.

Use `event_id = session_id + '-' + generation`, where generation is a monotonically
increasing numeric suffix within that boot. Retry the identical payload/ID.
2xx `{"accepted":true,"duplicate":false,"event_id":"…"}` means durable acceptance.
A retry returns `duplicate:true`; conflicting data for an existing ID returns 409.
No event upload renews the online heartbeat. Only authenticated command polling
proves presence, expiring after 5.5 seconds.

## App views and ordering

- `GET /command-devices/{serial}/activity`: latest generation in the current
  polling boot, online, seen_at, server_time. Old-boot queued events remain history.
- `GET /command-devices/{serial}/activity/events?limit=25&before=CURSOR`: all boot
  history by server receipt time, with `next_cursor`. History cursor is device-scoped.
- `GET /controller-equipment?device_id=ID&device_id=ID`: up to 100 registered
  equipment IDs, scoped to active user's farm/role. Each parent is queried once
  per batch. Returns reported_on (nullable), presence, received_at, output, next_due,
  maintenance_status and uptime-based elapsed_ms when applicable.
  Add `status_only=true` for the compact IoT dashboard: it reads the current-boot
  output snapshot and heartbeat once per controller, skipping maintenance history.
  Each light uses its own `lights.E`, `lights.F` or `lights.P` value for ON/OFF;
  controller connectivity alone never means an output is ON. Maintenance fields
  are omitted in this mode. Legacy `presence_only=true` returns only the heartbeat
  with no output snapshot. Responses are `Cache-Control: no-store`.

Controller cards offer **Controller activity & history**. Caretaker/farm owner
Farm Equipment Status keeps its existing headings/tabs and shows actual registered
equipment. Admin and technician equipment cards use the same reported status.
The Flutter ChangeNotifier polls sequentially: wait for completion then 2 seconds;
requests time out and abort at 8 seconds, pause in background, and resume on return.
One HTTP failure retains the last report through the presence grace period.
After 5.5 seconds without a new observation the app marks synchronization as
unknown (Syncing/Reconnecting), rather than inferring that the board is offline.
Only a successful API observation confirming the board heartbeat expired shows
Offline. `heartbeat_age_ms` and `offline_after_ms` use the API clock; the phone's
clock is not used to judge the ESP32. Cached/out-of-order observations cannot
renew presence or replace a newer report. Returning from background immediately
checks again after any cancelled request has finished.
Unavailable API status never invents OFF. Offline/stale cards label last-known
reports explicitly; no report from the current boot means Awaiting report.
Each advancing, API-qualified `seen_at` earns a full 5.5-second grace window
from receipt on the app's monotonic clock. API/database latency does not shorten
that window. One failed request or stale offline response does not immediately
clear healthy presence. Repeated cached `seen_at` values cannot renew it.
Adding another equipment item preserves existing items' healthy status.
Periodic snapshots are expected every 30 seconds; reports older than 65 seconds
are treated as stale even if command polling is healthy.

Polling pauses during actual app sleep/backgrounding and immediately revalidates
on resume, after any interrupted request finishes. Temporary focus changes are
ignored. Responses from an earlier lifecycle generation cannot replace fresh
data or surface an old error. Caretaker and farm owner dashboards retain loaded
data on a failed background refresh; first-load failures remain visible/retryable.
Legacy light switches use their existing 15-second heartbeat timeout with the
same receipt-based grace and lifecycle rules. Light status polling has its own
bounded, abortable transport and does not raise the global connection overlay.

Only fault/rejection events queue notifications: grid loss, RTC unavailable,
command rejection. The API accepts after durable storage; its lifespan worker
retries recipient-scoped idempotent notification delivery independently every 10
seconds. Routine status/stage reports do not generate notification noise.

RTC epoch fields are stored as reported, not assumed UTC or used for ordering.
UI dates use API received_at. Uptime duration arithmetic handles the 32-bit wrap.
Reported relays are commanded states, not proof of current/illumination/water flow.
Fertigation stopped does not imply watering completed normally. Firmware's bounded
volatile queue can drop events or lose them at reset; this is operational history,
not a guaranteed audit trail. Validate real light changeovers, grid pauses,
feeding/drainage transitions, retries and reconnects on the actual ESP32 hardware.
