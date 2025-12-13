#ifndef OTA_UPDATE_H
#define OTA_UPDATE_H

#include <ESP8266HTTPClient.h>
#include <ESP8266httpUpdate.h>
#include <LittleFS.h>
#include "ConfigConstants.h"

class OtaUpdate {
public:
    static String getLocalVersion() {
        File file = LittleFS.open("/version/version.txt", "r");
        if (!file) return "0.0.0";
        String v = file.readString();
        file.close();
        v.trim();
        return v;
    }

    static String getRemoteVersion(const String& url = OTA_VERSION_URL) {
        WiFiClientSecure client;
        client.setInsecure();
        HTTPClient http;
        if (!http.begin(client, url)) return "";
        int httpCode = http.GET();
        if (httpCode != 200) {
            http.end();
            return "";
        }
        String v = http.getString();
        http.end();
        v.trim();
        return v;
    }

    static bool updateFirmware(const String& binUrl = OTA_BIN_URL) {
        WiFiClientSecure client;
        client.setInsecure();
        t_httpUpdate_return ret = ESPhttpUpdate.update(client, binUrl);
        return (ret == HTTP_UPDATE_OK);
    }
};

#endif // OTA_UPDATE_H
