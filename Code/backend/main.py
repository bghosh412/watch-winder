import gc
import utime as time
import uasyncio as asyncio
import network

# Collect garbage before starting
gc.collect()

print('Starting Watch Winder System...')
print('Free memory:', gc.mem_free())

# CRITICAL: Wait for WiFi connection before starting services
print('Checking WiFi connection status...')
wlan_sta = network.WLAN(network.STA_IF)
wlan_ap = network.WLAN(network.AP_IF)
time.sleep(5)  # Allow time for interfaces to initialize
# Wait up to 60 seconds for WiFi connection or AP configuration
max_wait = 60
wait_count = 0

while wait_count < max_wait:
    if wlan_sta.isconnected():
        print('WiFi connected as client:', wlan_sta.ifconfig()[0])
        break
    elif wlan_ap.active():
        print('AP mode active - waiting for WiFi configuration...')
        print('Please connect to AP and configure WiFi before continuing')
        time.sleep(5)
        wait_count += 5
        # Keep waiting in AP mode until user configures WiFi
        continue
    else:
        print('Waiting for WiFi connection... ({}/{})'.format(wait_count, max_wait))
        time.sleep(2)
        wait_count += 2

# If still in AP mode or not connected, don't start services
if wlan_ap.active() and not wlan_sta.isconnected():
    print('\n=== WiFi Configuration Required ===')
    print('System is in AP mode. Please configure WiFi before services can start.')
    print('Connect to the AP and configure WiFi credentials.')
    print('Device will not start scheduler/API until WiFi is configured.')
    while True:
        time.sleep(10)
        if wlan_sta.isconnected():
            print('WiFi connected! Restarting to start services...')
            import machine
            machine.reset()

# Only proceed if connected to WiFi
if not wlan_sta.isconnected():
    print('ERROR: No WiFi connection. Cannot start services.')
    print('Please configure WiFi and reset the device.')
    while True:
        time.sleep(10)

print('\n=== WiFi Connected - Starting Services ===')
print('IP Address:', wlan_sta.ifconfig()[0])

try:
    # Import scheduler service first
    import scheduler_service
    print('Scheduler service imported')
    gc.collect()
    
    # Start the winding scheduler (this creates an asyncio task)
    #scheduler_service.start_scheduler()
    print('Winding scheduler started')
    gc.collect()
    
    # Import and start API server
    import api
    print('API module imported successfully')
    gc.collect()
    print('Free memory after import:', gc.mem_free())
    
    # Start the server (this will run the asyncio event loop)
    api.app.run(host='0.0.0.0', port=80)
    
except ImportError as e:
    print('Import error:', e)
    print('Make sure all required files are uploaded to the ESP32')
    import sys
    sys.print_exception(e)
except MemoryError as e:
    print('Memory error:', e)
    print('ESP32 ran out of memory. Try reducing features.')
    import sys
    sys.print_exception(e)
except Exception as e:
    print('Error starting system:', e)
    import sys
    sys.print_exception(e)
