#!/usr/bin/env python3
"""
Simple HTTP server to serve the curriculum viewer website.
Run this script and open http://localhost:8000 in your browser.

Usage:
    python serve.py                  # Serves viewer.html (DI formats viewer)
    python serve.py formats          # Serves viewer.html (DI formats viewer)
    python serve.py mappings         # Serves mappings_viewer.html (substandard mappings)
"""

import http.server
import socketserver
import webbrowser
import os
import sys

PORT = 8000

class MyHTTPRequestHandler(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        # Add CORS headers to allow local development
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        super().end_headers()

def main():
    # Determine which viewer to open based on command line argument
    viewer = 'viewer.html'  # Default
    viewer_name = 'DI Formats Viewer'
    
    if len(sys.argv) > 1:
        arg = sys.argv[1].lower()
        if arg in ['mappings', 'mapping', 'm']:
            viewer = 'mappings_viewer.html'
            viewer_name = 'Substandard Mappings Viewer'
        elif arg in ['formats', 'format', 'f', 'viewer']:
            viewer = 'viewer.html'
            viewer_name = 'DI Formats Viewer'
        elif arg in ['help', '-h', '--help']:
            print(__doc__)
            return
        else:
            print(f"Unknown option: {arg}")
            print("\nAvailable options:")
            print("  formats   - DI Formats Viewer (default)")
            print("  mappings  - Substandard Mappings Viewer")
            print("  help      - Show this help message")
            return
    
    handler = MyHTTPRequestHandler
    
    with socketserver.TCPServer(("", PORT), handler) as httpd:
        print(f"{'='*60}")
        print(f"Server started at http://localhost:{PORT}")
        print(f"Serving: {viewer_name}")
        print(f"Directory: {os.getcwd()}")
        print(f"{'='*60}")
        print("\nPress Ctrl+C to stop the server")
        
        # Try to open browser automatically
        try:
            webbrowser.open(f'http://localhost:{PORT}/{viewer}')
        except:
            pass
        
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n\nServer stopped.")

if __name__ == "__main__":
    main()


