#ifndef CONFIG_CONSTANTS_H
#define CONFIG_CONSTANTS_H

// Firmware version (update this with each release)
#define FIRMWARE_VERSION "1.0.11"

// OTA update URLs
#define OTA_VERSION_URL "https://raw.githubusercontent.com/bghosh412/OTA/main/WW-OTA/version.txt"
#define OTA_BIN_URL     "https://raw.githubusercontent.com/bghosh412/OTA/main/WW-OTA/firmware.bin"
#define OTA_LFS_URL     "https://raw.githubusercontent.com/bghosh412/OTA/main/WW-OTA/littlefs.bin"


// Ntfy topic and message templates
#define NTFY_TOPIC "ww-dad-01"
#define NTFY_MSG_STARTUP_PREFIX "Watch Winder is up and running at http://"
#define NTFY_MSG_STARTUP_SUFFIX ""
#define NTFY_MSG_WINDING "Winding started at %s and will wind your favorite Automatic Watch for next %.1f min, at %.1f RPM."
#define NTFY_MSG_WINDING_COMPLETE "Winding completed at %s. Your watch is ready!"

// WiFi credentials (optionally move to secrets file)
#define WIFI_SSID     ""
#define WIFI_PASSWORD ""

#endif // CONFIG_CONSTANTS_H
