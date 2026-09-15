# ESP32 light switch

1. Install backend requirements, run `python migrate_light_switches.py`, and wait for the `sensor_kind` index to become available in Appwrite. Deploy the API and Flutter changes.
2. Register a **Light Switch** under the correct farm. Set its Location / Zone to the label wanted on the existing Lights card, e.g. E RACK. This is separate from a light-intensity sensor.
3. Configure the Arduino sketch with Wi-Fi, API HTTPS URL, full registered serial, the farm sensor ingestion key, trusted root certificate, GPIO and relay polarity. Use ESP32 Arduino core and ArduinoJson 7. Compile and upload for the actual board.
4. The ESP32 polls every 2 seconds. Tap the existing dashboard light card to request a change. ON/OFF is the device-reported relay GPIO state; physical lamp feedback requires a separate feedback input.

User endpoints require a valid account JWT and an active Admin, Super Admin, or assigned Caretaker/Owner profile. Device endpoints require the farm-specific sensor key; missing keys fail closed. Database control documents have no client permissions.

The device is offline after 15 seconds without a poll. Commands expire after 10 seconds and belong to one device connection session. The sketch creates a new session after a failed network request or restart, so old commands are not replayed. ON/OFF commands set an absolute state, never invert the GPIO. The relay starts OFF at boot and retains its last state during a network outage. Match this behavior and GPIO polarity to your installation before connecting the load.

No relay is activated by registering a device or deploying these files. Hardware compilation and relay confirmation must be checked on your board. The API uses immutable command and acknowledgement documents; if concurrent commands arrive, the newest command is the one offered to the device. Retain control documents for audit, or remove expired command/ack pairs using a separate retention job.
