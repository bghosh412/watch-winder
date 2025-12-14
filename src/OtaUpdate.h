#ifndef OTA_UPDATE_H
#define OTA_UPDATE_H

#include <ESP8266HTTPClient.h>
#include <ESP8266httpUpdate.h>
#include <LittleFS.h>
#include "ConfigConstants.h"

class OtaUpdate {
public:
    static String getLocalVersion() {
        File file = LittleFS.open("/Config/version.txt", "r");
        if (!file) {
            Serial.println("[OTA] Version file not found, returning 0.0.0");
            return "0.0.0";
        }
        String v = file.readString();
        file.close();
        v.trim();
        Serial.printf("[OTA] Local version: %s\n", v.c_str());
        return v;
    }

    static bool setLocalVersion(const String& version) {
        // Ensure Config directory exists
        if (!LittleFS.exists("/Config")) {
            Serial.println("[OTA] Creating /Config directory");
            LittleFS.mkdir("/Config");
        }
        
        File file = LittleFS.open("/Config/version.txt", "w");
        if (!file) {
            Serial.println("[OTA] Failed to create version.txt");
            return false;
        }
        file.print(version);
        file.close();
        Serial.printf("[OTA] Version updated to: %s\n", version.c_str());
        return true;
    }

    static String getRemoteVersion(const String& url = OTA_VERSION_URL) {
        WiFiClientSecure client;
        client.setInsecure();
        HTTPClient http;
        if (!http.begin(client, url)) {
            Serial.println("[OTA] Failed to connect to version URL");
            return "";
        }
        int httpCode = http.GET();
        if (httpCode != 200) {
            Serial.printf("[OTA] Version fetch failed with code: %d\n", httpCode);
            http.end();
            return "";
        }
        String v = http.getString();
        http.end();
        v.trim();
        Serial.printf("[OTA] Remote version: %s\n", v.c_str());
        return v;
    }

    static bool updateFirmware(const String& binUrl = OTA_BIN_URL) {
        Serial.printf("[OTA] Free heap before update: %u bytes\n", ESP.getFreeHeap());
        
        // Use WiFiClientSecure with absolute minimal settings
        WiFiClientSecure client;
        client.setInsecure();  // Bypass SSL certificate validation
        //client.setBufferSizes(256, 512);  // Minimal RX buffer, standard TX
        
        // Disable session caching to save memory
        //client.setSession(nullptr);
        
        ESPhttpUpdate.setLedPin(LED_BUILTIN, LOW);
        ESPhttpUpdate.rebootOnUpdate(true);
        ESPhttpUpdate.setFollowRedirects(HTTPC_STRICT_FOLLOW_REDIRECTS);
        
        ESPhttpUpdate.onStart([]() {
            Serial.println("[OTA] Firmware download started...");
        });
        ESPhttpUpdate.onEnd([]() {
            Serial.println("[OTA] Firmware update completed! Device will reboot now...");
            Serial.flush();
        });
        ESPhttpUpdate.onProgress([](int cur, int total) {
            static int lastPercent = -1;
            int percent = (cur * 100) / total;
            if (percent != lastPercent && percent % 10 == 0) {
                Serial.printf("[OTA] Progress: %d%%\n", percent);
                lastPercent = percent;
            }
        });
        ESPhttpUpdate.onError([](int err) {
            Serial.printf("[OTA] Update error: %d - %s\n", err, ESPhttpUpdate.getLastErrorString().c_str());
        });
        
        yield();
        delay(500);  // Give WiFi time to stabilize
        
        t_httpUpdate_return ret = ESPhttpUpdate.update(client, binUrl);
        
        // If we reach here, update failed (success would have rebooted)
        if (ret == HTTP_UPDATE_OK) {
            Serial.println("[OTA] Firmware update successful - rebooting!");
            delay(100);
            ESP.restart();
            return true;
        } else if (ret == HTTP_UPDATE_NO_UPDATES) {
            Serial.println("[OTA] No firmware updates available");
            return false;
        } else {
            Serial.printf("[OTA] Firmware update failed: %d - %s\n", ret, ESPhttpUpdate.getLastErrorString().c_str());
            return false;
        }
    }

    static bool updateFilesystem(const String& lfsUrl = OTA_LFS_URL) {
        Serial.printf("[OTA] Starting filesystem update from: %s\n", lfsUrl.c_str());
        Serial.printf("[OTA] Free heap: %u bytes\n", ESP.getFreeHeap());
        
        // Close LittleFS early to free memory
        LittleFS.end();
        delay(100);
        
        Serial.printf("[OTA] Free heap after LittleFS close: %u bytes\n", ESP.getFreeHeap());
        
        // Use WiFiClientSecure with minimal settings for ESP8266
        WiFiClientSecure client;
        client.setInsecure();  // Bypass SSL certificate validation
        client.setBufferSizes(512, 512);  // Minimal buffers
        client.setTimeout(60000);  // 60 second timeout for larger file
        
        ESPhttpUpdate.rebootOnUpdate(false);
        ESPhttpUpdate.setFollowRedirects(HTTPC_STRICT_FOLLOW_REDIRECTS);
        
        ESPhttpUpdate.onStart([]() {
            Serial.println("[OTA] Filesystem update starting...");
        });
        ESPhttpUpdate.onEnd([]() {
            Serial.println("[OTA] Filesystem update completed!");
        });
        ESPhttpUpdate.onProgress([](int cur, int total) {
            static int lastPercent = -1;
            int percent = (cur * 100) / total;
            if (percent != lastPercent && percent % 10 == 0) {
                Serial.printf("[OTA] Filesystem progress: %d%%\n", percent);
                lastPercent = percent;
            }
        });
        ESPhttpUpdate.onError([](int err) {
            Serial.printf("[OTA] Filesystem update error: %d - %s\n", err, ESPhttpUpdate.getLastErrorString().c_str());
        });
        
        Serial.println("[OTA] Downloading and flashing filesystem...");
        yield();
        delay(500);  // Give WiFi time to stabilize
        
        t_httpUpdate_return ret = ESPhttpUpdate.updateFS(client, lfsUrl);
        
        if (ret == HTTP_UPDATE_OK) {
            Serial.println("[OTA] Filesystem update successful");
            return true;
        } else if (ret == HTTP_UPDATE_NO_UPDATES) {
            Serial.println("[OTA] No filesystem updates available");
            return false;
        } else {
            Serial.printf("[OTA] Filesystem update failed: %d - %s\n", ret, ESPhttpUpdate.getLastErrorString().c_str());
            return false;
        }
    }
};

#endif // OTA_UPDATE_H
