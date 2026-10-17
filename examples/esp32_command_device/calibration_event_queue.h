// ESP32 Arduino + ArduinoJson 7. Durable outbox, separate from actuator safety.
// Use one owner task (or an external mutex) for all queue methods.
#pragma once
#include <Arduino.h>
#include <Preferences.h>
#include <ArduinoJson.h>
#include <esp_system.h>
#include <esp_random.h>

class CalibrationEventQueue {
 public:
  bool begin() { return storage.begin("cal-events", false); }
  static String eventUuid() {
    uint8_t bytes[16];
    esp_fill_random(bytes, sizeof(bytes));
    bytes[6] = (bytes[6] & 0x0f) | 0x40;
    bytes[8] = (bytes[8] & 0x3f) | 0x80;
    char out[37];
    snprintf(out, sizeof(out),
      "%02x%02x%02x%02x-%02x%02x-%02x%02x-%02x%02x-%02x%02x%02x%02x%02x%02x",
      bytes[0], bytes[1], bytes[2], bytes[3], bytes[4], bytes[5], bytes[6], bytes[7],
      bytes[8], bytes[9], bytes[10], bytes[11], bytes[12], bytes[13], bytes[14], bytes[15]);
    return out;
  }
  // Fill session_id, calibration_id, command_id, type, target, state, uptime_ms,
  // reason/rack/etc before enqueueing. A full outbox MUST be surfaced to an
  // operator; never silently overwrite old events or bypass physical safety.
  bool enqueue(JsonDocument& event) {
    if (event["event_id"].isNull()) event["event_id"] = eventUuid();
    event["category"] = "calibration";
    String payload;
    serializeJson(event, payload);
    for (int i = 0; i < CAPACITY; ++i) {
      String name = slot(i);
      String existing = storage.getString(name.c_str(), "");
      if (!existing.isEmpty()) {
        JsonDocument saved;
        if (!deserializeJson(saved, existing) &&
            saved["event_id"].as<String>() == event["event_id"].as<String>())
          return existing == payload;
      }
    }
    for (int i = 0; i < CAPACITY; ++i) {
      String name = slot(i);
      if (!storage.isKey(name.c_str()))
        return storage.putString(name.c_str(), payload) == payload.length();
    }
    return false;
  }
  // Upload this JSON unchanged to /command-devices/{serial}/events using
  // x-sensor-key. Preserve the original boot session even after rebooting.
  bool peek(int& index, String& payload) {
    for (int i = 0; i < CAPACITY; ++i) {
      payload = storage.getString(slot(i).c_str(), "");
      if (!payload.isEmpty()) { index = i; return true; }
    }
    return false;
  }
  // Call only for HTTP 200 + accepted:true and the matching event_id. Checking
  // the ID prevents deleting an event if a stale response targets a reused slot.
  bool accepted(int index, const String& eventId) {
    if (index < 0 || index >= CAPACITY) return false;
    String name = slot(index);
    JsonDocument saved;
    if (deserializeJson(saved, storage.getString(name.c_str(), ""))) return false;
    if (saved["event_id"].as<String>() != eventId) return false;
    return storage.remove(name.c_str());
  }
 private:
  static constexpr int CAPACITY = 32;
  Preferences storage;
  String slot(int index) { return "evt" + String(index); }
};
