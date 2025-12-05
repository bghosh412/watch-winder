import gc
import socket
import utime as time

gc.collect()

# Track server start time for uptime calculation
SERVER_START_TIME = time.time()

# Manual JSON encoding
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
    """Improved JSON parser for nested structures"""
    s = s.strip()
    if not s:
        return {}
    
    # Try to use ujson if available (MicroPython)
    try:
        import ujson
        return ujson.loads(s)
    except:
        pass
    
    # Try standard json (Python)
    try:
        import json
        return json.loads(s)
    except:
        pass
    
    # Fallback: basic parser for simple key:value pairs only
    if s.startswith('{') and s.endswith('}'):
        result = {}
        content = s[1:-1].strip()
        if content:
            pairs = content.split(',')
            for pair in pairs:
                if ':' in pair:
                    k, v = pair.split(':', 1)
                    k = k.strip().strip('"')
                    v = v.strip().strip('"')
                    try:
                        v = int(v)
                    except:
                        pass
                    result[k] = v
        return result
    return {}

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
                    print('Raw body:', body)
                    body_data = parse_simple_json(body)
                    print('Parsed body_data:', body_data)
                    print('Type of body_data:', type(body_data))
        
        # OPTIONS handling
        if method == 'OPTIONS':
            send_response(conn, '200 OK', 'text/plain', '')
            return
        
        # Route handling
        # Support both /api/feed and /api/feednow for compatibility
        if path == '/api/feednow' or path == '/api/feed':
            import utime as time
            import lib.notification
            import calibration_service
            import event_log_service
            import quantity_service
            import last_fed_service

            # Log manual feed event
            event_log_service.log_event(event_log_service.EVENT_FEED_MANUAL, 'Manual feed via web interface')

            # Disburse food using calibrated servo settings
            food_dispensed = calibration_service.disburseFood()

            if food_dispensed:
                # Update quantity and last fed timestamp
                quantity = quantity_service.read_quantity()
                if quantity > 0:
                    quantity -= 1
                quantity_service.write_quantity(quantity)
                last_fed_service.write_last_fed_now()

                # Free memory before sending notification
                gc.collect()

                # Send notification
                now = time.localtime()
                msg = "Food disbursed at {:02d}:{:02d}:{:02d}. Feed remaining: {}".format(now[3], now[4], now[5], quantity)
                lib.notification.send_ntfy_notification(msg)

                result = json_encode({'status': 'ok', 'quantity': quantity})
                send_response(conn, '200 OK', 'application/json', result)
                # Memory optimization: delete large objects and collect
                del result, msg, now, quantity, food_dispensed
                gc.collect()
            else:
                # Food dispensing failed
                result = json_encode({'status': 'error', 'message': 'Failed to dispense food'})
                send_response(conn, '500 Internal Server Error', 'application/json', result)
                del result, food_dispensed
                gc.collect()
            
        elif path == '/api/quantity':
            if method == 'GET':
                import quantity_service
                quantity = quantity_service.read_quantity()
                result = json_encode({'quantity': quantity})
                send_response(conn, '200 OK', 'application/json', result)
                del result, quantity
                gc.collect()
            else:
                import lib.notification
                import event_log_service
                import quantity_service
                value = body_data.get('quantity')
                if value is not None:
                    quantity_service.write_quantity(value)
                    # Log quantity update
                    event_log_service.log_event(event_log_service.EVENT_QUANTITY_UPDATE, 'Updated to {}'.format(value))
                    gc.collect()
                    msg = "Remaining food quantity updated to {}".format(value)
                    lib.notification.send_ntfy_notification(msg)
                    result = json_encode({'status': 'ok'})
                    send_response(conn, '200 OK', 'application/json', result)
                    del result, msg, value
                    gc.collect()
                else:
                    send_response(conn, '400 Bad Request', 'application/json', json_encode({'error': 'Missing quantity'}))
                    gc.collect()
                    
        elif path == '/api/home':
            import quantity_service
            import last_fed_service
            import next_feed_service
            quantity = quantity_service.read_quantity()
            last_fed = last_fed_service.read_last_fed()
            next_feed = next_feed_service.read_next_feed()
            result = json_encode({
                'connectionStatus': 'Online',
                'feedRemaining': '{} more feed remaining'.format(quantity),
                'lastFed': last_fed,
                'batteryStatus': '40% of the Battery remaining',
                'nextFeed': next_feed
            })
            send_response(conn, '200 OK', 'application/json', result)
            del result, quantity, last_fed, next_feed
            gc.collect()
            
        elif path == '/api/ping' or path == '/api/status':
            send_response(conn, '200 OK', 'application/json', json_encode({'status': 'ok', 'message': 'Server is running'}))
            gc.collect()
            
        elif path == '/api/schedule' or path == '/api/schedules' or path.startswith('/api/schedule/'):
            import services
            if method == 'GET':
                data = services.read_schedule()
                result = json_encode(data) if data else json_encode({'error': 'Could not read schedule'})
                send_response(conn, '200 OK', 'application/json', result)
                del result, data
                gc.collect()
            elif method == 'DELETE':
                # For now, just return success - implement delete logic as needed
                send_response(conn, '200 OK', 'application/json', json_encode({'status': 'ok', 'message': 'Schedule deleted'}))
                gc.collect()
            else:
                # write_schedule already calculates and saves next feed time
                import event_log_service
                print('Received schedule data:', body_data)
                result = services.write_schedule(body_data)
                if result:
                    # Log schedule change
                    event_log_service.log_event(event_log_service.EVENT_CONFIG_CHANGE, 'Schedule updated')
                    send_response(conn, '200 OK', 'application/json', json_encode({'status': 'ok'}))
                    gc.collect()
                else:
                    print('Failed to write schedule')
                    send_response(conn, '500 Internal Server Error', 'application/json', json_encode({'error': 'Failed to save schedule'}))
                    gc.collect()
        
        elif path == '/api/calibration/get':
            if method == 'GET':
                try:
                    import calibration_service
                    data = calibration_service.get_current_calibration()
                    send_response(conn, '200 OK', 'application/json', json_encode(data))
                    del data
                    gc.collect()
                except Exception as e:
                    print('Error reading calibration:', e)
                    send_response(conn, '500 Internal Server Error', 'application/json', json_encode({'error': str(e)}))
                    gc.collect()
            else:
                send_response(conn, '405 Method Not Allowed', 'application/json', json_encode({'error': 'Only GET allowed'}))
                gc.collect()
        
        elif path == '/api/events':
            if method == 'GET':
                try:
                    import event_log_service
                    limit = 100  # Default to all events
                    events = event_log_service.read_events(limit)
                    send_response(conn, '200 OK', 'application/json', json_encode({'events': events}))
                    del events
                    gc.collect()
                except Exception as e:
                    print('Error reading events:', e)
                    send_response(conn, '500 Internal Server Error', 'application/json', json_encode({'error': str(e)}))
                    gc.collect()
            else:
                send_response(conn, '405 Method Not Allowed', 'application/json', json_encode({'error': 'Only GET allowed'}))
                gc.collect()
        
        elif path == '/api/system/memory':
            if method == 'GET':
                try:
                    gc.collect()
                    free_mem = gc.mem_free()
                    send_response(conn, '200 OK', 'application/json', json_encode({'free_memory': free_mem}))
                    del free_mem
                    gc.collect()
                except Exception as e:
                    print('Error reading memory:', e)
                    send_response(conn, '500 Internal Server Error', 'application/json', json_encode({'error': str(e)}))
                    gc.collect()
            else:
                send_response(conn, '405 Method Not Allowed', 'application/json', json_encode({'error': 'Only GET allowed'}))
                gc.collect()
        
        elif path == '/api/system/uptime':
            if method == 'GET':
                try:
                    uptime_seconds = int(time.time() - SERVER_START_TIME)
                    send_response(conn, '200 OK', 'application/json', json_encode({'uptime': uptime_seconds}))
                    del uptime_seconds
                    gc.collect()
                except Exception as e:
                    print('Error reading uptime:', e)
                    send_response(conn, '500 Internal Server Error', 'application/json', json_encode({'error': str(e)}))
                    gc.collect()
            else:
                send_response(conn, '405 Method Not Allowed', 'application/json', json_encode({'error': 'Only GET allowed'}))
                gc.collect()
        
        elif path == '/api/config':
            if method == 'GET':
                try:
                    import config
                    result = {
                        'ntfy_topic': config.NTFY_TOPIC if hasattr(config, 'NTFY_TOPIC') else 'N/A',
                        'ntfy_server': config.NTFY_SERVER if hasattr(config, 'NTFY_SERVER') else 'N/A'
                    }
                    send_response(conn, '200 OK', 'application/json', json_encode(result))
                    del result
                    gc.collect()
                except Exception as e:
                    print('Error reading config:', e)
                    send_response(conn, '500 Internal Server Error', 'application/json', json_encode({'error': str(e)}))
                    gc.collect()
            else:
                send_response(conn, '405 Method Not Allowed', 'application/json', json_encode({'error': 'Only GET allowed'}))
                gc.collect()
        
        elif path == '/api/calibration':
            if method == 'GET':
                try:
                    import calibration_service
                    data = calibration_service.get_current_calibration()
                    send_response(conn, '200 OK', 'application/json', json_encode(data))
                    del data
                    gc.collect()
                except Exception as e:
                    print('Error reading calibration:', e)
                    send_response(conn, '500 Internal Server Error', 'application/json', json_encode({'error': str(e)}))
                    gc.collect()
            else:
                send_response(conn, '405 Method Not Allowed', 'application/json', json_encode({'error': 'Only GET allowed'}))
                gc.collect()
        
        elif path == '/api/calibration/save':
            if method == 'POST':
                try:
                    import calibration_service
                    duty_cycle = body_data.get('duty_cycle')
                    pulse_duration = body_data.get('pulse_duration')
                    if duty_cycle is not None and pulse_duration is not None:
                        success = calibration_service.save_calibration(duty_cycle, pulse_duration)
                        if success:
                            send_response(conn, '200 OK', 'application/json', json_encode({'status': 'ok', 'duty_cycle': duty_cycle, 'pulse_duration': pulse_duration}))
                            gc.collect()
                        else:
                            send_response(conn, '500 Internal Server Error', 'application/json', json_encode({'error': 'Failed to save'}))
                            gc.collect()
                    else:
                        send_response(conn, '400 Bad Request', 'application/json', json_encode({'error': 'Missing parameters'}))
                        gc.collect()
                except Exception as e:
                    print('Error saving calibration:', e)
                    send_response(conn, '500 Internal Server Error', 'application/json', json_encode({'error': str(e)}))
                    gc.collect()
            else:
                send_response(conn, '405 Method Not Allowed', 'application/json', json_encode({'error': 'Only POST allowed'}))
                gc.collect()
        
        elif path == '/api/calibration/adjust_duty':
            if method == 'POST':
                try:
                    import calibration_service
                    increment = body_data.get('increment', 1)
                    duty_cycle, pulse_duration = calibration_service.adjust_duty_cycle(increment)
                    send_response(conn, '200 OK', 'application/json', json_encode({'status': 'ok', 'duty_cycle': duty_cycle, 'pulse_duration': pulse_duration}))
                    gc.collect()
                except Exception as e:
                    print('Error adjusting duty cycle:', e)
                    send_response(conn, '500 Internal Server Error', 'application/json', json_encode({'error': str(e)}))
                    gc.collect()
            else:
                send_response(conn, '405 Method Not Allowed', 'application/json', json_encode({'error': 'Only POST allowed'}))
                gc.collect()
        
        elif path == '/api/calibration/adjust_duration':
            if method == 'POST':
                try:
                    import calibration_service
                    increment = body_data.get('increment', 5)
                    duty_cycle, pulse_duration = calibration_service.adjust_pulse_duration(increment)
                    send_response(conn, '200 OK', 'application/json', json_encode({'status': 'ok', 'duty_cycle': duty_cycle, 'pulse_duration': pulse_duration}))
                    gc.collect()
                except Exception as e:
                    print('Error adjusting pulse duration:', e)
                    send_response(conn, '500 Internal Server Error', 'application/json', json_encode({'error': str(e)}))
                    gc.collect()
            else:
                send_response(conn, '405 Method Not Allowed', 'application/json', json_encode({'error': 'Only POST allowed'}))
                gc.collect()

        elif path == '/api/calibration/test':
            if method == 'POST':
                try:
                    import calibration_service
                    result = calibration_service.test_calibration()
                    send_response(conn, '200 OK', 'application/json', json_encode(result))
                    gc.collect()
                except Exception as e:
                    print('Error testing calibration:', e)
                    send_response(conn, '500 Internal Server Error', 'application/json', json_encode({'error': str(e)}))
                    gc.collect()
            else:
                send_response(conn, '405 Method Not Allowed', 'application/json', json_encode({'error': 'Only POST allowed'}))
                gc.collect()
        
        elif path == '/api/calibrate/left' or path == '/api/calibrate/right':
            if method == 'POST':
                try:
                    # Check if running on actual hardware (ESP8266/ESP32)
                    try:
                        from machine import Pin
                        on_hardware = True
                    except ImportError:
                        on_hardware = False
                        print('Warning: Not running on ESP hardware, motor control disabled')
                    # The actual motor movement logic should be here, but is omitted for brevity
                    # You may want to add direction handling logic if needed
                    # For now, just return a success message
                    result = json_encode({'status': 'ok', 'message': 'Motor calibration endpoint called'})
                    send_response(conn, '200 OK', 'application/json', result)
                    del result
                    gc.collect()
                except Exception as e:
                    print('Error in calibration:', e)
                    error_msg = 'Calibration error: {}'.format(str(e))
                    send_response(conn, '500 Internal Server Error', 'application/json', json_encode({'status': 'error', 'message': error_msg}))
                    gc.collect()
            else:
                send_response(conn, '405 Method Not Allowed', 'application/json', json_encode({'error': 'Only POST allowed'}))
                gc.collect()

        elif path == '/api/ota/check':
            if method == 'GET':
                try:
                    from ota.ota_updater import OTAUpdater
                    updater = OTAUpdater()
                    remote_data = updater.check_for_updates()
                    
                    if remote_data:
                        result = json_encode({
                            'update_available': True,
                            'version': remote_data['version'],
                            'date': remote_data.get('date', ''),
                            'notes': remote_data.get('notes', ''),
                            'files_count': len(remote_data.get('files', []))
                        })
                    else:
                        result = json_encode({'update_available': False})
                    
                    send_response(conn, '200 OK', 'application/json', result)
                    del result, updater, remote_data
                    gc.collect()
                except Exception as e:
                    print('OTA check error:', e)
                    error_msg = json_encode({'error': str(e)})
                    send_response(conn, '500 Internal Server Error', 'application/json', error_msg)
                    gc.collect()
            else:
                send_response(conn, '405 Method Not Allowed', 'application/json', json_encode({'error': 'Only GET allowed'}))
                gc.collect()

        elif path == '/api/ota/update':
            if method == 'POST':
                try:
                    from ota.ota_updater import check_and_update
                    success = check_and_update()
                    result = json_encode({'success': success})
                    send_response(conn, '200 OK', 'application/json', result)
                    del result, success
                    gc.collect()
                except Exception as e:
                    print('OTA update error:', e)
                    error_msg = json_encode({'success': False, 'error': str(e)})
                    send_response(conn, '500 Internal Server Error', 'application/json', error_msg)
                    gc.collect()
            else:
                send_response(conn, '405 Method Not Allowed', 'application/json', json_encode({'error': 'Only POST allowed'}))
                gc.collect()

        elif path == '/api/system/reboot':
            if method == 'POST':
                try:
                    result = json_encode({'success': True, 'message': 'Rebooting...'})
                    send_response(conn, '200 OK', 'application/json', result)
                    del result
                    gc.collect()
                    # Reboot after sending response
                    import machine
                    import utime as time
                    time.sleep(1)
                    machine.reset()
                except Exception as e:
                    print('Reboot error:', e)
                    error_msg = json_encode({'success': False, 'error': str(e)})
                    send_response(conn, '500 Internal Server Error', 'application/json', error_msg)
                    gc.collect()
            else:
                send_response(conn, '405 Method Not Allowed', 'application/json', json_encode({'error': 'Only POST allowed'}))
                gc.collect()

        elif path == '/' or path == '/index.html':
            try:
                # Stream file in chunks to avoid memory issues
                with open('UI/index.html', 'rb') as f:
                    # Get file size
                    import os
                    file_size = os.stat('UI/index.html')[6]
                    
                    # Send headers
                    response = 'HTTP/1.1 200 OK\r\n'
                    response += 'Content-Type: text/html\r\n'
                    response += 'Access-Control-Allow-Origin: *\r\n'
                    response += 'Connection: close\r\n'
                    response += 'Content-Length: {}\r\n'.format(file_size)
                    # Prevent caching of HTML pages
                    response += 'Cache-Control: no-cache, no-store, must-revalidate\r\n'
                    response += 'Pragma: no-cache\r\n'
                    response += 'Expires: 0\r\n'
                    response += '\r\n'
                    conn.send(response.encode())
                    
                    # Stream file in 512 byte chunks
                    while True:
                        chunk = f.read(512)
                        if not chunk:
                            break
                        conn.send(chunk)
                        gc.collect()
            except Exception as e:
                print('Error serving index.html:', e)
                error_msg = 'Error: {}'.format(str(e))
                send_response(conn, '500 Internal Server Error', 'text/html', '<html><body><h1>Error</h1><p>{}</p></body></html>'.format(error_msg))
                
        else:
            # Try to serve static file
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
                
                print('Serving file:', file_path)
                
                # Stream file in chunks to avoid memory issues
                import os
                file_size = os.stat(file_path)[6]
                
                # Send headers
                response = 'HTTP/1.1 200 OK\r\n'
                response += 'Content-Type: {}\r\n'.format(content_type)
                response += 'Access-Control-Allow-Origin: *\r\n'
                response += 'Connection: close\r\n'
                response += 'Content-Length: {}\r\n'.format(file_size)
                
                # Add caching headers for images (cache for 1 week)
                if content_type.startswith('image/'):
                    response += 'Cache-Control: public, max-age=604800\r\n'  # 7 days
                    response += 'Expires: Thu, 31 Dec 2026 23:59:59 GMT\r\n'
                else:
                    # No cache for HTML, CSS, JS files
                    response += 'Cache-Control: no-cache, no-store, must-revalidate\r\n'
                    response += 'Pragma: no-cache\r\n'
                    response += 'Expires: 0\r\n'
                
                response += '\r\n'
                conn.send(response.encode())
                
                # Stream file in 512 byte chunks
                with open(file_path, 'rb') as f:
                    while True:
                        chunk = f.read(512)
                        if not chunk:
                            break
                        conn.send(chunk)
                        gc.collect()
                        
            except Exception as e:
                print('Error serving file {}: {}'.format(file_path, e))
                send_response(conn, '404 Not Found', 'text/plain', 'Not Found')
        
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
        """Async server implementation that allows concurrent tasks."""
        import uasyncio as asyncio
        
        # Get actual IP address
        actual_ip = self._get_ip(host)
        
        # Create and bind socket
        addr = socket.getaddrinfo(host, port)[0][-1]
        self.socket = socket.socket()
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.socket.bind(addr)
        self.socket.listen(5)
        self.socket.setblocking(False)  # Non-blocking for asyncio
        print('Server running on {}:{}'.format(actual_ip, port))
        
        # Send startup notification
        self._send_startup_notification(actual_ip, port)
        
        while True:
            try:
                # Accept connections asynchronously
                conn, addr = await asyncio.wait_for(
                    self._accept_connection(), 
                    timeout=1
                )
                print('Connection from', addr)
                
                # Handle request in a separate task (non-blocking)
                asyncio.create_task(self._handle_connection(conn))
                
            except asyncio.TimeoutError:
                # Timeout allows other tasks (like scheduler) to run
                await asyncio.sleep(0)
            except Exception as e:
                print('Server error:', e)
                await asyncio.sleep(0.1)
                gc.collect()
    
    async def _accept_connection(self):
        """Async wrapper for socket.accept()."""
        import uasyncio as asyncio
        while True:
            try:
                return self.socket.accept()
            except OSError:
                await asyncio.sleep(0.1)
    
    async def _handle_connection(self, conn):
        """Handle a single connection asynchronously."""
        import uasyncio as asyncio
        try:
            conn.settimeout(5.0)
            
            # Read request
            request = b''
            while True:
                try:
                    chunk = conn.recv(1024)
                    if not chunk:
                        break
                    request += chunk
                    # Check if we have full request
                    if b'\r\n\r\n' in request:
                        # Check if there's a body
                        if b'Content-Length:' in request:
                            header_end = request.find(b'\r\n\r\n')
                            headers = request[:header_end].decode()
                            for line in headers.split('\r\n'):
                                if line.startswith('Content-Length:'):
                                    content_length = int(line.split(':')[1].strip())
                                    body_received = len(request) - header_end - 4
                                    if body_received >= content_length:
                                        break
                        else:
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
        """Blocking server implementation (fallback if asyncio unavailable)."""
        actual_ip = self._get_ip(host)
        
        addr = socket.getaddrinfo(host, port)[0][-1]
        self.socket = socket.socket()
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.socket.bind(addr)
        self.socket.listen(5)
        print('Server running on {}:{}'.format(actual_ip, port))
        
        self._send_startup_notification(actual_ip, port)
        
        while True:
            conn = None
            try:
                conn, addr = self.socket.accept()
                conn.settimeout(5.0)
                
                # Read request
                request = b''
                while True:
                    try:
                        chunk = conn.recv(1024)
                        if not chunk:
                            break
                        request += chunk
                        if b'\r\n\r\n' in request:
                            if b'Content-Length:' in request:
                                header_end = request.find(b'\r\n\r\n')
                                headers = request[:header_end].decode()
                                for line in headers.split('\r\n'):
                                    if line.startswith('Content-Length:'):
                                        content_length = int(line.split(':')[1].strip())
                                        body_received = len(request) - header_end - 4
                                        if body_received >= content_length:
                                            break
                            else:
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
        """Get actual IP address."""
        if host == '0.0.0.0':
            try:
                import network
                sta = network.WLAN(network.STA_IF)
                if sta.isconnected():
                    return sta.ifconfig()[0]
            except:
                pass
        return host
    
    def _send_startup_notification(self, ip, port):
        """Send startup notification."""
        try:
            import lib.notification
            import utime as time
            url = 'http://{}:{}'.format(ip, port)
            now = time.localtime()
            time_str = "{:02d}:{:02d}:{:02d}".format(now[3], now[4], now[5])
            msg = 'Feeder started at {} and can be accessed at {}'.format(time_str, url)
            lib.notification.send_ntfy_notification(msg)
            print('Startup notification sent:', msg)
        except Exception as e:
            print('Could not send startup notification:', e)

app = SimpleServer()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
