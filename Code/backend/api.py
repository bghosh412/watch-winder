import gc
import socket
import utime as time

gc.collect()

# Track server start time for uptime calculation
SERVER_START_TIME = time.time()

# Manual JSON encoding (minimal)
def json_encode(obj):
    if obj is None:
        return 'null'
    elif isinstance(obj, bool):
        return 'true' if obj else 'false'
    elif isinstance(obj, (int, float)):
        return str(obj)
    elif isinstance(obj, str):
        escaped = obj.replace('\\', '\\\\').replace('"', '\\"').replace('\n', '\\n').replace('\r', '\\r').replace('\t', '\\t')
        return '"{}"'.format(escaped)
    elif isinstance(obj, dict):
        items = []
        for k, v in obj.items():
            items.append('"{}": {}'.format(k, json_encode(v)))
        return '{' + ', '.join(items) + '}'
    elif isinstance(obj, list):
        items = [json_encode(item) for item in obj]
        return '[' + ', '.join(items) + ']'
    return 'null'

def parse_simple_json(s):
    """Parse JSON string"""
    s = s.strip()
    if not s:
        return {}
    try:
        import ujson
        return ujson.loads(s)
    except:
        pass
    try:
        import json
        return json.loads(s)
    except:
        pass
    return {}

def calculate_next_winding(schedule):
    """Calculate next winding time based on schedule"""
    try:
        import utime as time
        now = time.localtime()
        current_day = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'][now[6]]
        current_hour_24 = now[3]
        current_minute = now[4]
        
        # Convert winding times to 24-hour format
        winding_times_24 = []
        for wt in schedule.get('winding_times', []):
            hour = wt['hour']
            if wt['ampm'] == 'PM' and hour != 12:
                hour += 12
            elif wt['ampm'] == 'AM' and hour == 12:
                hour = 0
            winding_times_24.append((hour, wt['minute']))
        
        # Find next winding time today
        for hour, minute in sorted(winding_times_24):
            if hour > current_hour_24 or (hour == current_hour_24 and minute > current_minute):
                if schedule.get('days', {}).get(current_day, False):
                    return '{:02d}:{:02d} Today'.format(hour, minute)
        
        # Find next active day
        days_order = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
        current_day_idx = days_order.index(current_day)
        for i in range(1, 8):
            next_day = days_order[(current_day_idx + i) % 7]
            if schedule.get('days', {}).get(next_day, False):
                if winding_times_24:
                    hour, minute = sorted(winding_times_24)[0]
                    return '{:02d}:{:02d} {}'.format(hour, minute, next_day)
        
        return 'Not scheduled'
    except Exception as e:
        print('Error calculating next winding:', e)
        return 'Not scheduled'

def send_response(conn, status, content_type, body):
    gc.collect()
    response = 'HTTP/1.1 {}\r\n'.format(status)
    response += 'Content-Type: {}\r\n'.format(content_type)
    response += 'Access-Control-Allow-Origin: *\r\n'
    response += 'Access-Control-Allow-Methods: GET, POST, DELETE, OPTIONS\r\n'
    response += 'Access-Control-Allow-Headers: Content-Type\r\n'
    response += 'Connection: close\r\n'
    response += 'Content-Length: {}\r\n'.format(len(body))
    response += '\r\n'
    conn.send(response.encode())
    conn.send(body.encode() if isinstance(body, str) else body)
    gc.collect()

def handle_request(conn, request):
    gc.collect()
    method = None
    path = None
    try:
        # Handle empty request
        if not request or len(request) == 0:
            print('Empty request received, ignoring')
            return
        lines = request.split(b'\r\n')
        if not lines:
            return
        request_line = lines[0].decode()
        parts = request_line.split()
        if len(parts) < 2:
            return
        method, path = parts[0], parts[1]
        # Extract path without query parameters
        if '?' in path:
            path = path.split('?')[0]
        print('Request: {} {}'.format(method, path))
        
        # Parse body if POST
        body_data = {}
        if method == 'POST':
            body_start = request.find(b'\r\n\r\n')
            if body_start != -1:
                body = request[body_start+4:].decode()
                if body:
                    body_data = parse_simple_json(body)
        
        # /api/home endpoint: serve status for frontend
        if path == '/api/home':
            try:
                # Read winds remaining
                try:
                    with open('data/quantitytxt', 'r') as f:
                        wind_remaining = f.read().strip()
                except:
                    wind_remaining = 'N/A'
                # Read last winding time
                try:
                    with open('data/last_windingtxt', 'r') as f:
                        last_winding = f.read().strip()
                except:
                    last_winding = ''
                # Read next winding time
                try:
                    with open('data/next_windingtxt', 'r') as f:
                        next_winding = f.read().strip()
                except:
                    next_winding = 'Not scheduled'
                # Read battery status (optional, fallback value)
                battery_status = '40% of the Battery remaining'
                result = json_encode({
                    'connectionStatus': 'Online',
                    'windRemaining': wind_remaining + ' more winds remaining' if wind_remaining != 'N/A' else 'N/A',
                    'lastWinding': last_winding,
                    'batteryStatus': battery_status,
                    'nextWinding': next_winding
                })
                send_response(conn, '200 OK', 'application/json', result)
                del result, wind_remaining, last_winding, next_winding, battery_status
                gc.collect()
                return
            except Exception as e:
                print('Error in /api/home:', e)
                send_response(conn, '500 Internal Server Error', 'application/json', json_encode({'error': str(e)}))
                gc.collect()
                return

        # /api/windnow endpoint: manual winding trigger
        elif path == '/api/windnow':
            if method == 'POST':
                try:
                    duration = body_data.get('duration', 30)
                    print(f"Manual winding triggered for {duration} minutes")
                    
                    # Wind the watch using motor service
                    import motor_service
                    success = motor_service.wind_watch(duration)
                    
                    if success:
                        # Update last winding time
                        now = time.localtime()
                        iso_time = "{:04d}-{:02d}-{:02d}T{:02d}:{:02d}:{:02d}".format(
                            now[0], now[1], now[2], now[3], now[4], now[5]
                        )
                        try:
                            with open('data/last_windingtxt', 'w') as f:
                                f.write(iso_time)
                        except:
                            pass
                        
                        result = json_encode({'status': 'ok', 'message': f'Winding completed for {duration} minutes', 'duration': duration})
                        send_response(conn, '200 OK', 'application/json', result)
                        del result
                        gc.collect()
                        return
                    else:
                        result = json_encode({'status': 'error', 'message': 'Failed to wind watch'})
                        send_response(conn, '500 Internal Server Error', 'application/json', result)
                        del result
                        gc.collect()
                        return
                except Exception as e:
                    print('Error in windnow:', e)
                    send_response(conn, '500 Internal Server Error', 'application/json', json_encode({'error': str(e)}))
                    gc.collect()
                    return
            else:
                send_response(conn, '405 Method Not Allowed', 'application/json', json_encode({'error': 'Only POST allowed'}))
                gc.collect()
                return

        # /api/schedule endpoint: read/write schedule
        elif path == '/api/schedule' or path == '/api/schedules':
            if method == 'GET':
                try:
                    with open('data/schedule.txt', 'r') as f:
                        schedule_data = parse_simple_json(f.read())
                    send_response(conn, '200 OK', 'application/json', json_encode(schedule_data))
                    del schedule_data
                    gc.collect()
                    return
                except Exception as e:
                    print('Error reading schedule:', e)
                    # Return default schedule
                    default = {
                        'winding_duration': 30,
                        'winding_times': [
                            {'hour': 8, 'minute': 0, 'ampm': 'AM'},
                            {'hour': 8, 'minute': 0, 'ampm': 'PM'}
                        ],
                        'days': {
                            'Monday': True, 'Tuesday': True, 'Wednesday': True,
                            'Thursday': True, 'Friday': True, 'Saturday': True, 'Sunday': True
                        }
                    }
                    send_response(conn, '200 OK', 'application/json', json_encode(default))
                    del default
                    gc.collect()
                    return
            elif method == 'POST':
                try:
                    # Save schedule
                    with open('data/schedule.txt', 'w') as f:
                        f.write(json_encode(body_data))
                    # Calculate next winding time
                    next_winding = calculate_next_winding(body_data)
                    with open('data/next_winding.txt', 'w') as f:
                        f.write(next_winding)
                    send_response(conn, '200 OK', 'application/json', json_encode({'status': 'ok'}))
                    gc.collect()
                    return
                except Exception as e:
                    print('Error saving schedule:', e)
                    send_response(conn, '500 Internal Server Error', 'application/json', json_encode({'error': str(e)}))
                    gc.collect()
                    return

        # /api/motor endpoint: read motor configuration
        elif path == '/api/motor':
            if method == 'GET':
                try:
                    with open('data/motor.txt', 'r') as f:
                        motor_data = parse_simple_json(f.read())
                    send_response(conn, '200 OK', 'application/json', json_encode(motor_data))
                    del motor_data
                    gc.collect()
                    return
                except Exception as e:
                    print('Error reading motor config:', e)
                    # Return default motor config
                    default = {'duty_cycle': 71, 'pulse_width': 180}
                    send_response(conn, '200 OK', 'application/json', json_encode(default))
                    del default
                    gc.collect()
                    return

        # Serve index.html for root or /index.html
        if path == '/' or path == '/index.html':
            try:
                with open('UI/index.html', 'rb') as f:
                    import os
                    file_size = os.stat('UI/index.html')[6]
                    response = 'HTTP/1.1 200 OK\r\n'
                    response += 'Content-Type: text/html\r\n'
                    response += 'Access-Control-Allow-Origin: *\r\n'
                    response += 'Connection: close\r\n'
                    response += 'Content-Length: {}\r\n'.format(file_size)
                    response += 'Cache-Control: no-cache, no-store, must-revalidate\r\n'
                    response += 'Pragma: no-cache\r\n'
                    response += 'Expires: 0\r\n'
                    response += '\r\n'
                    conn.send(response.encode())
                    while True:
                        chunk = f.read(512)
                        if not chunk:
                            break
                        conn.send(chunk)
                        gc.collect()
                return
            except Exception as e:
                print('Error serving index.html:', e)
                error_msg = 'Error: {}'.format(str(e))
                send_response(conn, '500 Internal Server Error', 'text/html', '<html><body><h1>Error</h1><p>{}</p></body></html>'.format(error_msg))
                return

        # Serve static files (css, js, images, etc.) from UI folder
        if not path.startswith('/api/'):
            file_path = 'UI' + path
            try:
                content_type = 'text/html'
                if path.endswith('.css'):
                    content_type = 'text/css'
                elif path.endswith('.js'):
                    content_type = 'application/javascript'
                elif path.endswith('.png'):
                    content_type = 'image/png'
                elif path.endswith('.jpg') or path.endswith('.jpeg'):
                    content_type = 'image/jpeg'
                elif path.endswith('.svg'):
                    content_type = 'image/svg+xml'
                elif path.endswith('.ico'):
                    content_type = 'image/x-icon'
                import os
                file_size = os.stat(file_path)[6]
                response = 'HTTP/1.1 200 OK\r\n'
                response += 'Content-Type: {}\r\n'.format(content_type)
                response += 'Access-Control-Allow-Origin: *\r\n'
                response += 'Connection: close\r\n'
                response += 'Content-Length: {}\r\n'.format(file_size)
                if content_type.startswith('image/'):
                    response += 'Cache-Control: public, max-age=604800\r\n'
                    response += 'Expires: Thu, 31 Dec 2026 23:59:59 GMT\r\n'
                else:
                    response += 'Cache-Control: no-cache, no-store, must-revalidate\r\n'
                    response += 'Pragma: no-cache\r\n'
                    response += 'Expires: 0\r\n'
                response += '\r\n'
                conn.send(response.encode())
                with open(file_path, 'rb') as f:
                    while True:
                        chunk = f.read(512)
                        if not chunk:
                            break
                        conn.send(chunk)
                        gc.collect()
                return
            except Exception as e:
                print('Error serving file {}: {}'.format(file_path, e))
                send_response(conn, '404 Not Found', 'text/plain', 'Not Found')
                return

        # Default handler: just return status OK for API
        send_response(conn, '200 OK', 'application/json', json_encode({'status': 'ok', 'message': 'Watch Winder API server is running'}))
        gc.collect()
    except Exception as e:
        print('Error handling request:', e)
        try:
            send_response(conn, '500 Internal Server Error', 'application/json', json_encode({'error': str(e)}))
        except:
            pass

class SimpleServer:
    def __init__(self):
        self.socket = None
        self.use_asyncio = False
    def run(self, host='0.0.0.0', port=5000):
        # Try to use asyncio if available
        try:
            import uasyncio as asyncio
            self.use_asyncio = True
            print('Using asyncio mode')
            asyncio.run(self._run_async(host, port))
        except ImportError:
            print('Asyncio not available, using blocking mode')
            self._run_blocking(host, port)
    async def _run_async(self, host, port):
        import uasyncio as asyncio
        actual_ip = self._get_ip(host)
        addr = socket.getaddrinfo(host, port)[0][-1]
        self.socket = socket.socket()
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.socket.bind(addr)
        self.socket.listen(5)
        self.socket.setblocking(False)
        print('Server running on {}:{}'.format(actual_ip, port))
        while True:
            try:
                conn, addr = await asyncio.wait_for(self._accept_connection(), timeout=1)
                print('Connection from', addr)
                asyncio.create_task(self._handle_connection(conn))
            except asyncio.TimeoutError:
                await asyncio.sleep(0)
            except Exception as e:
                print('Server error:', e)
                await asyncio.sleep(0.1)
                gc.collect()
    async def _accept_connection(self):
        import uasyncio as asyncio
        while True:
            try:
                return self.socket.accept()
            except OSError:
                await asyncio.sleep(0.1)
    async def _handle_connection(self, conn):
        try:
            conn.settimeout(5.0)
            request = b''
            while True:
                try:
                    chunk = conn.recv(1024)
                    if not chunk:
                        break
                    request += chunk
                    if b'\r\n\r\n' in request:
                        break
                except:
                    break
            if request:
                handle_request(conn, request)
            conn.close()
        except Exception as e:
            print('Connection error:', e)
            try:
                import sys
                sys.print_exception(e)
            except:
                import traceback
                traceback.print_exc()
        finally:
            try:
                conn.close()
            except:
                pass
            gc.collect()
    def _run_blocking(self, host, port):
        actual_ip = self._get_ip(host)
        addr = socket.getaddrinfo(host, port)[0][-1]
        self.socket = socket.socket()
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.socket.bind(addr)
        self.socket.listen(5)
        print('Server running on {}:{}'.format(actual_ip, port))
        while True:
            conn = None
            try:
                conn, addr = self.socket.accept()
                conn.settimeout(5.0)
                request = b''
                while True:
                    try:
                        chunk = conn.recv(1024)
                        if not chunk:
                            break
                        request += chunk
                        if b'\r\n\r\n' in request:
                            break
                    except:
                        break
                if request:
                    handle_request(conn, request)
                conn.close()
                gc.collect()
            except Exception as e:
                print('Server error:', e)
                if conn:
                    try:
                        conn.close()
                    except:
                        pass
                gc.collect()
    def _get_ip(self, host):
        if host == '0.0.0.0':
            try:
                import network
                sta = network.WLAN(network.STA_IF)
                if sta.isconnected():
                    return sta.ifconfig()[0]
            except:
                pass
        return host

app = SimpleServer()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
