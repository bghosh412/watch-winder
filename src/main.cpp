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
#define STEPPER_IN4 D5 // Changed from D4 to D5 to avoid onboard LED

ESP8266WebServer server(80);
StepperMotorDriver stepper(STEPPER_IN1, STEPPER_IN2, STEPPER_IN3, STEPPER_IN4);

// Forward declarations
void serveHTML(const char* path);
String readFile(const char* path);
bool writeFile(const char* path, const String& content);
void updateNextWindingTime();
void loadNextWindingTime();
void saveLastWindingTime();
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
void handleApiStop();
void handleStaticFile();

// Scheduled winding state
time_t nextWindingEpoch = 0;
unsigned long lastScheduleCheck = 0;
const unsigned long SCHEDULE_CHECK_INTERVAL = 300 * 1000UL; // 300 seconds
bool scheduledWindingInProgress = false;
bool manualWindingInProgress = false;

// Helper function implementations
String readFile(const char* path) {
  File file = LittleFS.open(path, "r");
  if (!file) {
    Serial.printf("[readFile] Failed to open: %s\n", path);
    return "";
  }
  String content = file.readString();
  file.close();
  content.trim();
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

void saveLastWindingTime() {
  time_t now = time(nullptr);
  struct tm t;
  localtime_r(&now, &t);
  String iso = formatISO8601(t);
  writeFile("/Config/last_winding.txt", iso);
  Serial.printf("[WINDING] Last winding time saved: %s\n", iso.c_str());
  iso = String();
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
    doc.clear();
  }
  sched = String();
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
      // Skip if this time slot is disabled
      if (timeObj.containsKey("enabled") && !timeObj["enabled"].as<bool>()) continue;
      
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
    iso = String();
  } else {
    Serial.println("[SCHEDULE] No valid next winding time found.");
  }
  
  // Cleanup
  doc.clear();
  sched = String();
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

  String lastWindingStr = readFile("/Config/last_winding.txt");
  String nextWindingStr = readFile("/Config/next_winding.txt");
  String quantity = readFile("/Config/quantity.txt");

  StaticJsonDocument<256> doc;
  
  // Connection status
  doc["connectionStatus"] = (WiFi.status() == WL_CONNECTED) ? "Online" : "Offline";
  
  // Last winding time (ISO format from file)
  if (lastWindingStr.length() > 0) {
    doc["lastWinding"] = lastWindingStr;
  }
  
  // Next winding time (ISO format from file)
  if (nextWindingStr.length() > 0) {
    doc["nextWinding"] = nextWindingStr;
  } else {
    doc["nextWinding"] = "Not scheduled";
  }
  
  // Wind remaining (not implemented, placeholder)
  doc["windRemaining"] = "N/A";
  
  // Battery status (not implemented, placeholder)
  doc["batteryStatus"] = "N/A";

  String response;
  serializeJson(doc, response);
  server.send(200, "application/json", response);
  
  // Cleanup
  doc.clear();
  lastWindingStr = String();
  nextWindingStr = String();
  quantity = String();
  response = String();
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
      doc.clear();
    } else {
      server.send(400, "application/json", "{\"status\":\"error\",\"error\":\"Invalid JSON\"}");
    }
  } else {
    server.send(404, "application/json", "{\"error\":\"Schedule not found\"}");
  }
  scheduleData = String();
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
      doc.clear();
      out = String();
    } else {
      server.send(400, "application/json", "{\"status\":\"error\",\"error\":\"Invalid JSON\"}");
    }
    body = String();
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
      manualWindingInProgress = true;

      server.send(200, "application/json", "{\"status\":\"ok\",\"message\":\"Winding started\"}");
      
      // Cleanup
      doc.clear();
      speedStr = String();
      body = String();
  } else {
    server.send(400, "application/json", "{\"status\":\"error\",\"error\":\"No data\"}");
  }
}

void handleApiStop() {
  Serial.println("[API] POST /api/stop - Stopping winding");
  stepper.stop();
  scheduledWindingInProgress = false;
  server.send(200, "application/json", "{\"status\":\"ok\",\"message\":\"Winding stopped\"}");
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
  
  // Cleanup
  localVersion = String();
  remoteVersion = String();
  response = String();
}

void handleApiDoUpdate() {
  // Get the remote version first
  String remoteVersion = OtaUpdate::getRemoteVersion(OTA_VERSION_URL);
  if (remoteVersion.length() == 0) {
    Serial.println("[OTA] Failed to fetch remote version");
    server.send(500, "application/json", "{\"status\":\"error\",\"error\":\"Failed to fetch remote version\"}");
    remoteVersion = String();
    return;
  }
  
  Serial.printf("[OTA] Updating from local version to remote version: %s\n", remoteVersion.c_str());
  remoteVersion = String();  // Free memory before OTA
  
  // Send response before starting OTA (connection will be lost during update)
  server.send(200, "application/json", "{\"status\":\"starting\"}");
  server.handleClient();
  delay(500);
  
  // Stop motor if running
  if (stepper.isRunning()) {
    Serial.println("[OTA] Stopping motor for OTA update...");
    stepper.stop();
    delay(100);
  }
  
  // Stop web server to free resources
  Serial.println("[OTA] Stopping web server...");
  server.stop();
  delay(100);
  
  // Close LittleFS to free resources
  Serial.println("[OTA] Closing file system...");
  LittleFS.end();
  delay(100);
  
  // Update firmware (this will reboot automatically on success)
  Serial.println("[OTA] Starting firmware update...");
  bool fwOk = OtaUpdate::updateFirmware(OTA_BIN_URL);
  
  // If firmware update succeeded, it would have rebooted. If we're here, it failed.
  if (!fwOk) {
    Serial.println("[OTA] Firmware update failed. Restarting web server...");
    server.begin();
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
  String msg = String("") + NTFY_MSG_STARTUP_PREFIX + WiFi.localIP().toString() + NTFY_MSG_STARTUP_SUFFIX + String("");
  ntfy.send(msg);

  configTime(5.5 * 3600, 0, "pool.ntp.org", "time.nist.gov");  // IST is UTC+5:30
  Serial.print("[setup] Waiting for NTP time sync (India/Kolkata)...");
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
  
  // Sync firmware version to file if different
  String localVer = OtaUpdate::getLocalVersion();
  if (localVer != FIRMWARE_VERSION) {
    Serial.printf("[setup] Version mismatch! File: %s, Firmware: %s\n", localVer.c_str(), FIRMWARE_VERSION);
    Serial.println("[setup] Updating version file...");
    OtaUpdate::setLocalVersion(FIRMWARE_VERSION);
  } else {
    Serial.printf("[setup] Firmware version: %s\n", FIRMWARE_VERSION);
  }
  
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
  server.on("/api/stop", HTTP_POST, handleApiStop);
  
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
      
      // Update next winding time immediately after starting
      Serial.println("[SCHEDULE] Updating next winding time...");
      updateNextWindingTime();
    }
  }
  if (scheduledWindingInProgress && !stepper.isRunning()) {
    Serial.println("[SCHEDULE] Scheduled winding finished.");
    scheduledWindingInProgress = false;
    saveLastWindingTime();
  }
  
  if (manualWindingInProgress && !stepper.isRunning()) {
    Serial.println("[MANUAL] Manual winding finished.");
    manualWindingInProgress = false;
    saveLastWindingTime();
  }
  
  yield();
  
  // Periodic heap monitoring and garbage collection
  static unsigned long lastPrint = 0;
  static unsigned long lastGC = 0;
  unsigned long now = millis();
  
  if (now - lastPrint > 5000) {
    Serial.printf("[loop] Running... Free heap: %u\n", ESP.getFreeHeap());
    lastPrint = now;
  }
  
  // Force periodic WiFi stack cleanup every 60 seconds
  if (now - lastGC > 60000) {
    ESP.wdtFeed();  // Feed watchdog
    lastGC = now;
  }
}