#include <Arduino.h>
#include <ESP8266WiFi.h>
#include <ESP8266WebServer.h>
#include <LittleFS.h>
#include <ArduinoJson.h>

const char* ssid = "Ghuntu";
const char* password = "dkg98310";

ESP8266WebServer server(80);

// Helper function to read file content
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

// Helper function to write file content
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

// Serve HTML pages
void serveHTML(const char* path) {
  File file = LittleFS.open(path, "r");
  if (!file) {
    server.send(404, "text/html", "<html><body>File not found</body></html>");
    return;
  }
  server.streamFile(file, "text/html");
  file.close();
}

// Serve static assets (CSS, JS, images)
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

// GET /api/home - Home page data
void handleApiHome() {
  Serial.println("[API] GET /api/home");
  yield();
  StaticJsonDocument<512> doc;
  
  doc["connectionStatus"] = "Online";
  doc["windRemaining"] = "6 more winds remaining";
  doc["lastWinding"] = readFile("/Config/last_winding.txt");
  doc["batteryStatus"] = "40% of the Battery remaining";
  doc["nextWinding"] = readFile("/Config/next_winding.txt");
  
  String response;
  serializeJson(doc, response);
  server.send(200, "application/json", response);
}

// GET /api/schedule - Get winding schedule
void handleApiScheduleGet() {
  Serial.println("[API] GET /api/schedule");
  yield();
  String scheduleData = readFile("/Config/schedule.txt");
  if (scheduleData.length() > 0) {
    StaticJsonDocument<512> doc;
    DeserializationError err = deserializeJson(doc, scheduleData);
    if (!err) {
      // Ensure winding_speed is present (default to Medium if missing)
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

// POST /api/schedule - Save winding schedule
void handleApiSchedulePost() {
  Serial.println("[API] POST /api/schedule");
  yield();
  if (server.hasArg("plain")) {
    String body = server.arg("plain");
    StaticJsonDocument<512> doc;
    DeserializationError err = deserializeJson(doc, body);
    if (!err) {
      // Ensure winding_speed is present (default to Medium if missing)
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

// POST /api/windnow - Wind now with duration
void handleApiWindNow() {
  Serial.println("[API] POST /api/windnow");
  yield();
  if (server.hasArg("plain")) {
    String body = server.arg("plain");
    StaticJsonDocument<128> doc;
    deserializeJson(doc, body);
    
    int duration = doc["duration"] | 30;
    Serial.printf("[API] Winding for %d minutes\n", duration);
    
    // Save duration
    writeFile("/Config/duration.txt", String(duration));
    
    // TODO: Trigger actual motor winding
    
    server.send(200, "application/json", "{\"status\":\"ok\",\"message\":\"Winding started\"}");
  } else {
    server.send(400, "application/json", "{\"status\":\"error\",\"error\":\"No data\"}");
  }
}

// GET /api/motor - Get motor settings
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

// POST /api/motor - Save motor settings
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

// GET /api/config - Get system config
void handleApiConfig() {
  Serial.println("[API] GET /api/config");
  yield();
  StaticJsonDocument<256> doc;
  doc["ntfy_topic"] = "watch-winder";
  doc["wifi_ssid"] = ssid;
  
  String response;
  serializeJson(doc, response);
  server.send(200, "application/json", response);
}

// GET /api/system/memory - Get free memory
void handleApiMemory() {
  Serial.println("[API] GET /api/system/memory");
  yield();
  StaticJsonDocument<128> doc;
  doc["free_memory"] = ESP.getFreeHeap();
  
  String response;
  serializeJson(doc, response);
  server.send(200, "application/json", response);
}

// GET /api/system/uptime - Get system uptime
void handleApiUptime() {
  Serial.println("[API] GET /api/system/uptime");
  yield();
  StaticJsonDocument<128> doc;
  doc["uptime"] = millis() / 1000;
  
  String response;
  serializeJson(doc, response);
  server.send(200, "application/json", response);
}

// GET /api/events - Get event log
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

// HTML Page Handlers
void handleRoot() {
  Serial.println("[handleRoot] Serving index.html");
  serveHTML("/UI/index.html");
}

void handleSetSchedule() {
  Serial.println("[handleSetSchedule] Serving setschedule.html");
  serveHTML("/UI/setschedule.html");
}

void handleWindNow() {
  Serial.println("[handleWindNow] Serving windnow.html");
  serveHTML("/UI/windnow.html");
}

void handleTroubleshooting() {
  Serial.println("[handleTroubleshooting] Serving troubleshooting.html");
  serveHTML("/UI/troubleshooting.html");
}

void setup() {
  Serial.begin(115200);
  Serial.println("[setup] Booting...");
  Serial.println("[setup] Waiting 5 seconds after boot...");
  delay(5000);
  WiFi.begin(ssid, password);
  Serial.print("[setup] Connecting to WiFi");
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println();
  Serial.print("[setup] Connected! IP address: ");
  Serial.println(WiFi.localIP());

  // Mount LittleFS
  Serial.println("[setup] Mounting LittleFS filesystem...");
  if (!LittleFS.begin()) {
    Serial.println("[setup] Failed to mount file system");
    return;
  }
  Serial.println("[setup] LittleFS mounted successfully");
  
  // List all files in LittleFS for debugging
  Serial.println("[setup] Listing LittleFS files:");
  Dir dir = LittleFS.openDir("/");
  while (dir.next()) {
    Serial.print("  FILE: ");
    Serial.print(dir.fileName());
    Serial.print("  SIZE: ");
    Serial.println(dir.fileSize());
  }
  
  // No need to preload index.html; HTML is served directly from LittleFS.

  // HTML Pages
  server.on("/", handleRoot);
  server.on("/index.html", handleRoot);
  server.on("/setschedule.html", handleSetSchedule);
  server.on("/windnow.html", handleWindNow);
  server.on("/troubleshooting.html", handleTroubleshooting);
  
  // API Endpoints
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
  
  // Static assets (CSS, JS, images)
  server.on("/css/styles.css", handleStaticFile);
  server.onNotFound(handleStaticFile);
  
  server.begin();
  Serial.println("[setup] HTTP server started");
}

void loop() {
  server.handleClient();
  yield(); // Aggressive memory management
  // Print free heap every 5 seconds
  static unsigned long lastPrint = 0;
  if (millis() - lastPrint > 5000) {
    Serial.printf("[loop] Running... Free heap: %u\n", ESP.getFreeHeap());
    lastPrint = millis();
  }
}