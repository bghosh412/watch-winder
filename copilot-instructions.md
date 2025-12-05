# CRITICAL: All backend code (in Code/backend/) MUST use only MicroPython-compatible libraries and APIs. Do NOT use standard Python modules that are not available in MicroPython (e.g., datetime, requests, pathlib, etc). Always prefer MicroPython's built-in modules (e.g., time, os, machine, network, ujson, etc) and test for compatibility on ESP32-C3.

# Watch Winder - AI Coding Agent Instructions

## Project Overview

ESP32-C3-based automatic watch winder using MicroPython. Supports:

- **Always-on server mode**: Custom HTTP API server for real-time web control

## Architecture

### Two Distinct Codebases

1. **Backend** (`Code/backend/`) - MicroPython for ESP32-C3 microcontroller
2. **Frontend** (`Code/frontend/`) - Vanilla HTML/CSS/JS web interface

**Critical**: These are separate execution environments. Backend runs on embedded hardware, frontend is browser-based. No shared runtime or modules.

### Backend Modes

- **Battery-Powered (Scheduled)**: Entry `main.py`. Wake → check schedule → wind if needed → deep sleep.
- **Always-On API Server**: Entry `api.py` (custom HTTP server). Real-time control via REST API, JSON files in `data/` for persistence.

### Backend Structure (MicroPython)

```
Code/backend/
├── main.py              # Entry point: schedule check → wind → deep sleep (battery mode)
├── api.py               # Custom HTTP API server for web control (always-on mode)
├── config.py            # All hardware pins, WiFi, schedule config
├── services.py          # Schedule data operations
├── last_winding_service.py  # Last winding timestamp tracking
├── next_winding_service.py  # Next scheduled winding calculation
├── duration_service.py      # windings duration
├── urequests.py         # HTTP client library (MicroPython)
├── data/                # JSON persistence layer (API mode only)
│   ├── schedule.json    # Winding schedule with times/days
│   ├── last_winding.json# Last winding timestamp
│   ├── next_winding.json# Calculated next winding time
│   └── duration.json    # windings duration in minutes
├── ota/                 # OTA (Over-The-Air) update system
│   ├── version.json     # Current installed firmware version
│   ├── ota_updater.py   # OTA update logic (downloads from GitHub)
│   └── README.md        # OTA documentation
├── UI/                  # Static files served by api.py

└── lib/
    ├──
```

**Service Layer Pattern**:

- All data operations abstracted into service modules (`*_service.py`)
- Read/write JSON files for persistence in API server mode
- ISO 8601 timestamp format: `YYYY-MM-DDTHH:MM:SS`
- Schedule format: `{"winding_times": [{"hour": 8, "minute": 0, "ampm": "AM", "enabled": true}], "days": {"Monday": true, ...}}`

**Power-critical patterns**:

- WiFi only enabled during notifications, immediately disconnected after
- Stepper powered off via `motor.off()` after every winding
- Deep sleep between cycles: `machine.deepsleep(DEEP_SLEEP_MINUTES * 60 * 1000000)`
- Debug output disabled in production: `esp.osdebug(None)`

### Frontend Structure

- Pure vanilla JS/HTML/CSS - no frameworks, no build tools
- Component-based with dynamic loading (`loadComponent()` in `app.js`)
- API calls to backend endpoints
- Status polling every 30 seconds for connection monitoring

**CRITICAL - Frontend Development Workflow**:

- **ALL frontend changes MUST be made in `Code/frontend/` folder ONLY**
- Never edit files directly in `Code/backend/UI/` - they are auto-generated and will be overwritten
- The build process (`build_backend.sh`) automatically:
  1. Builds frontend from `Code/frontend/` → `Code/frontend/dist/`
  2. Copies `Code/frontend/dist/` → `Code/backend/UI/`
  3. Copies `Code/backend/UI/` → `Code/backend/dist/UI/`
- Any manual changes to `Code/backend/UI/` will be lost on next build
- To update HTML/CSS/JS: Edit in `Code/frontend/`, run `npm run build`, then `build_backend.sh`

**API Integration Pattern**:
Frontend (`app.js`) expects these endpoints:

- `POST /api/wind` → manual winding trigger
- `POST /api/schedule` → create/update schedule
- `GET /api/schedules` → list all schedules
- `DELETE /api/schedule/{id}` → remove schedule
- `GET /api/status` → system health check

Backend (`api.py`) actual endpoints (adapt as needed for watch winder):

- `POST /api/windnow` → manual winding (reduces quantity, updates last_winding)
- `POST /api/schedule` → save schedule (calculates next_winding)
- `GET /api/schedule` → read schedule
- `POST /api/quantity` → update quantity
- `GET /api/home` → combined status (connection, quantity, last_winding, battery, next_winding)
- `GET /api/ping` → health check

**Note**: There's an endpoint mismatch between frontend expectations and backend implementation. Frontend needs updating or backend needs `/api/schedules` (plural) endpoint.

## Hardware Configuration

### GPIO Pin Assignments (ESP32-C3)

**Stepper Motor (ULN2003 driver, 28BYJ-48)**:

- IN1 → configurable in `config.py`
- IN2 → configurable in `config.py`
- IN3 → configurable in `config.py`
- IN4 → configurable in `config.py`

**DS3231 RTC (I2C)**:

- SDA → configurable in `config.py`
- SCL → configurable in `config.py`

**All pins configured in `config.py`** - modify there, not in driver files.

### Stepper Motor Specifics

- 28BYJ-48 with half-step sequence (8 steps/cycle)
- 4096 half-steps = 360° rotation
- `MOTOR_STEPS_PER_WINDING = 512` in config (one full rotation, adjust as needed)
- Delay between steps: `MOTOR_SPEED_MS = 2` (configurable for speed vs. power)

## Development Workflows

### IMPORTANT: Virtual Environment

**ALWAYS activate the virtual environment before running any commands:**

```bash
source venv/bin/activate
```

### Local Testing (Without Hardware)

```bash
# Activate venv first
source venv/bin/activate

# Syntax validation
micropython -m py_compile Code/backend/main.py

# Simulation test (no hardware required)
micropython Tests/test_simulation.py
```

### Hardware Testing

```bash
# Activate venv first
source venv/bin/activate

# Test individual components
micropython Tests/test_motor.py    # Motor control verification
micropython Tests/test_rtc.py      # RTC communication test
```

### Build Process (Compile Only - DO NOT Upload)

**After making changes, ALWAYS build/compile but DO NOT automatically upload to ESP32-C3:**

```bash
source venv/bin/activate
cd Code/backend
./build_backend.sh api   # For API mode
# OR
./build_backend.sh battery   # For battery mode
```

**Manual Upload Instructions** (only when user explicitly requests deployment):

```bash
cd Code/backend/dist
ampy -p /dev/ttyUSB0 -b 115200 put api.py
# ... etc
```

### Deployment to ESP32-C3

**CRITICAL**: After code changes:

1. ✅ Run build script to compile and prepare files
2. ❌ DO NOT automatically upload to device
3. ✅ Show user what files are ready in `dist/` folder
4. ✅ Wait for user to explicitly request upload/deployment

## Key Conventions

### Configuration Over Code

**Always modify `config.py` for**:

- Winding schedule (`WINDING_TIMES = [(8, 0), (20, 0)]` - 24hr format)
- WiFi credentials
- Motor parameters (steps, speed)
- GPIO pin assignments
- Deep sleep duration
- ntfy notification settings

### Winding Logic (`main.py`)

1. Wake from deep sleep (RTC maintains time)
2. Initialize RTC, read current time
3. Compare against `WINDING_TIMES` schedule
4. If match: execute `wind()` → send notification
5. Enter deep sleep for `DEEP_SLEEP_MINUTES`

**Timing tolerance**: Matches winding time within 1 minute window

### Notification Pattern

Uses ntfy.sh for push notifications:

```python
notifier = NotificationService(config.NTFY_SERVER, config.NTFY_TOPIC)
notifier.send_winding_notification(time_str)  # Success
notifier.send_error_notification(error_msg)   # Errors
```

Subscribe to notifications: `https://ntfy.sh/<NTFY_TOPIC>` on phone

## Common Tasks

### Adding New Winding Time

Edit `config.py`:

```python
WINDING_TIMES = [
    (8, 0),   # 8:00 AM
    (12, 0),  # 12:00 PM (NEW)
    (20, 0),  # 8:00 PM
]
```

### Adjusting Motor Rotation

Modify in `config.py`:

```python
MOTOR_STEPS_PER_WINDING = 1024  # Double rotation
MOTOR_SPEED_MS = 5              # Slower speed (higher = slower)
```

### Changing Deep Sleep Duration

```python
DEEP_SLEEP_MINUTES = 15  # Check every 15 minutes instead of 30
```

### Adding/Removing API Endpoints in api.py

**CRITICAL**: `api.py` uses a custom HTTP server (SimpleServer class), NOT decorators like Flask/Microdot.

**Pattern**: All endpoints are handled in if/elif chains within the request handling logic.

**To add a new endpoint**:

1. Locate the endpoint handling section (search for `elif path == '/api/`)
2. Add your endpoint BEFORE the static file serving section (`elif path == '/' or path == '/index.html'`)
3. Use this pattern:

```python
elif path == '/api/your_endpoint':
    if method == 'GET':  # or 'POST', 'DELETE', etc.
        try:
            # Your endpoint logic here
            result = json_encode({'key': 'value'})
            send_response(conn, '200 OK', 'application/json', result)
            del result  # Memory cleanup
            gc.collect()
        except Exception as e:
            print('Error:', e)
            error_msg = json_encode({'error': str(e)})
            send_response(conn, '500 Internal Server Error', 'application/json', error_msg)
            gc.collect()
    else:
        send_response(conn, '405 Method Not Allowed', 'application/json', json_encode({'error': 'Only GET allowed'}))
        gc.collect()
```

**Memory management**: Always `del` large variables and call `gc.collect()` after sending responses.

**Example endpoints** (search these in api.py for reference):

- `/api/windnow` - POST endpoint with body parsing
- `/api/quantity` - GET and POST methods
- `/api/home` - Combines multiple data sources
- `/api/ota/check` - OTA update check
- `/api/ota/update` - OTA download and apply

**To remove an endpoint**: Delete the entire `elif path == '/api/endpoint':` block.

### Frontend API Integration

Backend API endpoints expected at `/api/*`:

- `POST /api/wind` - Manual winding trigger
- `POST /api/schedule` - Add winding schedule
- `GET /api/schedules` - List all schedules
- `DELETE /api/schedule/{id}` - Remove schedule
- `GET /api/status` - System health check

## Running the API Server (Development Mode)

### Raspberry Pi / Linux

```bash
source venv/bin/activate
cd /home/pi/Desktop/WatchWinder/Code/backend
python3 api.py
```

### Windows (PowerShell)

```powershell
.\venv\Scripts\Activate.ps1
cd Code\backend
micropython api.py
```

Server always runs on port 5000. Frontend must use `http://localhost:5000` for all API calls.

## Testing Strategy

**Always test in this order**:

1. **Activate venv**: `source venv/bin/activate`
2. Syntax check: `micropython -m py_compile <file>`
3. Build: `./build_backend.sh api` (compiles to `dist/` folder)
4. Simulation: `micropython Tests/test_simulation.py`
5. Component tests: `test_motor.py`, `test_rtc.py`
6. Wokwi simulation (if modifying hardware interactions)
7. **STOP HERE** - Wait for user to explicitly request deployment
8. ESP32-C3 deployment (only when user asks)

## Important Constraints

- **File size**: Keep code minimal - ESP32-C3 has limited flash/RAM
- **Import errors in IDE**: Expected - uses MicroPython libraries not available in standard Python
- **WiFi**: Only 2.4GHz networks supported by ESP32-C3
- **Deep sleep**: Device loses RAM state - RTC maintains time externally
- **Battery life**: Design decisions prioritize power efficiency over features

## OTA (Over-The-Air) Update System

### Overview

Memory-efficient firmware update system that downloads only changed files from GitHub.

### Architecture

- **Surge Deployment**: http://winder-ota.surge.sh (mirrors `Code/backend/dist/` structure)
- **Local Version**: `ota/version.json` on ESP32-C3
- **Remote Version**: `version.json` at Surge base URL
- **Update Logic**: `ota/ota_updater.py`

### How It Works

1. **Version Check**: ESP32-C3 compares local `ota/version.json` with remote version from GitHub
2. **File Download**: If versions differ, downloads files listed in remote `version.json` one-by-one
3. **Atomic Update**: Each file downloaded to `.tmp`, then atomically renamed (rollback-safe)
4. **Memory Efficient**: Downloads 512-byte chunks, frequent `gc.collect()`, ~10-20KB RAM usage
5. **Reboot**: After successful update, device reboots to apply changes

### version.json Format

```json
{
  "version": "1.0.0",
  "date": "2025-12-05",
  "files": [
    "api.py",
    "services.py",
    "lib/stepper.py",
    "UI/index.html"
  ],
  "notes": "Initial release"
}
```

**Important**:

- File paths are relative to repo root (which mirrors `dist/` folder)
- Each new version should include ALL files from previous releases that still need updating
- `data/` directory files are NEVER included in OTA updates (preserves user settings)

### API Endpoints

- `GET /api/ota/check` - Check if update available
- `POST /api/ota/update` - Download and apply update
- `POST /api/system/reboot` - Reboot device

### Web UI

Troubleshooting page (`troubleshooting.html`) includes OTA update buttons:

- "Check for Updates" - Queries `/api/ota/check`
- "Download Update" - Triggers `/api/ota/update`, auto-reboots after 5 seconds

## Documentation

- Full project details: `Instructions/instructions.md`
- Backend testing guide: `Code/backend/README.md`
- Frontend setup: `Code/frontend/README.md`
- Test suite info: `Tests/README.md`
- OTA system: `Code/backend/ota/README.md`
