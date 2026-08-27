import http.server, socketserver, os, base64
D = os.path.dirname(os.path.abspath(__file__))
os.chdir(D)
class H(http.server.SimpleHTTPRequestHandler):
    def guess_type(self, path):
        t = super().guess_type(path)
        return 'text/html; charset=utf-8' if t == 'text/html' else t
    def do_POST(self):
        n = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(n).decode('utf-8')
        name = self.path.strip('/') or 'out'
        if ',' in body:
            body = body.split(',', 1)[1]
        with open(os.path.join(D, name + '.png'), 'wb') as f:
            f.write(base64.b64decode(body))
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Content-Length', '2')
        self.end_headers()
        self.wfile.write(b'ok')
socketserver.TCPServer.allow_reuse_address = True
with socketserver.TCPServer(("127.0.0.1", 8793), H) as s:
    s.serve_forever()
