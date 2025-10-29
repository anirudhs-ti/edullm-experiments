#!/usr/bin/env python3
"""
Simple HTTP server to serve the Grade 3 mappings viewer website.
Run this script and open http://localhost:8000 in your browser.

The website displays the brute-force mapping results from substandard_to_sequence_mappings.v3.json
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
    # Change to the script's directory
    script_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(script_dir)
    
    viewer = 'mappings_viewer.html'
    viewer_name = 'Grade 3 Substandard Mappings Viewer (Brute-Force Results)'
    
    handler = MyHTTPRequestHandler
    
    with socketserver.TCPServer(("", PORT), handler) as httpd:
        print(f"{'='*60}")
        print(f"Server started at http://localhost:{PORT}")
        print(f"Serving: {viewer_name}")
        print(f"Directory: {os.getcwd()}")
        print(f"{'='*60}")
        print(f"\nOpen your browser to: http://localhost:{PORT}/{viewer}")
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
