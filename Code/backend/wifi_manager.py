# Author: Igor Ferreira
# License: MIT
# Version: 2.1.0
# Description: WiFi Manager for ESP8266 and ESP32 using MicroPython.

import machine
import network
import socket
import re
import utime as time


class WifiManager:

    def __init__(self, ssid = 'WifiManager', password = 'wifimanager', reboot = True, debug = False):
        self.wlan_sta = network.WLAN(network.STA_IF)
        self.wlan_sta.active(True)
        self.wlan_ap = network.WLAN(network.AP_IF)
        
        # Avoids simple mistakes with wifi ssid and password lengths, but doesn't check for forbidden or unsupported characters.
        if len(ssid) > 32:
            raise Exception('The SSID cannot be longer than 32 characters.')
        else:
            self.ap_ssid = ssid
        if len(password) < 8:
            raise Exception('The password cannot be less than 8 characters long.')
        else:
            self.ap_password = password
            
        # Set the access point authentication mode to WPA2-PSK.
        self.ap_authmode = 3
        
        # The file were the credentials will be stored.
        # There is no encryption, it's just a plain text archive. Be aware of this security problem!
        self.wifi_credentials = 'wifi.dat'
        
        # Prevents the device from automatically trying to connect to the last saved network without first going through the steps defined in the code.
        self.wlan_sta.disconnect()
        
        # Change to True if you want the device to reboot after configuration.
        # Useful if you're having problems with web server applications after WiFi configuration.
        self.reboot = reboot
        
        self.debug = debug


    def connect(self, retries=1):
        import gc
        import machine
        
        # XIAO ESP32C3: Enable PCB antenna via GPIO3
        try:
            antenna_pin = machine.Pin(3, machine.Pin.OUT)
            antenna_pin.value(0)  # 0 = Use PCB antenna
        except:
            pass
        
        if self.wlan_sta.isconnected():
            return
        
        # Free memory before WiFi operations
        gc.collect()
        
        profiles = self.read_credentials()
        attempt = 0
        while attempt < retries:
            for ssid, *_ in self.wlan_sta.scan():
                ssid = ssid.decode("utf-8")
                if ssid in profiles:
                    password = profiles[ssid]
                    if self.wifi_connect(ssid, password):
                        return
            attempt += 1
            if not self.wlan_sta.isconnected() and attempt < retries:
                print('WiFi connection failed. Retrying ({}/{})...'.format(attempt, retries))
        if not self.wlan_sta.isconnected():
            print('Could not connect to any WiFi network after {} attempt(s). Starting the configuration portal...'.format(retries))
            self.web_server()
        
    
    def disconnect(self):
        if self.wlan_sta.isconnected():
            self.wlan_sta.disconnect()


    def is_connected(self):
        return self.wlan_sta.isconnected()


    def get_address(self):
        return self.wlan_sta.ifconfig()


    def write_credentials(self, profiles):
        lines = []
        for ssid, password in profiles.items():
            lines.append('{0};{1}\n'.format(ssid, password))
        with open(self.wifi_credentials, 'w') as file:
            file.write(''.join(lines))


    def read_credentials(self):
        lines = []
        try:
            with open(self.wifi_credentials) as file:
                lines = file.readlines()
        except Exception as error:
            if self.debug:
                print(error)
            pass
        profiles = {}
        for line in lines:
            ssid, password = line.strip().split(';')
            profiles[ssid] = password
        return profiles


    def wifi_connect(self, ssid, password):
        import gc
        import machine
        
        # XIAO ESP32C3: Enable PCB antenna via GPIO3
        try:
            antenna_pin = machine.Pin(3, machine.Pin.OUT)
            antenna_pin.value(0)  # 0 = Use PCB antenna
        except:
            pass
        
        # Free memory before connection attempt
        gc.collect()
        
        # Disconnect any existing connection first
        if self.wlan_sta.isconnected():
            print('Disconnecting from existing network...')
            self.wlan_sta.disconnect()
            time.sleep(1)
        
        # Ensure STA is active
        if not self.wlan_sta.active():
            print('Activating STA interface...')
            self.wlan_sta.active(True)
            time.sleep(1)
        
        print('Connecting to SSID:', ssid)
        print('Using password of length:', len(password))
        
        try:
            self.wlan_sta.connect(ssid, password)
        except Exception as e:
            print('Connection initiation error:', e)
            return False
        
        # Wait up to 20 seconds for connection
        for i in range(200):
            if self.wlan_sta.isconnected():
                print('\nConnected successfully!')
                print('IP address:', self.wlan_sta.ifconfig()[0])
                print('Network info:', self.wlan_sta.ifconfig())
                
                # Clean up after successful connection
                gc.collect()
                
                return True
            else:
                # Check status for better error reporting
                status = self.wlan_sta.status()
                if i % 10 == 0:
                    print('Connection status:', status)
                
                # Status codes:
                # 1001 = connecting
                # 201 = no AP found
                # 202 = wrong password
                # 203 = timeout
                if status == 202:
                    print('\nConnection failed: Wrong password!')
                    break
                elif status == 201:
                    print('\nConnection failed: Network not found!')
                    break
                elif status == 203:
                    print('\nConnection failed: Timeout!')
                    break
                
                print('.', end='')
                time.sleep_ms(100)
        
        print('\nConnection failed after timeout')
        print('Final status:', self.wlan_sta.status())
        self.wlan_sta.disconnect()
        return False

    
    def web_server(self):
        import gc
        import machine
        
        # Free memory before starting web server
        gc.collect()
        
        # XIAO ESP32C3: Enable PCB antenna via GPIO3
        print('Starting AP mode on ESP32-C3...')
        try:
            print('Configuring XIAO ESP32C3 antenna...')
            antenna_pin = machine.Pin(3, machine.Pin.OUT)
            antenna_pin.value(0)  # 0 = Use PCB antenna
            print('PCB antenna enabled via GPIO3')
        except Exception as e:
            print('Antenna config:', e)
        
        time.sleep_ms(500)
        
        # CRITICAL for ESP32-C3: Must disable station mode first
        print('Disabling station mode...')
        self.wlan_sta.active(False)
        time.sleep_ms(200)
        
        # Deactivate AP first to ensure clean state
        print('Deactivating AP...')
        self.wlan_ap.active(False)
        time.sleep_ms(200)
        
        
        # Activate AP with ESP32-C3 compatible settings
        print('Activating AP...')
        self.wlan_ap.active(True)
        time.sleep(1)
        
        # ESP32-C3: Configure with minimal settings first
        print('Configuring AP with SSID:', self.ap_ssid)
        try:
            # Set transmit power to maximum (helps visibility)
            self.wlan_ap.config(txpower=20)
        except:
            pass  # Some firmware versions don't support txpower
        
        # Configure essid first, then other params
        self.wlan_ap.config(essid=self.ap_ssid)
        time.sleep_ms(500)
        self.wlan_ap.config(password=self.ap_password)
        time.sleep_ms(500)
        self.wlan_ap.config(authmode=self.ap_authmode)
        time.sleep_ms(500)
        
        # Try configuring channel separately
        try:
            self.wlan_ap.config(channel=6)
            print('Channel set to 6')
        except Exception as e:
            print('Could not set channel:', e)
        
        time.sleep(2)  # Give AP time to fully initialize and broadcast
        
        # Verify AP is active
        if self.wlan_ap.active():
            print('AP is ACTIVE')
            print('AP config:', self.wlan_ap.ifconfig())
            print('AP status:', self.wlan_ap.status())
            cfg = self.wlan_ap.config('essid')
            print('Broadcasting SSID:', cfg)
        else:
            print('ERROR: AP failed to activate!')
            return
        
        server_socket = socket.socket()
        server_socket.close()
        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server_socket.bind(('', 80))
        server_socket.listen(1)
        print('Connect to', self.ap_ssid, 'with the password', self.ap_password, 'and access the captive portal at', self.wlan_ap.ifconfig()[0])
        
        while True:
            # Free memory at start of each request loop
            gc.collect()
            if self.wlan_sta.isconnected():
                self.wlan_ap.active(False)
                if self.reboot:
                    print('The device will reboot in 5 seconds.')
                    time.sleep(5)
                    machine.reset()
            self.client, addr = server_socket.accept()
            try:
                self.client.settimeout(5.0)
                self.request = b''
                try:
                    while True:
                        if '\r\n\r\n' in self.request:
                            # Fix for Safari browser
                            self.request += self.client.recv(512)
                            break
                        self.request += self.client.recv(128)
                except Exception as error:
                    # It's normal to receive timeout errors in this stage, we can safely ignore them.
                    if self.debug:
                        print(error)
                    pass
                if self.request:
                    if self.debug:
                        print(self.url_decode(self.request))
                    url = re.search('(?:GET|POST) /(.*?)(?:\\?.*?)? HTTP', self.request).group(1).decode('utf-8').rstrip('/')
                    if url == '':
                        self.handle_root()
                    elif url == 'configure':
                        self.handle_configure()
                    else:
                        self.handle_not_found()
            except Exception as error:
                if self.debug:
                    print(error)
                return
            finally:
                self.client.close()


    def send_header(self, status_code = 200):
        self.client.send("""HTTP/1.1 {0} OK\r\n""".format(status_code))
        self.client.send("""Content-Type: text/html\r\n""")
        self.client.send("""Connection: close\r\n\r\n""")


    def send_response(self, payload, status_code = 200):
        self.send_header(status_code)
        self.client.sendall("""
            <!DOCTYPE html>
            <html lang="en">
                <head>
                    <title>WiFi Manager</title>
                    <meta charset="UTF-8">
                    <meta name="viewport" content="width=device-width, initial-scale=1">
                    <link rel="icon" href="data:,">
                </head>
                <body>
                    {0}
                </body>
            </html>
        """.format(payload))
        self.client.close()


    def handle_root(self):
        # Build the complete HTML first, then send it all at once
        html_parts = []
        html_parts.append("""<!DOCTYPE html>
<html lang="en">
<head>
    <title>WiFi Manager</title>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <link rel="icon" href="data:,">
    <style>
        body { font-family: Arial, sans-serif; max-width: 600px; margin: 20px auto; padding: 20px; }
        h1 { color: #333; }
        .network { padding: 10px; margin: 5px 0; background: #f0f0f0; border-radius: 5px; }
        input[type="password"] { padding: 8px; width: 200px; }
        input[type="submit"] { padding: 10px 20px; background: #007bff; color: white; border: none; border-radius: 5px; cursor: pointer; }
    </style>
</head>
<body>
    <h1>WiFi Manager</h1>
    <p>Select a network to connect:</p>
    <form action="/configure" method="post" accept-charset="utf-8">
""")
        
        # Ensure STA is active for scanning
        if not self.wlan_sta.active():
            print('Activating STA for WiFi scan...')
            self.wlan_sta.active(True)
            time.sleep(2)
        
        # Perform WiFi scan
        print('Scanning for WiFi networks...')
        network_count = 0
        
        try:
            networks = self.wlan_sta.scan()
            print('Raw scan returned {} results'.format(len(networks) if networks else 0))
            
            if networks:
                seen_ssids = set()
                for net in networks:
                    try:
                        ssid = net[0].decode("utf-8") if isinstance(net[0], bytes) else str(net[0])
                        
                        if ssid and ssid.strip() and ssid not in seen_ssids:
                            seen_ssids.add(ssid)
                            network_count += 1
                            print('Adding network: {}'.format(ssid))
                            html_parts.append(
                                '<div class="network">'
                                '<input type="radio" name="ssid" value="{}" id="net{}">'
                                '<label for="net{}">&nbsp;{}</label>'
                                '</div>\n'.format(ssid, network_count, network_count, ssid)
                            )
                    except Exception as e:
                        print('Error processing network:', e)
                        continue
                
                print('Total unique networks: {}'.format(network_count))
        except Exception as e:
            print('Scan error:', e)
            import sys
            sys.print_exception(e)
        
        if network_count == 0:
            html_parts.append('<p style="color: red;">No WiFi networks found. Please refresh to try again.</p>\n')
        
        html_parts.append("""
        <p><label for="password">Password:&nbsp;</label><input type="password" id="password" name="password"></p>
        <p><input type="submit" value="Connect"></p>
    </form>
</body>
</html>
""")
        
        # Send complete HTML at once
        complete_html = ''.join(html_parts)
        self.send_header()
        self.client.sendall(complete_html)
        self.client.close()


    def handle_configure(self):
        # Decode the request first
        decoded_request = self.url_decode(self.request)
        print('Decoded request:', decoded_request)
        
        # Extract the POST body (after \r\n\r\n)
        body_start = decoded_request.find(b'\r\n\r\n')
        if body_start != -1:
            post_body = decoded_request[body_start + 4:]
            print('POST body:', post_body)
        else:
            post_body = decoded_request
        
        # Match SSID and password from form data
        match = re.search(b'ssid=([^&]*)&password=([^&\r\n]*)', post_body)
        if match:
            ssid = match.group(1).decode('utf-8')
            password = match.group(2).decode('utf-8')
            
            print('Attempting connection to SSID:', ssid)
            print('Password (for debug):', password)
            print('Password length:', len(password))
            
            if len(ssid) == 0:
                self.send_response("""
                    <p style="color: red;">SSID must be provided!</p>
                    <p><a href="/">Go back and try again</a></p>
                """, 400)
            elif self.wifi_connect(ssid, password):
                self.send_response("""
                    <h2 style="color: green;">Successfully connected!</h2>
                    <p><strong>Network:</strong> {0}</p>
                    <p><strong>IP address:</strong> {1}</p>
                    <p>The device will now restart and connect automatically.</p>
                """.format(ssid, self.wlan_sta.ifconfig()[0]))
                profiles = self.read_credentials()
                profiles[ssid] = password
                self.write_credentials(profiles)
                print('Credentials saved. Rebooting...')
                time.sleep(3)
            else:
                self.send_response("""
                    <h2 style="color: red;">Connection Failed</h2>
                    <p>Could not connect to: <strong>{0}</strong></p>
                    <p>Please check:</p>
                    <ul>
                        <li>Password is correct</li>
                        <li>Network is within range</li>
                        <li>Network is operational</li>
                    </ul>
                    <p><a href="/">Go back and try again</a></p>
                """.format(ssid))
                time.sleep(2)
        else:
            print('Could not parse form data')
            print('Raw request:', self.request)
            self.send_response("""
                <p style="color: red;">Could not parse form data!</p>
                <p>Please try again.</p>
                <p><a href="/">Go back</a></p>
            """, 400)
            time.sleep(2)


    def handle_not_found(self):
        self.send_response("""
            <p>Page not found!</p>
        """, 404)


    def url_decode(self, url_string):

        # Source: https://forum.micropython.org/viewtopic.php?t=3076
        # unquote('abc%20def') -> b'abc def'
        # Note: strings are encoded as UTF-8. This is only an issue if it contains
        # unescaped non-ASCII characters, which URIs should not.

        if not url_string:
            return b''

        if isinstance(url_string, str):
            url_string = url_string.encode('utf-8')

        bits = url_string.split(b'%')

        if len(bits) == 1:
            return url_string

        res = [bits[0]]
        appnd = res.append
        hextobyte_cache = {}

        for item in bits[1:]:
            try:
                code = item[:2]
                char = hextobyte_cache.get(code)
                if char is None:
                    char = hextobyte_cache[code] = bytes([int(code, 16)])
                appnd(char)
                appnd(item[2:])
            except Exception as error:
                if self.debug:
                    print(error)
                appnd(b'%')
                appnd(item)

        return b''.join(res)
