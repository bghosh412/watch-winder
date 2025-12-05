# boot.py - MicroPython startup file for ESP8266
# Initiates WiFi connection using WifiManager

import gc
from wifi_manager import WifiManager

# Collect garbage at startup
gc.collect()

# Log system restart
try:
    import event_log_service
    event_log_service.log_event(event_log_service.EVENT_RESTART, 'System boot')
except:
    pass  # Don't fail boot if logging fails

# You can customize SSID and password below if needed

import os
SSID = 'WifiManager'
PASSWORD = 'wifimanager'
print('Starting WiFi connection...')
wifi = WifiManager()

# MicroPython-compatible file existence check
def file_exists(path):
    try:
        os.stat(path)
        return True
    except OSError:
        return False

# Use WifiManager's retry logic
wifi_dat_exists = file_exists('wifi.dat')
max_retries = 3 if wifi_dat_exists else 1
wifi.connect(retries=max_retries)

# Collect garbage after WiFi connection
gc.collect()

# Optionally, print IP address if connected
if wifi.is_connected():
    print('Connected to WiFi. IP:', wifi.get_address()[0])
    
    # Setup mDNS for easy access via hostname
    try:
        import config
        import network
        mdns_hostname = config.MDNS_HOSTNAME if hasattr(config, 'MDNS_HOSTNAME') else 'fishfeeder'
        mdns_service_name = config.MDNS_SERVICE_NAME if hasattr(config, 'MDNS_SERVICE_NAME') else 'Fish Feeder Device'
        
        # Try to use mDNS if available (ESP32)
        try:
            import mdns
            mdns_server = mdns.Server(0)
            mdns_server.start(mdns_hostname, mdns_service_name)
            # Add HTTP service advertisement
            mdns_server.add_service('_http', '_tcp', 5000, mdns_service_name)
            print('mDNS started: {}.local'.format(mdns_hostname))
            print('Access at: http://{}.local:5000'.format(mdns_hostname))
            # Also try to set the hostname via network interface
            sta_if = network.WLAN(network.STA_IF)
            sta_if.config(dhcp_hostname=mdns_hostname)
            print('Network hostname also set to: {}'.format(mdns_hostname))
        except ImportError:
            # mDNS not available on ESP8266, use network hostname
            sta_if = network.WLAN(network.STA_IF)
            try:
                sta_if.config(dhcp_hostname=mdns_hostname)
                print('Network hostname set: {}'.format(mdns_hostname))
                print('Try accessing: http://{}.local:5000'.format(mdns_hostname))
            except:
                print('Could not set hostname (older firmware)')
                print('Access via IP: http://{}:5000'.format(wifi.get_address()[0]))
    except Exception as e:
        print('mDNS setup failed:', e)
        print('Access via IP: http://{}:5000'.format(wifi.get_address()[0]))
    
    # Set timezone to India/Kolkata (UTC+5:30)
    try:
        import ntptime
        import machine
        import utime as time
        
        # Wait a moment for network to be fully ready
        time.sleep(2)
        
        print('Syncing time with NTP server...')
        
        # Try multiple NTP servers with timeout
        ntp_servers = ['pool.ntp.org', 'time.google.com', 'time.cloudflare.com']
        sync_success = False
        
        for ntp_server in ntp_servers:
            try:
                print('Trying NTP server: {}'.format(ntp_server))
                ntptime.host = ntp_server
                ntptime.timeout = 5  # 5 second timeout
                ntptime.settime()  # Sync with NTP server (gets UTC time)
                sync_success = True
                print('Successfully synced with {}'.format(ntp_server))
                break
            except Exception as e:
                print('Failed to sync with {}: {}'.format(ntp_server, e))
                if ntp_server == ntp_servers[-1]:
                    # Last server also failed
                    raise Exception('All NTP servers failed')
                # Try next server
                continue
        
        if sync_success:
            # India/Kolkata is UTC+5:30 (19800 seconds offset)
            # ESP32/ESP8266 stores time in UTC, so we need to add the offset
            IST_OFFSET = 19800  # 5 hours 30 minutes in seconds
            
            # Get current UTC time
            current_time = time.time()
            
            # Add IST offset
            ist_time = current_time + IST_OFFSET
            
            # Convert to struct_time
            tm = time.localtime(ist_time)
            
            # Set RTC with IST time
            rtc = machine.RTC()
            rtc.datetime((tm[0], tm[1], tm[2], tm[6], tm[3], tm[4], tm[5], 0))
            
            print('Time synced to India/Kolkata timezone')
            print('Current time:', time.localtime())
        
    except Exception as e:
        print('Failed to sync time:', e)
        print('Continuing without time sync...')
        print('Note: Scheduled feeding may not work correctly without time sync')
else:
    print('WiFi not connected. Configuration portal may be active.')

# Final garbage collection before main.py loads
gc.collect()
