#ifndef NTFY_CLIENT_H
#define NTFY_CLIENT_H

#include <ESP8266WiFi.h>
#include <ESP8266HTTPClient.h>

class NtfyClient {
public:
    NtfyClient(const String& topic) : _topic(topic) {}

    bool send(const String& message) {
        if (WiFi.status() != WL_CONNECTED) {
            Serial.println("[NtfyClient] WiFi not connected");
            return false;
        }
        WiFiClient client;
        HTTPClient http;
        String url = "http://ntfy.sh/" + _topic;
        http.begin(client, url);
        http.addHeader("Content-Type", "text/plain");
        http.addHeader("Title", "Watch Winder");
        int httpCode = http.POST(message);
        if (httpCode > 0) {
            Serial.printf("[NtfyClient] Sent to topic '%s': %s (code: %d)\n", _topic.c_str(), message.c_str(), httpCode);
            http.end();
            return true;
        } else {
            Serial.printf("[NtfyClient] Failed to send to topic '%s': %s (code: %d)\n", _topic.c_str(), message.c_str(), httpCode);
            http.end();
            return false;
        }
    }

private:
    String _topic;
};

#endif // NTFY_CLIENT_H
