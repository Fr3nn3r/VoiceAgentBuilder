#!/usr/bin/env python3
"""Simple HTTP server to serve the owl avatar frontend."""

import http.server
import socketserver
import os
from pathlib import Path

PORT = 8080
DIRECTORY = "public"


class MyHTTPRequestHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=DIRECTORY, **kwargs)

    def end_headers(self):
        # Add CORS headers for development
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate")
        super().end_headers()


if __name__ == "__main__":
    import sys
    import threading

    # Ensure the public directory exists
    public_dir = Path(__file__).parent / DIRECTORY
    if not public_dir.exists():
        print(f"[X] Error: {DIRECTORY}/ directory not found")
        exit(1)

    os.chdir(public_dir.parent)

    # Allow reuse of address to prevent "Address already in use" errors
    socketserver.TCPServer.allow_reuse_address = True

    httpd = socketserver.TCPServer(("", PORT), MyHTTPRequestHandler)

    print(f"[OK] Serving owl avatar frontend at http://localhost:{PORT}")
    print(f"[OK] Open http://localhost:{PORT} in your browser")
    print("[OK] Press Ctrl+C to stop")

    # Run server in a thread so Ctrl+C works properly on Windows
    server_thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    server_thread.start()

    try:
        # Keep main thread alive
        server_thread.join()
    except KeyboardInterrupt:
        print("\n[OK] Server stopped")
        httpd.shutdown()
        sys.exit(0)
