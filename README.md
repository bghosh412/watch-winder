# Watch Winder Project

ESP32-C3 based automatic watch winder with web interface.

## Hardware

- ESP32-C3 microcontroller
- 28BYJ-48 stepper motor with ULN2003 driver
- MicroPython firmware

## Flashing MicroPython to ESP32-C3

Use the following command to flash custom MicroPython firmware to ESP32-C3:

```bash
esptool.py --chip esp32c3 --port /dev/ttyACM0 write_flash --force -z \
  0x0 /home/pi/micropython/ports/esp32/build/bootloader/bootloader.bin \
  0x8000 /home/pi/micropython/ports/esp32/build/partition_table/partition-table.bin \
  0x10000 /home/pi/micropython/ports/esp32/build/micropython.bin
```

**Note:** Ensure MicroPython is built for ESP32-C3 using `make BOARD=ESP32_GENERIC_C3`

## Development Setup

1. Install Node.js dependencies:
   ```bash
   npm install
   ```

2. Build the project:
   ```bash
   node build_backend.js
   ```

3. Test the API server locally:
   ```bash
   cd Code/backend/dist
   micropython api.py
   ```

## Project Structure

- `Code/backend/` - MicroPython backend code
- `Code/frontend/` - HTML/CSS/JS web interface
- `build_backend.js` - Build script to prepare deployment files
- `Code/backend/dist/` - Compiled output ready for ESP32-C3 deployment

## Documentation

See `copilot-instructions.md` for detailed development guidelines.
