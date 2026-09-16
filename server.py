import os
import json
import urllib.parse
from http.server import HTTPServer, SimpleHTTPRequestHandler

PORT = 8080
DATA_FILE = os.path.join(os.path.dirname(__file__), 'rsvps.json')

def ensure_data_file():
    if not os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump([], f, ensure_ascii=False, indent=2)

class CustomHandler(SimpleHTTPRequestHandler):
    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()

    def do_POST(self):
        if self.path == '/api/rsvp':
            content_length = int(self.headers.get('Content-Length', 0))
            post_data = self.rfile.read(content_length)
            
            try:
                data = json.loads(post_data.decode('utf-8'))
            except Exception:
                data = urllib.parse.parse_qs(post_data.decode('utf-8'))

            ensure_data_file()

            rsvps = []
            try:
                with open(DATA_FILE, 'r', encoding='utf-8') as f:
                    rsvps = json.load(f)
            except Exception:
                rsvps = []

            rsvps.append(data)

            with open(DATA_FILE, 'w', encoding='utf-8') as f:
                json.dump(rsvps, f, ensure_ascii=False, indent=2)

            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps({"status": "success", "total": len(rsvps)}).encode('utf-8'))
        else:
            self.send_error(404, "Endpoint not found")

    def do_GET(self):
        if self.path == '/admin' or self.path == '/rsvps':
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.end_headers()
            
            rsvps = []
            ensure_data_file()
            try:
                with open(DATA_FILE, 'r', encoding='utf-8') as f:
                    rsvps = json.load(f)
            except Exception:
                pass

            html = "<html><head><meta charset='utf-8'><title>Коноктордун жооптору — Эрбол & Аделина</title>"
            html += "<meta name='viewport' content='width=device-width, initial-scale=1.0'>"
            html += "<style>body{font-family:Segoe UI, sans-serif;padding:24px;background:#FAF8F5;color:#2D2825;} table{width:100%;border-collapse:collapse;margin-top:16px;background:#FFF;box-shadow:0 4px 15px rgba(0,0,0,0.05);border-radius:8px;overflow:hidden;} th,td{padding:14px;border-bottom:1px solid #eee;text-align:left;} th{background:#C5A880;color:white;font-weight:600;} tr:hover{background:#FDFBF7;} .badge-yes{color:#2e7d32;font-weight:600;} .badge-no{color:#c62828;}</style></head><body>"
            html += "<h2>🤍 Эрбол & Аделина — Коноктордун жооптору (RSVP)</h2>"
            html += f"<p style='font-size:1.1rem;'><b>Жалпы жооп берген коноктордун саны:</b> {len(rsvps)}</p>"
            html += "<table><tr><th>#</th><th>Коноктун аты-жөнү</th><th>Катышуусу</th><th>Убактысы</th></tr>"
            
            for idx, item in enumerate(reversed(rsvps), 1):
                name = item.get('name', item.get('guestName', '-'))
                att = item.get('attendance', '-')
                ts = item.get('timestamp', '-')
                cls = "badge-yes" if "Ооба" in str(att) else "badge-no"
                html += f"<tr><td>{idx}</td><td><b>{name}</b></td><td class='{cls}'>{att}</td><td>{ts}</td></tr>"
            
            html += "</table></body></html>"
            self.wfile.write(html.encode('utf-8'))
        else:
            super().do_GET()

if __name__ == '__main__':
    ensure_data_file()
    print(f"Server started on port {PORT}")
    server = HTTPServer(('0.0.0.0', PORT), CustomHandler)
    server.serve_forever()
