#include <Arduino.h>
#include <ESP8266WiFi.h>
#include <ESP8266WebServer.h>
#include <LittleFS.h>
#include <ArduinoJson.h>
#include "OtaUpdate.h"
#include "ConfigConstants.h"
#include "StepperMotorDriver.h"
#include <WiFiManager.h>
#include <time.h>
#include "NtfyClient.h"

// Define your stepper motor pins here (change as per your wiring)
#define STEPPER_IN1 D1
#define STEPPER_IN2 D2
#define STEPPER_IN3 D3
#define STEPPER_IN4 D4

ESP8266WebServer server(80);
StepperMotorDriver stepper(STEPPER_IN1, STEPPER_IN2, STEPPER_IN3, STEPPER_IN4);

// Forward declarations
void serveHTML(const char* path);
String readFile(const char* path);
bool writeFile(const char* path, const String& content);
void updateNextWindingTime();
void loadNextWindingTime();
void getWindingParams(int& duration, String& speed);
void handleRoot();
void handleSetSchedule();
void handleWindNow();
void handleTroubleshooting();
void handleApiConfig();
void handleApiHome();
void handleApiScheduleGet();
void handleApiSchedulePost();
void handleApiWindNow();
void handleApiMotorGet();
void handleApiMotorPost();
void handleApiMemory();
void handleApiUptime();
void handleApiEvents();
void handleApiCheckUpdate();
void handleApiDoUpdate();
void handleStaticFile();

// Scheduled winding state
time_t nextWindingEpoch = 0;
unsigned long lastScheduleCheck = 0;
const unsigned long SCHEDULE_CHECK_INTERVAL = 300 * 1000UL; // 300 seconds
bool scheduledWindingInProgress = false;

// Helper function implementations
String readFile(const char* path) {
  File file = LittleFS.open(path, "r");
  if (!file) {
    Serial.printf("[readFile] Failed to open: %s\n", path);
    return "";
  }
  String content = file.readString();
  file.close();
  return content;
}

bool writeFile(const char* path, const String& content) {
  File file = LittleFS.open(path, "w");
  if (!file) {
    Serial.printf("[writeFile] Failed to open: %s\n", path);
    return false;
  }
  file.print(content);
  file.close();
  return true;
}

const char* weekdayName(int wday) {
  static const char* names[] = {"Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"};
  return names[wday % 7];
}

String formatISO8601(const struct tm& t) {
  char buf[25];
  snprintf(buf, sizeof(buf), "%04d-%02d-%02dT%02d:%02d:%02d", t.tm_year+1900, t.tm_mon+1, t.tm_mday, t.tm_hour, t.tm_min, t.tm_sec);
  return String(buf);
}

time_t parseISO8601(const String& iso) {
  struct tm t;
  if (sscanf(iso.c_str(), "%d-%d-%dT%d:%d:%d", &t.tm_year, &t.tm_mon, &t.tm_mday, &t.tm_hour, &t.tm_min, &t.tm_sec) == 6) {
    t.tm_year -= 1900;
    t.tm_mon -= 1;
    t.tm_isdst = -1;
    return mktime(&t);
  }
  return 0;
}

void loadNextWindingTime() {
  String nextWindingStr = readFile("/Config/next_winding.txt");
  nextWindingEpoch = parseISO8601(nextWindingStr);
}

void getWindingParams(int& duration, String& speed) {
  String sched = readFile("/Config/schedule.txt");
  duration = 30;
  speed = "Medium";
  if (sched.length() > 0) {
    StaticJsonDocument<256> doc;
    DeserializationError err = deserializeJson(doc, sched);
    if (!err) {
      if (doc.containsKey("winding_duration")) duration = doc["winding_duration"];
      if (doc.containsKey("winding_speed")) speed = String(doc["winding_speed"].as<const char*>());
    }
  }
}

void updateNextWindingTime() {
  String sched = readFile("/Config/schedule.txt");
  if (sched.length() == 0) return;
  StaticJsonDocument<512> doc;
  DeserializationError err = deserializeJson(doc, sched);
  if (err) return;
  JsonArray times = doc["winding_times"].as<JsonArray>();
  JsonObject days = doc["days"].as<JsonObject>();
  time_t now = time(nullptr);
  struct tm t;
  localtime_r(&now, &t);
  time_t soonest = 0;
  for (int dayOffset = 0; dayOffset < 8; ++dayOffset) {
    int wday = (t.tm_wday + dayOffset) % 7;
    const char* dayName = weekdayName(wday);
    if (!days[dayName] || !days[dayName].as<bool>()) continue;
    for (JsonVariant timeObj : times) {
      int hour = timeObj["hour"];
      int minute = timeObj["minute"];
      String ampm = timeObj["ampm"].as<String>();
      int hour24 = (ampm == "PM" && hour != 12) ? hour + 12 : (ampm == "AM" && hour == 12 ? 0 : hour);
      struct tm candidate = t;
      candidate.tm_mday += dayOffset;
      candidate.tm_hour = hour24;
      candidate.tm_min = minute;
      candidate.tm_sec = 0;
      time_t candidateEpoch = mktime(&candidate);
      if (candidateEpoch <= now) continue;
      if (soonest == 0 || candidateEpoch < soonest) soonest = candidateEpoch;
    }
  }
  if (soonest > 0) {
    struct tm soonestTm;
    localtime_r(&soonest, &soonestTm);
    String iso = formatISO8601(soonestTm);
    writeFile("/Config/next_winding.txt", iso);
    nextWindingEpoch = soonest;
    Serial.printf("[SCHEDULE] Next winding scheduled for %s\n", iso.c_str());
  } else {
    Serial.println("[SCHEDULE] No valid next winding time found.");
  }
}

// HTML route handlers
void handleRoot() { serveHTML("/UI/index.html"); }
void handleSetSchedule() { serveHTML("/UI/setschedule.html"); }
void handleWindNow() { serveHTML("/UI/windnow.html"); }
void handleTroubleshooting() { serveHTML("/UI/troubleshooting.html"); }

void serveHTML(const char* path) {
  File file = LittleFS.open(path, "r");
  if (!file) {
    server.send(404, "text/html", "<html><body>File not found</body></html>");
    return;
  }
  server.streamFile(file, "text/html");
  file.close();
}

void handleStaticFile() {
  String path = "/UI" + server.uri();
  Serial.printf("[handleStaticFile] Serving: %s\n", path.c_str());
  
  String contentType = "text/plain";
  if (path.endsWith(".css")) contentType = "text/css";
  else if (path.endsWith(".js")) contentType = "application/javascript";
  else if (path.endsWith(".png")) contentType = "image/png";
  else if (path.endsWith(".jpg") || path.endsWith(".jpeg")) contentType = "image/jpeg";
  else if (path.endsWith(".gif")) contentType = "image/gif";
  else if (path.endsWith(".svg")) contentType = "image/svg+xml";
  
  File file = LittleFS.open(path, "r");
  if (!file) {
    server.send(404, "text/plain", "File not found");
    return;
  }
  server.streamFile(file, contentType);
  file.close();
}

// API Endpoints
void handleApiConfig() {
  Serial.println("[API] GET /api/config");
  yield();
  StaticJsonDocument<256> doc;
  doc["ntfy_topic"] = NTFY_TOPIC;
  doc["wifi_ssid"] = WiFi.SSID();
  String response;
  serializeJson(doc, response);
  server.send(200, "application/json", response);
}

void handleApiHome() {
  Serial.println("[API] GET /api/home");
  yield();

  String lastWinding = readFile("/Config/last_winding.txt");
  String nextWinding = readFile("/Config/next_winding.txt");
  String duration = readFile("/Config/duration.txt");
  String quantity = readFile("/Config/quantitytxt");

  StaticJsonDocument<256> doc;
  doc["last_winding"] = lastWinding;
  doc["next_winding"] = nextWinding;
  doc["duration"] = duration;
  doc["quantity"] = quantity;

  String response;
  serializeJson(doc, response);
  server.send(200, "application/json", response);
}

void handleApiScheduleGet() {
  Serial.println("[API] GET /api/schedule");
  yield();
  String scheduleData = readFile("/Config/schedule.txt");
  if (scheduleData.length() > 0) {
    StaticJsonDocument<512> doc;
    DeserializationError err = deserializeJson(doc, scheduleData);
    if (!err) {
      if (!doc.containsKey("winding_speed")) {
        doc["winding_speed"] = "Medium";
      }
      String response;
      serializeJson(doc, response);
      server.send(200, "application/json", response);
    } else {
      server.send(500, "application/json", "{\"error\":\"Invalid schedule format\"}");
    }
  } else {
    server.send(404, "application/json", "{\"error\":\"Schedule not found\"}");
  }
}

void handleApiSchedulePost() {
  Serial.println("[API] POST /api/schedule");
  yield();
  if (server.hasArg("plain")) {
    String body = server.arg("plain");
    StaticJsonDocument<512> doc;
    DeserializationError err = deserializeJson(doc, body);
    if (!err) {
      if (!doc.containsKey("winding_speed")) {
        doc["winding_speed"] = "Medium";
      }
      String out;
      serializeJson(doc, out);
      if (writeFile("/Config/schedule.txt", out)) {
        server.send(200, "application/json", "{\"status\":\"ok\"}");
      } else {
        server.send(500, "application/json", "{\"status\":\"error\",\"error\":\"Failed to save\"}");
      }
    } else {
      server.send(400, "application/json", "{\"status\":\"error\",\"error\":\"Invalid JSON\"}");
    }
  } else {
    server.send(400, "application/json", "{\"status\":\"error\",\"error\":\"No data\"}");
  }
}

void handleApiWindNow() {
  Serial.println("[API] POST /api/windnow");
  yield();
  if (server.hasArg("plain")) {
    String body = server.arg("plain");
    StaticJsonDocument<128> doc;
    deserializeJson(doc, body);
    
      int duration = doc["duration"] | 30;
      Serial.printf("[API] Winding for %d minutes\n", duration);

      writeFile("/Config/duration.txt", String(duration));

      String speedStr = "Medium";
      if (doc.containsKey("speed")) {
        speedStr = String(doc["speed"].as<const char*>());
      }

      float rpm = StepperMotorDriver::speedStringToRPM(speedStr);
      Serial.printf("[API] Using winding speed: %s (%.1f RPM)\n", speedStr.c_str(), rpm);

      bool clockwise = true;
      if (doc.containsKey("direction")) {
        String dirStr = String(doc["direction"].as<const char*>());
        if (dirStr == "CCW" || dirStr == "ccw" || dirStr == "counterclockwise") clockwise = false;
      }

      stepper.runForDuration((float)duration, rpm, clockwise);

      server.send(200, "application/json", "{\"status\":\"ok\",\"message\":\"Winding started\"}");
  } else {
    server.send(400, "application/json", "{\"status\":\"error\",\"error\":\"No data\"}");
  }
}

void handleApiMotorGet() {
  Serial.println("[API] GET /api/motor");
  yield();
  String motorData = readFile("/Config/motor.txt");
  if (motorData.length() > 0) {
    server.send(200, "application/json", motorData);
  } else {
    server.send(404, "application/json", "{\"error\":\"Motor config not found\"}");
  }
}

void handleApiMotorPost() {
  Serial.println("[API] POST /api/motor");
  yield();
  if (server.hasArg("plain")) {
    String body = server.arg("plain");
    if (writeFile("/Config/motor.txt", body)) {
      server.send(200, "application/json", "{\"status\":\"ok\"}");
    } else {
      server.send(500, "application/json", "{\"status\":\"error\",\"error\":\"Failed to save\"}");
    }
  } else {
    server.send(400, "application/json", "{\"status\":\"error\",\"error\":\"No data\"}");
  }
}

void handleApiMemory() {
  Serial.println("[API] GET /api/system/memory");
  yield();
  StaticJsonDocument<128> doc;
  doc["free_memory"] = ESP.getFreeHeap();
  
  String response;
  serializeJson(doc, response);
  server.send(200, "application/json", response);
}

void handleApiUptime() {
  Serial.println("[API] GET /api/system/uptime");
  yield();
  StaticJsonDocument<128> doc;
  doc["uptime"] = millis() / 1000;
  
  String response;
  serializeJson(doc, response);
  server.send(200, "application/json", response);
}

void handleApiEvents() {
  Serial.println("[API] GET /api/events");
  yield();
  StaticJsonDocument<512> doc;
  JsonArray events = doc.createNestedArray("events");
  events.add("System started");
  events.add("WiFi connected");
  events.add("Web server started");
  
  String response;
  serializeJson(doc, response);
  server.send(200, "application/json", response);
}

void handleApiCheckUpdate() {
  String localVersion = OtaUpdate::getLocalVersion();
  String remoteVersion = OtaUpdate::getRemoteVersion(OTA_VERSION_URL);
  bool updateAvailable = (remoteVersion.length() > 0 && remoteVersion != localVersion);
  String response = String("{\"local_version\":\"") + localVersion + "\",\"remote_version\":\"" + remoteVersion + "\",\"update_available\":" + (updateAvailable ? "true" : "false") + "}";
  server.send(200, "application/json", response);
}

void handleApiDoUpdate() {
  bool ok = OtaUpdate::updateFirmware(OTA_BIN_URL);
  if (ok) {
    server.send(200, "application/json", "{\"status\":\"ok\"}");
    delay(1000);
    ESP.restart();
  } else {
    server.send(500, "application/json", "{\"status\":\"error\",\"error\":\"OTA failed\"}");
  }
}

void setup() {
  Serial.begin(115200);
  Serial.println("[setup] Booting...");
  Serial.println("[setup] Waiting 5 seconds after boot...");
  delay(5000);

  WiFiManager wifiManager;
  wifiManager.setTimeout(180);
  if (!wifiManager.autoConnect("WatchWinder-Setup")) {
    Serial.println("[setup] Failed to connect and no config provided. Rebooting...");
    delay(3000);
    ESP.restart();
  }

  Serial.print("[setup] Connected! IP address: ");
  Serial.println(WiFi.localIP());

  NtfyClient ntfy(NTFY_TOPIC);
  String msg = String("{\"Watch Winder is up and running at http://") + WiFi.localIP().toString() + String("\"}");
  ntfy.send(msg);

  configTime(0, 0, "pool.ntp.org", "time.nist.gov");
  Serial.print("[setup] Waiting for NTP time sync...");
  time_t now = time(nullptr);
  while (now < 1640995200) {
    delay(500);
    Serial.print(".");
    now = time(nullptr);
  }
  Serial.println(" done.");

  if (!LittleFS.begin()) {
    Serial.println("[setup] Failed to mount file system");
    return;
  }
  Serial.println("[setup] LittleFS mounted successfully");
  
  loadNextWindingTime();
  
  Dir dir = LittleFS.openDir("/");
  while (dir.next()) {
    Serial.print("  FILE: ");
    Serial.print(dir.fileName());
    Serial.print("  SIZE: ");
    Serial.println(dir.fileSize());
  }
  
  server.on("/", handleRoot);
  server.on("/index.html", handleRoot);
  server.on("/setschedule.html", handleSetSchedule);
  server.on("/windnow.html", handleWindNow);
  server.on("/troubleshooting.html", handleTroubleshooting);
  
  server.on("/api/home", HTTP_GET, handleApiHome);
  server.on("/api/schedule", HTTP_GET, handleApiScheduleGet);
  server.on("/api/schedule", HTTP_POST, handleApiSchedulePost);
  server.on("/api/windnow", HTTP_POST, handleApiWindNow);
  server.on("/api/motor", HTTP_GET, handleApiMotorGet);
  server.on("/api/motor", HTTP_POST, handleApiMotorPost);
  server.on("/api/config", HTTP_GET, handleApiConfig);
  server.on("/api/system/memory", HTTP_GET, handleApiMemory);
  server.on("/api/system/uptime", HTTP_GET, handleApiUptime);
  server.on("/api/events", HTTP_GET, handleApiEvents);
  server.on("/api/check_update", HTTP_GET, handleApiCheckUpdate);
  server.on("/api/do_update", HTTP_POST, handleApiDoUpdate);
  
  server.on("/css/styles.css", handleStaticFile);
  server.onNotFound(handleStaticFile);
  
  server.begin();
  Serial.println("[setup] HTTP server started");
}

void loop() {
  server.handleClient();
  stepper.update();
  
  unsigned long nowMillis = millis();
  time_t nowEpoch = time(nullptr);
  unsigned long checkInterval = SCHEDULE_CHECK_INTERVAL;
  if (nextWindingEpoch > 0 && nowEpoch < nextWindingEpoch) {
    unsigned long diff = (unsigned long)(nextWindingEpoch - nowEpoch) * 1000UL;
    if (diff < SCHEDULE_CHECK_INTERVAL) checkInterval = diff;
  }
  if (nowMillis - lastScheduleCheck > checkInterval) {
    lastScheduleCheck = nowMillis;
    if (nextWindingEpoch > 0 && nowEpoch >= nextWindingEpoch && !scheduledWindingInProgress) {
      int duration;
      String speed;
      getWindingParams(duration, speed);
      float rpm = StepperMotorDriver::speedStringToRPM(speed);
      Serial.printf("[SCHEDULE] Starting scheduled winding: %d min, %s (%.1f RPM)\n", duration, speed.c_str(), rpm);
      stepper.runForDuration((float)duration, rpm, true);
      scheduledWindingInProgress = true;
    }
  }
  if (scheduledWindingInProgress && !stepper.isRunning()) {
    Serial.println("[SCHEDULE] Scheduled winding finished. Updating next_winding.txt...");
    scheduledWindingInProgress = false;
    updateNextWindingTime();
  }
  
  yield();
  static unsigned long lastPrint = 0;
  if (millis() - lastPrint > 5000) {
    Serial.printf("[loop] Running... Free heap: %u\n", ESP.getFreeHeap());
    lastPrint = millis();
  }
}