// ESP32 Arduino core + ArduinoJson 7. Configure matching named commands in the app.
#include <WiFi.h>
#include <WiFiClientSecure.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>
#include <esp_system.h>
#include <time.h>

const char* WIFI_SSID = "YOUR_WIFI";
const char* WIFI_PASSWORD = "YOUR_PASSWORD";
const char* API_URL = "https://YOUR_API_HOST";
const char* SERIAL_NUMBER = "YOUR_REGISTERED_SERIAL";
const char* FARM_DEVICE_KEY = "YOUR_FARM_SENSOR_KEY";
// Paste the trusted root CA for API_URL. Never disable TLS verification.
const char* ROOT_CA = R"CERT(-----BEGIN CERTIFICATE-----
PASTE_YOUR_ROOT_CA_HERE
-----END CERTIFICATE-----)CERT";
const int PUMP_PIN = 26; // Adapt pin and polarity for your controller.
const bool ACTIVE_LOW = true;
String sessionId, resultId, resultMessage;
uint32_t sequence = 0;
bool awaitingAck = false, resultSuccess = false;
unsigned long lastAttempt = 0;

void newSession() {
  char id[33];
  snprintf(id, sizeof(id), "%08lx%08lx%08lx%08lx", (unsigned long)esp_random(),
    (unsigned long)esp_random(), (unsigned long)esp_random(), (unsigned long)esp_random());
  sessionId = id; sequence = 0; awaitingAck = false;
}
void advance() {
  awaitingAck = false;
  if (sequence >= 2147483647UL) newSession(); else sequence++;
}
String encodeSegment(const char* value) {
  String encoded;
  for (const unsigned char* p = (const unsigned char*)value; *p; p++) {
    if (isalnum(*p) || *p == '-' || *p == '_' || *p == '.' || *p == '~') encoded += char(*p);
    else { char code[4]; snprintf(code, sizeof(code), "%%%02X", *p); encoded += code; }
  }
  return encoded;
}
bool request(const char* action, JsonDocument& body, JsonDocument& result, int& status) {
  WiFiClientSecure tls; tls.setCACert(ROOT_CA);
  HTTPClient http; http.setConnectTimeout(3000); http.setTimeout(3000);
  String url = String(API_URL) + "/command-devices/" + encodeSegment(SERIAL_NUMBER) + "/" + action;
  if (!http.begin(tls, url)) return false;
  http.addHeader("Content-Type", "application/json");
  http.addHeader("x-sensor-key", FARM_DEVICE_KEY);
  String payload; serializeJson(body, payload);
  status = http.POST(payload);
  bool ok = status >= 200 && status < 300;
  if (ok) ok = !deserializeJson(result, http.getString());
  http.end(); return ok;
}
bool applyCommand(const String& value, String& message) {
  // Replace/extend this explicit mapping for your board. Never eval commands.
  if (value == "PUMP_START" || value == "PUMP_STOP") {
    bool on = value == "PUMP_START";
    digitalWrite(PUMP_PIN, on == ACTIVE_LOW ? LOW : HIGH);
    bool applied = digitalRead(PUMP_PIN) == (on == ACTIVE_LOW ? LOW : HIGH);
    message = applied ? (on ? "Pump output enabled" : "Pump output disabled") : "Output did not match request";
    // This confirms the GPIO output. Add physical feedback to confirm equipment.
    return applied;
  }
  message = "Command value is not supported by this firmware"; return false;
}
void setup() {
  Serial.begin(115200); pinMode(PUMP_PIN, OUTPUT);
  digitalWrite(PUMP_PIN, ACTIVE_LOW ? HIGH : LOW);
  newSession(); WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  configTime(0, 0, "pool.ntp.org", "time.google.com");
}
void loop() {
  if (WiFi.status() != WL_CONNECTED || time(nullptr) < 1700000000 || millis() - lastAttempt < 2000) { delay(25); return; }
  lastAttempt = millis();
  JsonDocument body, result; int status = 0;
  body["session_id"] = sessionId; body["sequence"] = sequence;
  if (awaitingAck) {
    body["command_id"] = resultId; body["success"] = resultSuccess; body["message"] = resultMessage;
    if (request("ack", body, result, status) && result["accepted"] == true) advance();
    // A stale slot must not be executed again. Polling will resolve it.
    else if (status == 409) advance();
    return;
  }
  unsigned long began = millis();
  if (!request("poll", body, result, status)) return;
  if (result["advance_sequence"] == true) { advance(); return; }
  if (result["command"].isNull()) return;
  unsigned long budget = result["valid_for_ms"] | 0UL;
  if (millis() - began >= budget || result["command"]["sequence"].as<uint32_t>() != sequence) { advance(); return; }
  resultId = result["command"]["id"].as<String>();
  if (resultId.isEmpty()) return;
  resultSuccess = applyCommand(result["command"]["value"].as<String>(), resultMessage);
  // Remember the result before any network request; never reapply while retrying.
  awaitingAck = true;
}
