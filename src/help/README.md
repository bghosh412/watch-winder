# ESP8266 PlatformIO Build & Monitor Guide

## Build Commands

To build the project:

```
platformio run --target clean

platformio run --target uploadfs

reset ESP8266

platformio run --target uploadfs
```

To build for a specific environment (e.g., d1_mini):

```
platformio run --environment d1_mini
```

To upload (flash) the firmware to the ESP8266:

```
platformio run --target upload
```

## Serial Monitor Commands

To open the serial monitor:

```
platformio device monitor
```

To specify a baud rate (e.g., 115200):

```
platformio device monitor --baud 115200
```

## Additional Tips

- Make sure your ESP8266 is connected and in flash mode for uploading.
- Check your `platformio.ini` for the correct board and port settings.
- Use `ls /dev/tty*` to find your device's serial port if needed.
