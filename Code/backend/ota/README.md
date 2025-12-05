# OTA (Over-The-Air) Update System

This module provides automatic firmware updates for the ESP32 fish feeder from GitHub.

## How It Works

1. **Version Check**: ESP32 compares local `version.json` with remote version from GitHub
2. **File Download**: If versions differ, downloads only the changed files listed in `files[]` array
3. **Atomic Update**: Files downloaded to `.tmp`, then atomically renamed (rollback-safe)
4. **Reboot Required**: After successful update, device must reboot to apply changes

## Files

- `version.json` - Current installed version on ESP32
- `ota_updater.py` - OTA update logic

## Usage

### Manual OTA Check (ESP32 REPL)

```python
from ota.ota_updater import check_and_update
check_and_update()
```

### Add to API Server (api.py)

```python
@app.route('/api/ota/check', methods=['GET'])
def ota_check(request):
    from ota.ota_updater import OTAUpdater
    updater = OTAUpdater()
    remote_data = updater.check_for_updates()
    if remote_data:
        return {'update_available': True, 'version': remote_data['version']}
    return {'update_available': False}

@app.route('/api/ota/update', methods=['POST'])
def ota_update(request):
    from ota.ota_updater import check_and_update
    success = check_and_update()
    return {'success': success}
```

### Automatic Update on Boot (main.py or api.py)

```python
# Check for updates on startup (optional)
try:
    from ota.ota_updater import check_and_update
    check_and_update()
except Exception as e:
    print(f"OTA check failed: {e}")
```

## Surge Deployment Structure

Base URL: `http://feeder-ota.surge.sh`

**Note**: Site structure mirrors `Code/backend/dist/` folder (deployed structure on ESP32)

```
http://feeder-ota.surge.sh/
├── version.json          # Master version file
├── api.py
├── config.py
├── services.py
├── ota/
│   ├── version.json
│   └── ota_updater.py
├── lib/
│   └── stepper.py
└── UI/
    └── index.html
```

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

## Memory Usage

- Minimal RAM footprint (~10-20KB during update)
- Downloads one file at a time
- Streaming writes to filesystem
- Frequent garbage collection

## Safety Features

- Atomic file replacement (`.tmp` → rename)
- Failed downloads don't corrupt existing files
- `data/` directory excluded (preserves user settings)
- Version rollback: push older version.json to GitHub

## Testing

Run test suite on Raspberry Pi before deploying:

```bash
cd /home/pi/Desktop/Feeder
python3 Tests/test_ota.py
```

## Deployment Workflow

1. Make changes to Feeder codebase
2. Build: `cd Code/backend && npm run build:api`
3. Copy `Code/backend/dist/*` to Surge deployment folder
4. Update `version.json` (bump version, list changed files)
5. Deploy to Surge: `surge . feeder-ota.surge.sh`
6. ESP32 checks for updates via web UI or automatically on boot
