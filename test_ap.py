"""
Simple AP test for ESP32-C3 - Tests if AP is visible
"""
import network
import time
import gc
import machine

# XIAO ESP32C3: Try to enable PCB antenna using machine module
print('Configuring XIAO ESP32C3 antenna...')
try:
    # Some ESP32-C3 boards need GPIO3 configured for antenna switching
    # XIAO ESP32C3: GPIO3 controls antenna (0V = PCB antenna, 3.3V = external)
    antenna_pin = machine.Pin(3, machine.Pin.OUT)
    antenna_pin.value(0)  # 0 = Use PCB antenna
    print('PCB antenna enabled via GPIO3')
except Exception as e:
    print('Antenna config:', e)

time.sleep(0.5)

# Free memory before WiFi operations
gc.collect()

# CRITICAL: Disable STA mode FIRST before enabling AP
print('Disabling station mode...')
sta = network.WLAN(network.STA_IF)
sta.active(False)
time.sleep(1)

# Deactivate AP first to ensure clean state
print('Resetting AP...')
ap = network.WLAN(network.AP_IF)
ap.active(False)
time.sleep(1)

# Now activate AP
print('Activating AP...')
ap.active(True)
time.sleep(1)

# Configure with open network (no password) for testing
print('Configuring AP: ESP32_C3_TEST (open network)...')
ap.config(essid='ESP32_C3_TEST')
time.sleep(0.5)

# Set to open network
ap.config(authmode=0)  # 0 = open, no password
time.sleep(0.5)

# Try setting max TX power for better visibility
try:
    ap.config(txpower=20)
    print('TX power set to maximum (20dBm)')
except Exception as e:
    print('Could not set TX power:', e)

# Wait for AP to fully initialize
time.sleep(2)

print('\n=== AP Status ===')
print('AP Active:', ap.active())
ap_ip = ap.ifconfig()[0]
print('AP IP:', ap_ip)
print('AP Config:', ap.ifconfig())
try:
    print('AP SSID:', ap.config('essid'))
    print('AP Channel:', ap.config('channel'))
except:
    pass

print('\n=== Starting Web Server ===')
print('Connect to ESP32_C3_TEST and visit:', ap_ip)

# Simple web server
import socket

html = """HTTP/1.1 200 OK
Content-Type: text/html

<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ESP32-C3 Test Portal</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            max-width: 600px;
            margin: 50px auto;
            padding: 20px;
            background: #f0f0f0;
        }
        .container {
            background: white;
            padding: 30px;
            border-radius: 10px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }
        h1 { color: #333; }
        .success { color: #28a745; font-weight: bold; }
        .info { background: #e7f3ff; padding: 15px; border-radius: 5px; margin: 20px 0; }
    </style>
</head>
<body>
    <div class="container">
        <h1>🎉 ESP32-C3 Portal Working!</h1>
        <p class="success">✓ WiFi AP is active</p>
        <p class="success">✓ Web server is running</p>
        <p class="success">✓ PCB antenna is enabled</p>
        <div class="info">
            <h3>Connection Info:</h3>
            <p><strong>SSID:</strong> ESP32_C3_TEST</p>
            <p><strong>IP:</strong> """ + ap_ip + """</p>
            <p><strong>Status:</strong> Connected and working!</p>
        </div>
        <p>Your XIAO ESP32C3 is configured correctly and ready to use.</p>
    </div>
</body>
</html>
"""

server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
server.bind(('', 80))
server.listen(5)

print('Web server listening on port 80...')

while True:
    try:
        conn, addr = server.accept()
        print('Connection from:', addr)
        request = conn.recv(1024)
        conn.send(html)
        conn.close()
        print('Response sent')
    except Exception as e:
        print('Error:', e)
        try:
            conn.close()
        except:
            pass
    gc.collect()
