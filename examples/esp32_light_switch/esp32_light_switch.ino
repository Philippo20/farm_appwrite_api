// ESP32 Arduino core + ArduinoJson 7. One registered relay per sketch.
#include <WiFi.h>
#include <WiFiClientSecure.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>
#include <esp_system.h>

const char* WIFI_SSID = "YOUR_WIFI";
const char* WIFI_PASSWORD = "YOUR_PASSWORD";
const char* API_URL = "https://YOUR_API_HOST";
const char* SERIAL_NUMBER = "YOUR_REGISTERED_SERIAL";
const char* FARM_DEVICE_KEY = "YOUR_FARM_SENSOR_KEY";
// Paste the trusted root CA for API_URL. Never disable TLS verification.
const char* ROOT_CA = R"CERT(-----BEGIN CERTIFICATE-----
PASTE_YOUR_ROOT_CA_HERE
-----END CERTIFICATE-----)CERT";
const int RELAY_PIN = 26; // Choose the correct GPIO for your board.
const bool ACTIVE_LOW = true; // Match the relay module.
String sessionId;
String lastApplied;
unsigned long lastPoll = 0;

void newSession() {
  char id[33];
  snprintf(id, sizeof(id), "%08lx%08lx%08lx%08lx", (unsigned long)esp_random(), (unsigned long)esp_random(), (unsigned long)esp_random(), (unsigned long)esp_random());
  sessionId = id;
  lastApplied = "";
}
bool reportedOn() { return digitalRead(RELAY_PIN) == (ACTIVE_LOW ? LOW : HIGH); }
bool request(const char* action, JsonDocument& body, JsonDocument& result) {
  WiFiClientSecure tls;
  tls.setCACert(ROOT_CA);
  HTTPClient http;
  http.setConnectTimeout(4000);
  http.setTimeout(4000);
  String url = String(API_URL) + "/switches/" + SERIAL_NUMBER + "/" + action;
  if (!http.begin(tls, url)) return false;
  http.addHeader("Content-Type", "application/json");
  http.addHeader("x-sensor-key", FARM_DEVICE_KEY);
  String payload;
  serializeJson(body, payload);
  int status = http.POST(payload);
  bool ok = status >= 200 && status < 300;
  if (ok) ok = !deserializeJson(result, http.getString());
  http.end();
  return ok;
}
void setup() {
  // Start OFF on reboot; no saved desired state is replayed.
  digitalWrite(RELAY_PIN, ACTIVE_LOW ? HIGH : LOW);
  pinMode(RELAY_PIN, OUTPUT);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  configTime(0, 0, "pool.ntp.org", "time.nist.gov"); // TLS certificate checks need time.
  newSession();
}
void loop() {
  if (millis() - lastPoll < 2000) { delay(10); return; }
  lastPoll = millis();
  if (WiFi.status() != WL_CONNECTED) { newSession(); WiFi.reconnect(); return; }
  JsonDocument body, result;
  body["session_id"] = sessionId;
  body["reported_on"] = reportedOn();
  const unsigned long began = millis();
  if (!request("poll", body, result)) { newSession(); return; }
  JsonObject command = result["command"].as<JsonObject>();
  if (command.isNull() || !command["desired_on"].is<bool>() || !command["id"].is<const char*>()) return;
  unsigned long lifetime = command["valid_for_ms"] | 0UL;
  if (lifetime == 0 || millis() - began >= lifetime) return;
  String commandId = command["id"].as<String>();
  if (commandId != lastApplied) {
    bool desired = command["desired_on"].as<bool>();
    digitalWrite(RELAY_PIN, desired ? (ACTIVE_LOW ? LOW : HIGH) : (ACTIVE_LOW ? HIGH : LOW));
    lastApplied = commandId;
  }
  JsonDocument ack, acknowledged;
  ack["session_id"] = sessionId;
  ack["command_id"] = commandId;
  ack["reported_on"] = reportedOn();
  if (!request("ack", ack, acknowledged)) newSession();
}
