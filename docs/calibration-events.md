# Controller calibration events

Run `python migrate_calibration_events.py` before deploying. This creates a
private indexed event collection; no existing sensor readings are changed.

## Firmware protocol

POST `https://api-5u45d.ondigitalocean.app/command-devices/{serial}/events` with
`x-sensor-key: FARM_SENSOR_KEY` and `Content-Type: application/json`.

```json
{
  "category": "calibration",
  "event_id": "06f7fe7c-1b56-4774-8902-b15b8fc013a5",
  "session_id": "board-session-id",
  "calibration_id": "d7593af8-1d92-49bf-bd87-bef68b3a2b41",
  "command_id": "a638d00e-9eb3-497b-a5d1-17e6889af195",
  "type": "calibration.cancelled",
  "target": "ef_drain",
  "state": "idle",
  "reason": "grid_power_lost",
  "message": "Calibration cancelled: grid power lost.",
  "uptime_ms": 125000,
  "grid_available": false,
  "elapsed_ms": 12400,
  "saved": false
}
```

`category` may be omitted and defaults to `calibration`. All IDs are UUIDs except
the boot `session_id`, which follows the existing command polling protocol.
`calibration_id` is the dispatched selection command UUID. Keep it throughout
that calibration. `command_id` is the dispatched triggering command UUID (selection,
start, stop, cancellation). Autonomous safety events use the most recent command
that started/affected the operation, not an invented command ID. Both commands
must belong to this serial and the original boot session. Current connectivity,
command expiry and the current boot do not invalidate historical event delivery.
If no selection exists, a `rejected` / `no_calibration_selected` event uses the
triggering start command UUID as its attempted `calibration_id`.

Supported types: `calibration.request_received`, `calibration.waiting_for_start`,
`calibration.starting`, `calibration.running`, `calibration.completed`,
`calibration.cancelled`, `calibration.rejected`, `calibration.not_saved`.

Targets: `ef_drain`, `p_drain`, `fertigation`. Fertigation requires `rack` (`E`,
`F`, `P`); omit it for drains. A calibration cannot change target/rack or boot.
`state` is the controller's raw state (up to 64 characters); the UI's workflow
state comes from the event type, not assumptions about pump activity.

Cancellation, rejection and not-saved events require one of these reasons:
`grid_power_lost`, `grid_power_unavailable`, `tank_not_full`, `all_racks_disabled`,
`selected_rack_disabled`, `calibration_already_running`, `no_calibration_selected`,
`pump_start_delay`, `pump_not_started`, `maximum_duration_reached`,
`duration_too_short`, `user_cancelled`, `command_expired`.
Starting may include `pump_start_delay`; progress events may include a reason too.

Completion requires `saved: true` and a positive integer `saved_duration_ms`.
All other events use `saved: false` and omit `saved_duration_ms`. The API preserves
previous saved durations on cancellation, rejection and not-saved measurements.
`uptime_ms` is an integer from the original boot; `elapsed_ms` is optional.

## Delivery, ordering and safety

- Persist the complete event locally before transmission. Give it a UUID once;
  retries must send the same ID and contents. Queue through Wi-Fi loss/reboots.
  See `examples/esp32_command_device/calibration_event_queue.h` for an NVS outbox.
- A 200 response includes `accepted: true`, `duplicate`, `event_id`. Remove that
  queued event only after the accepted response. A lost response is safe to retry.
  A conflicting reuse of an ID returns 409; invalid fields return 422. Do not
  discard these failures silently. A 503 can mean the event was saved but its
  notification delivery needs retrying; resend the same event.
- Continue authenticated `/poll` requests every two seconds. Event uploads never
  renew device presence. Heartbeat timeout remains 5.5 seconds. Keep network work
  outside pump safety/control loops and avoid starving heartbeat polls.
- Original selection time orders separate calibrations. Original boot uptime
  orders events within a calibration. Terminal results survive delayed progress
  and old queued calibrations do not replace newer results. A rejected repeat
  request does not falsely stop an already running calibration.
- A final result is immutable per calibration. Conflicting terminal events return
  409, as does progress with a later uptime than an already-finalized result.
- Saved durations come only from controller completion events. A command ACK
  confirms command handling, not calibration completion. Firmware owns valve,
  pump, power-loss and maximum-duration safety behavior.
- History displays **received time**, original uptime and command/calibration IDs.
  The API does not invent an occurrence timestamp from reconnection time.

## UI and notifications

Open **Calibration & history** on a Command Device card (Admin/Super Admin,
technician or other roles with existing device access). The compact dialog/mobile
sheet shows controller progress, reasons, reported elapsed time, confirmed saved
measurements and paginated expandable history. Use the device's configured named
commands for selection, `CAL_START`, stop and cancellation; exact firmware values
are preserved. Sending is limited to existing authorized control roles.

The configured selection values are `EF_D_SELECT`, `P_D_SELECT`, and
`FERT_D_SELECT`. The picker shows only these calibration selections. Once the
controller reports `waiting_for_start`, the selection control becomes **Start** /
**Cancel**, using the registered IDs for `CAL_START` / `CAL_CANCEL`. On `starting`
or `running`, the controls become **Stop** / **Cancel**, using `CAL_STOP` /
`CAL_CANCEL`. A confirmed cancellation returns to the selection view. A command
ACK alone never advances this workflow. Missing configured actions are disabled
with a configuration message rather than guessed or replaced by another command.

When offline during an active calibration, the UI says **status unknown**, retaining
the last report and saved measurements. It never assumes cancellation or success.

Completion, cancellation, rejection and not-saved events create recipient-scoped
idempotent inbox/push notifications for active admins, the current farm team and
the selection initiator. Intermediate progress stays in the panel/history.

Authenticated reads:
- `GET /command-devices/{serial}/calibrations`: current session, latest attempt,
  saved measurements by target/rack and ten recent events.
- `GET /command-devices/{serial}/calibrations/events?before=EVENT_UUID&limit=25`:
  paginated history (maximum 50 per page). Optional `calibration_id` filters a run.

These use the signed-in user's JWT/selected role and farm access checks, not the
board key. The collection has no public database permissions.
