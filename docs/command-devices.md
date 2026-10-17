# Command devices

Run `python migrate_command_devices.py` before deploying. It adds `command_device`
to the existing sensor type enum, preserves all existing types/defaults and adds
optional `command_config` JSON (8192 characters). Commands reuse the private switch
control collection. Existing temperature sensors and light switches are unchanged.

Admin and Super Admin can register or edit a Command Device from Sensors → Devices.
Configure 1–12 commands, each with a stable ID, unique name (up to 60 characters)
and exact value (up to 256 characters). The value is delivered as data to firmware;
the API does not execute code, HTTP requests or shell commands from that value.
Command devices have no numeric readings, thresholds, calibration or automatic
maintenance tasks. Normal sensor ingest cannot create or modify command devices.

The card shows online status, the command selector, value preview and the last
device result. The card refreshes every two seconds in the foreground. Admins and
the existing assigned farm owner/caretaker control roles may send commands.
Assigned technicians and farm managers may view status without sending commands.
Configuration remains limited to Admin and Super Admin. User requests require an
Appwrite JWT and use the selected role. Sent commands are recorded in audit logs.

## Board protocol

Use HTTPS with certificate verification and the registered farm's sensor key in
`x-sensor-key`. The key is never included in the card, guide or URL. One board uses
one registered serial. Firmware must implement the command values you configure.
See `examples/esp32_command_device/esp32_command_device.ino` for an example.

On every boot generate a new `session_id` (8–64 alphanumeric, underscore or hyphen
characters) and start `sequence` at zero. Poll sequentially every two seconds:

```http
POST /command-devices/{serial}/poll
x-sensor-key: FARM_SPECIFIC_KEY
Content-Type: application/json

{"session_id":"unique-board-boot-id","sequence":0}
```

An idle response has `command: null` and `advance_sequence: false`. A pending
response contains `command.id`, `command.command_key`, `command.label`,
`command.value`, `command.sequence` and top-level `valid_for_ms`.

Execute only supported values, once per command ID, within the remaining lifetime.
Conservatively subtract request round-trip time from `valid_for_ms`. Return success
only after the operation is applied or the controller confirms it:

```http
POST /command-devices/{serial}/ack
x-sensor-key: FARM_SPECIFIC_KEY
Content-Type: application/json

{"session_id":"unique-board-boot-id","sequence":0,"command_id":"UUID_FROM_POLL","success":true,"message":"Pump started"}
```

Report `success: false` and a message on failure. Acknowledgements are immutable
and idempotent. Retry an acknowledgement after a lost response, without repeating
the operation. After an accepted acknowledgement, increment sequence. A poll with
`advance_sequence: true` means that slot is resolved, expired or invalidated:
increment sequence without executing anything. A stale acknowledgement returns
409; poll again to resolve the slot. Never reuse a boot session after restart.

## Delivery guarantees

- A board is online for 4 seconds after its last authenticated poll. The state
  response includes `offline_after_ms: 4000` so the card uses the same timeout.
- A command expires after 10 seconds and is bound to its boot session, sequence
  and configuration revision. Restarting or editing configuration invalidates it.
- An immutable, unique database document claims each board sequence. Concurrent
  senders cannot overwrite that slot. User request UUIDs make retries idempotent,
  even after the board advances or later commands are sent.
- The card shows Confirmed only after a success acknowledgement. Rejected values
  show Failed. Missing or late acknowledgements show Expired; this does not prove
  that an operation never happened. Physical operations must be idempotent.
- An inactive device cannot execute a new command. An offline board is not queued
  work to execute unexpectedly on its next boot.

Board execution depends on firmware. Automated tests simulate polling, expiry,
concurrent senders, acknowledgements, configuration changes and role restrictions;
they do not replace testing the actual controller and connected equipment.
