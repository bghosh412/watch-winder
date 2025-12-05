# CRITICAL: All backend code (in Code/backend/) MUST use only MicroPython-compatible libraries and APIs. Do NOT use standard Python modules that are not available in MicroPython (e.g., datetime, requests, pathlib, etc). Always prefer MicroPython's built-in modules (e.g., time, os, machine, network, ujson, etc) and test for compatibility on ESP8266/ESP32.
# Fish Feeder - AI Coding Agent Instructions

## Project Overview
ESP8266 automatic fish feeder using MicroPython. Supports **two deployment modes**:
- **Battery-powered mode**: Deep sleep cycles, minimal power usage (4 AA batteries)
- **Always-on server mode**: Microdot API server for real-time web control

## Architecture

### Two Distinct Codebases
1. **Backend** (`Code/backend/`) - MicroPython for ESP8266 microcontroller
2. **Frontend** (`Code/frontend/`) - Vanilla HTML/CSS/JS web interface

**Critical**: These are separate execution environments. Backend runs on embedded hardware (or Raspberry Pi for development), frontend is browser-based. No shared runtime or modules.

### Dual Backend Modes
The backend supports two operational modes with different entry points:

**Mode 1: Battery-Powered (Scheduled)**
- Entry: `main.py`
- Pattern: Wake → check schedule → feed if needed → deep sleep (30min)
- Power: Minimal WiFi usage (only for notifications)
- Use case: Production deployment on battery power

**Mode 2: Always-On API Server**
- Entry: `api.py` (Custom HTTP server using SimpleServer class)
- Pattern: HTTP server on port 5000, real-time control via REST API
- Persistence: JSON files in `data/` directory (`schedule.json`, `last_fed.json`, `next_feed.json`, `quantity.json`)
- Use case: Development on Raspberry Pi, or mains-powered ESP32 with web interface
- **IMPORTANT**: `api.py` uses a custom HTTP server implementation, NOT Microdot framework

### Backend Structure (MicroPython)
```
Code/backend/
├── main.py              # Entry point: schedule check → feed → deep sleep (battery mode)
├── api.py               # Custom HTTP API server for web control (always-on mode)
├── config.py            # All hardware pins, WiFi, schedule config
├── services.py          # Schedule data operations
├── last_fed_service.py  # Last feed timestamp tracking
├── next_feed_service.py # Next scheduled feed calculation
├── quantity_service.py  # Feed quantity/remaining tracking
├── microdot.py          # Lightweight WSGI web framework (not used by api.py)
├── urequests.py         # HTTP client library (MicroPython)
├── data/                # JSON persistence layer (API mode only)
│   ├── schedule.json    # Feeding schedule with times/days
│   ├── last_fed.json    # Last feeding timestamp
│   ├── next_feed.json   # Calculated next feed time
│   └── quantity.json    # Remaining feed quantity
├── ota/                 # OTA (Over-The-Air) update system
│   ├── version.json     # Current installed firmware version
│   ├── ota_updater.py   # OTA update logic (downloads from GitHub)
│   └── README.md        # OTA documentation
├── UI/                  # Static files served by api.py
│   ├── index.html
│   ├── feednow.html
│   ├── setquantity.html
│   ├── setschedule.html
│   ├── troubleshooting.html  # Includes OTA update UI
│   ├── css/styles.css
│   └── assets/images/
└── lib/
    ├── stepper.py       # 28BYJ-48 motor control (half-step sequence)
    ├── rtc_handler.py   # DS3231 I2C RTC communication
    └── notification.py  # ntfy.sh push notifications via urequests
```

**Service Layer Pattern**:
- All data operations abstracted into service modules (`*_service.py`)
- Read/write JSON files for persistence in API server mode
- ISO 8601 timestamp format: `YYYY-MM-DDTHH:MM:SS`
- Schedule format: `{"feeding_times": [{"hour": 8, "minute": 0, "ampm": "AM", "enabled": true}], "days": {"Monday": true, ...}}`

**Power-critical patterns**:
- WiFi only enabled during notifications, immediately disconnected after
- Motor powered off via `motor.off()` after every feeding
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
- `POST /api/feed` → manual feeding trigger
- `POST /api/schedule` → create/update schedule
- `GET /api/schedules` → list all schedules
- `DELETE /api/schedule/{id}` → remove schedule
- `GET /api/status` → system health check

Backend (`api.py`) actual endpoints:
- `POST /api/feednow` → manual feeding (reduces quantity, updates last_fed)
- `POST /api/schedule` → save schedule (calculates next_feed)
- `GET /api/schedule` → read schedule
- `POST /api/quantity` → update quantity
- `GET /api/home` → combined status (connection, quantity, last_fed, battery, next_feed)
- `GET /api/ping` → health check

**Note**: There's an endpoint mismatch between frontend expectations and backend implementation. Frontend needs updating or backend needs `/api/schedules` (plural) endpoint.

## Hardware Configuration

### GPIO Pin Assignments (ESP8266)
**Stepper Motor (ULN2003 driver)**:
- IN1 → GPIO12 (D6), IN2 → GPIO13 (D7)
- IN3 → GPIO14 (D5), IN4 → GPIO15 (D8)

**DS3231 RTC (I2C)**:
- SDA → GPIO4 (D2), SCL → GPIO5 (D1)

**All pins configured in `config.py`** - modify there, not in driver files.

### Stepper Motor Specifics
- 28BYJ-48 with half-step sequence (8 steps/cycle)
- 4096 half-steps = 360° rotation
- `MOTOR_STEPS_PER_FEEDING = 512` in config (one full rotation)
- Delay between steps: `MOTOR_SPEED_MS = 2` (configurable for speed vs. power)

## Development Workflows

### IMPORTANT: Virtual Environment
**ALWAYS activate the virtual environment before running any commands:**
```bash
# Activate venv (Linux/Raspberry Pi)
source venv/bin/activate

# Or on Windows PowerShell
.\venv\Scripts\Activate.ps1
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
**After making changes, ALWAYS build/compile but DO NOT automatically upload to ESP8266/ESP32:**

```bash
# Activate venv first
source venv/bin/activate

# Build the distribution files
cd Code/backend
./build_backend.sh api   # For API mode
# OR
./build_backend.sh battery   # For battery mode

# This compiles and prepares files in dist/ folder
# DO NOT run upload commands automatically
```

**Manual Upload Instructions** (only when user explicitly requests deployment):
```bash
# Example upload commands (DO NOT RUN AUTOMATICALLY)
cd Code/backend/dist
ampy -p /dev/ttyUSB0 -b 115200 put api.py
# ... etc
```

### Deployment to ESP8266/ESP32
**CRITICAL**: After code changes:
1. ✅ Run build script to compile and prepare files
2. ❌ DO NOT automatically upload to device
3. ✅ Show user what files are ready in `dist/` folder
4. ✅ Wait for user to explicitly request upload/deployment

```bash
# User must explicitly run deployment
cd Code/backend
./deploy_to_esp8266.sh /dev/ttyUSB0  # Only when user asks
```

**Port detection**:
- Linux/Raspberry Pi: Check `/dev/ttyUSB*` or `/dev/ttyACM*`
- Windows: Use Device Manager → Ports to find COM port number

### Wokwi Simulation
Online circuit simulation at https://wokwi.com
- Circuit diagram: `Code/backend/wokwi/diagram.json`
- Upload all backend files to simulate hardware interactions without physical components

## Key Conventions

### Configuration Over Code
**Always modify `config.py` for**:
- Feeding schedule (`FEEDING_TIMES = [(8, 0), (20, 0)]` - 24hr format)
- WiFi credentials
- Motor parameters (steps, speed)
- GPIO pin assignments
- Deep sleep duration
- ntfy notification settings

### Feeding Logic (`main.py`)
1. Wake from deep sleep (RTC maintains time)
2. Initialize RTC, read current time
3. Compare against `FEEDING_TIMES` schedule
4. If match: execute `feed()` → send notification
5. Enter deep sleep for `DEEP_SLEEP_MINUTES`

**Timing tolerance**: Matches feeding time within 1 minute window

### Notification Pattern
Uses ntfy.sh for push notifications:
```python
notifier = NotificationService(config.NTFY_SERVER, config.NTFY_TOPIC)
notifier.send_feeding_notification(time_str)  # Success
notifier.send_error_notification(error_msg)   # Errors
```

Subscribe to notifications: `https://ntfy.sh/<NTFY_TOPIC>` on phone

## Common Tasks

### Adding New Feeding Time
Edit `config.py`:
```python
FEEDING_TIMES = [
    (8, 0),   # 8:00 AM
    (12, 0),  # 12:00 PM (NEW)
    (20, 0),  # 8:00 PM
]
```

### Adjusting Motor Rotation
Modify in `config.py`:
```python
MOTOR_STEPS_PER_FEEDING = 1024  # Double rotation
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
- `/api/feednow` - POST endpoint with body parsing
- `/api/quantity` - GET and POST methods
- `/api/home` - Combines multiple data sources
- `/api/ota/check` - OTA update check
- `/api/ota/update` - OTA download and apply

**To remove an endpoint**: Delete the entire `elif path == '/api/endpoint':` block.

### Frontend API Integration
Backend API endpoints expected at `/api/*`:
- `POST /api/feed` - Manual feeding trigger
- `POST /api/schedule` - Add feeding schedule
- `GET /api/schedules` - List all schedules
- `DELETE /api/schedule/{id}` - Remove schedule
- `GET /api/status` - System health check

## Running the API Server (Development Mode)

### Raspberry Pi / Linux
```bash
# ALWAYS activate venv first
source venv/bin/activate

cd /home/pi/Desktop/Feeder/Code/backend
python3 api.py
```

### Windows (PowerShell)
```powershell
# ALWAYS activate venv first
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
8. ESP8266/ESP32 deployment (only when user asks)

## Important Constraints

- **File size**: Keep code minimal - ESP8266 has limited flash/RAM
- **Import errors in IDE**: Expected - uses MicroPython libraries not available in standard Python
- **WiFi**: Only 2.4GHz networks supported by ESP8266
- **Deep sleep**: Device loses RAM state - RTC maintains time externally
- **Battery life**: Design decisions prioritize power efficiency over features

## OTA (Over-The-Air) Update System

### Overview
Memory-efficient firmware update system that downloads only changed files from GitHub.

### Architecture
- **Surge Deployment**: http://feeder-ota.surge.sh (mirrors `Code/backend/dist/` structure)
- **Local Version**: `ota/version.json` on ESP32
- **Remote Version**: `version.json` at Surge base URL
- **Update Logic**: `ota/ota_updater.py`

### How It Works
1. **Version Check**: ESP32 compares local `ota/version.json` with remote version from GitHub
2. **File Download**: If versions differ, downloads files listed in remote `version.json` one-by-one
3. **Atomic Update**: Each file downloaded to `.tmp`, then atomically renamed (rollback-safe)
4. **Memory Efficient**: Downloads 512-byte chunks, frequent `gc.collect()`, ~10-20KB RAM usage
5. **Reboot**: After successful update, device reboots to apply changes

### version.json Format
```json
{
  "version": "1.2.3",
  "date": "2025-12-01",
  "files": [
    "api.py",
    "services.py",
    "lib/stepper.py",
    "UI/index.html"
  ],
  "notes": "Bug fixes and new features"
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

### Deployment Workflow
1. Make changes to Feeder codebase
2. Build: `cd Code/backend && npm run build:api`
3. Copy `Code/backend/dist/*` to Surge deployment folder
4. Update `version.json` (bump version, list changed files)
5. Deploy to Surge: `surge . feeder-ota.surge.sh`
6. ESP32 checks for updates via web UI or automatically on boot

### Testing
Run test suite on Raspberry Pi before deploying:
```bash
source venv/bin/activate
python3 Tests/test_ota.py
```

### Safety Features
- Atomic file replacement (`.tmp` → rename)
- Failed downloads don't corrupt existing files
- `data/` directory excluded (preserves user settings)
- Version rollback: push older version.json to GitHub

### Files
- `Code/backend/ota/ota_updater.py` - OTA logic
- `Code/backend/ota/version.json` - Local version
- `Code/backend/ota/README.md` - Full OTA documentation
- `Tests/test_ota.py` - OTA test suite

## Documentation
- Full project details: `Instructions/instructions.md`
- Backend testing guide: `Code/backend/README.md`
- Frontend setup: `Code/frontend/README.md`
- Test suite info: `Tests/README.md`
- OTA system: `Code/backend/ota/README.md`
