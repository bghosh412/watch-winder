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
        # Default handler: just return status OK
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
