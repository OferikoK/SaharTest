#!/usr/bin/env python3
"""
מעקב תרגול - מבחן מחוננים
===========================
שרת מקומי שמריץ את האתר ומאפשר העברת קבצים לתיקיית "סיימנו".

הפעלה:
  python3 start_tracker.py

ואז פתח בנייד: http://<IP-של-המחשב>:8888
"""

import http.server
import json
import os
import shutil
import socketserver
import urllib.parse
import webbrowser

PORT = 8888
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DONE_DIR = os.path.join(BASE_DIR, "סיימנו")
STATE_FILE = os.path.join(BASE_DIR, ".tracker_state.json")

os.makedirs(DONE_DIR, exist_ok=True)


def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {"completed": [], "prizes": []}


def save_state(data):
    with open(STATE_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def move_to_done(filename):
    """Move a PDF file to the סיימנו folder"""
    src = os.path.join(BASE_DIR, filename + ".pdf")
    dst = os.path.join(DONE_DIR, filename + ".pdf")
    if os.path.exists(src):
        shutil.move(src, dst)
        return True
    return False


def move_back(filename):
    """Move a PDF file back from סיימנו folder"""
    src = os.path.join(DONE_DIR, filename + ".pdf")
    dst = os.path.join(BASE_DIR, filename + ".pdf")
    if os.path.exists(src):
        shutil.move(src, dst)
        return True
    return False


class TrackerHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=BASE_DIR, **kwargs)

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == '/' or parsed.path == '/index.html':
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.end_headers()
            # Read the HTML file and inject the saved state
            html_path = os.path.join(BASE_DIR, 'tracker.html')
            with open(html_path, 'r', encoding='utf-8') as f:
                html = f.read()
            # Inject state before </body>
            state = load_state()
            inject = f"""
<script id="saved-state" type="application/json">{json.dumps(state, ensure_ascii=False)}</script>
<script>
(function() {{
  try {{
    const el = document.getElementById('saved-state');
    if (el) {{
      const saved = JSON.parse(el.textContent);
      if (saved && saved.completed) {{
        state = saved;
        state.lastAction = null;
        render();
      }}
    }}
  }} catch(e) {{ console.error(e); }}
}})();
</script>
"""
            html = html.replace('</body>', inject + '</body>')
            self.wfile.write(html.encode('utf-8'))
            return

        elif parsed.path == '/api/state':
            self.send_response(200)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            state = load_state()
            self.wfile.write(json.dumps(state, ensure_ascii=False).encode('utf-8'))
            return

        elif parsed.path == '/api/files':
            # List all PDF files in the base dir (not done)
            self.send_response(200)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.end_headers()
            files = [f[:-4] for f in os.listdir(BASE_DIR) if f.endswith('.pdf')]
            done_files = [f[:-4] for f in os.listdir(DONE_DIR) if f.endswith('.pdf')]
            self.wfile.write(json.dumps({"available": files, "done": done_files}, ensure_ascii=False).encode('utf-8'))
            return

        super().do_GET()

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length).decode('utf-8') if content_length else '{}'
        data = json.loads(body)

        if parsed.path == '/api/complete':
            unit = data.get('unit', '')
            state = load_state()
            if unit and unit not in state['completed']:
                state['completed'].append(unit)
                moved = move_to_done(unit)
                save_state(state)
                self.send_json({"ok": True, "moved": moved})
            else:
                self.send_json({"ok": False, "reason": "already done or empty"})
            return

        elif parsed.path == '/api/undo':
            unit = data.get('unit', '')
            state = load_state()
            if unit in state['completed']:
                state['completed'].remove(unit)
                moved_back = move_back(unit)
                save_state(state)
                self.send_json({"ok": True, "moved_back": moved_back})
            else:
                self.send_json({"ok": False})
            return

        elif parsed.path == '/api/add_prize':
            prize = data.get('prize', {})
            state = load_state()
            state.setdefault('prizes', []).append(prize)
            save_state(state)
            self.send_json({"ok": True})
            return

        elif parsed.path == '/api/remove_prize':
            state = load_state()
            if state.get('prizes'):
                state['prizes'].pop()
                save_state(state)
            self.send_json({"ok": True})
            return

        elif parsed.path == '/api/reset':
            # Move all files back
            state = load_state()
            for unit in state.get('completed', []):
                move_back(unit)
            save_state({"completed": [], "prizes": []})
            self.send_json({"ok": True})
            return

        self.send_json({"error": "not found"}, 404)

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()

    def send_json(self, data, code=200):
        self.send_response(code)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode('utf-8'))

    def log_message(self, format, *args):
        # Quieter logging
        if '/api/' in str(args[0]):
            print(f"  API: {args[0]}")


# Update the HTML to use API calls
HTML_UPDATE = True

if __name__ == '__main__':
    # Get local IP
    import socket
    hostname = socket.gethostname()
    try:
        local_ip = socket.gethostbyname(hostname)
    except:
        local_ip = "localhost"

    print("=" * 50)
    print("  🏆 מעקב תרגול - מבחן מחוננים")
    print("=" * 50)
    print(f"\n  📱 פתח בנייד: http://{local_ip}:{PORT}")
    print(f"  💻 או במחשב: http://localhost:{PORT}")
    print(f"\n  📁 תיקיית בסיס: {BASE_DIR}")
    print(f"  ✅ תיקיית סיימנו: {DONE_DIR}")
    print(f"\n  לעצירה: Ctrl+C")
    print("=" * 50 + "\n")

    with socketserver.TCPServer(("", PORT), TrackerHandler) as httpd:
        try:
            webbrowser.open(f"http://localhost:{PORT}")
        except:
            pass
        httpd.serve_forever()
