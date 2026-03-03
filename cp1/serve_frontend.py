import http.server
import socketserver
import os
import webbrowser
import threading
import time
PORT = 8080
DIRECTORY = "."
class MyHTTPRequestHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=DIRECTORY, **kwargs)
    def end_headers(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.send_header('Cache-Control', 'no-store, no-cache, must-revalidate')
        super().end_headers()
    def log_message(self, format, *args):
        pass
def open_browser():
    time.sleep(1)
    webbrowser.open(f'http://localhost:{PORT}')
if __name__ == '__main__':
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    print("=" * 60)
    print("🌐 GlucoNova AI - Frontend Server")
    print("=" * 60)
    print(f"📡 Server starting on http://localhost:{PORT}")
    print(f"📂 Serving files from: {os.getcwd()}")
    print()
    print("✅ Server is ready!")
    print(f"🌐 Open your browser to: http://localhost:{PORT}")
    print()
    print("⚠️  Keep this window open while using the application")
    print("🛑 Press Ctrl+C to stop the server")
    print("=" * 60)
    print()
    try:
        with socketserver.TCPServer(("", PORT), MyHTTPRequestHandler) as httpd:
            httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n\n🛑 Server stopped by user")
        print("=" * 60)
