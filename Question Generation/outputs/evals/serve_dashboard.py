#!/usr/bin/env python3
"""
Simple HTTP server to serve the evaluation dashboard.
Run this script from the evals directory to access the dashboard in your browser.
"""

import http.server
import socketserver
import os
import socket

def get_local_ip():
    """Get the local IP address of the container/machine."""
    try:
        # Create a socket to get the local IP
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
        return local_ip
    except Exception:
        return "localhost"

def find_free_port(start_port=8000, max_attempts=10):
    """Find a free port starting from start_port."""
    for port in range(start_port, start_port + max_attempts):
        try:
            with socketserver.TCPServer(("", port), None) as s:
                return port
        except OSError:
            continue
    raise RuntimeError(f"Could not find a free port in range {start_port}-{start_port + max_attempts}")

class CORSRequestHandler(http.server.SimpleHTTPRequestHandler):
    """HTTP request handler with CORS enabled."""
    
    def end_headers(self):
        """Add CORS headers to all responses."""
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', '*')
        self.send_header('Cache-Control', 'no-store, no-cache, must-revalidate')
        super().end_headers()
    
    def log_message(self, format, *args):
        """Custom log message format."""
        print(f"[{self.log_date_time_string()}] {format % args}")

def main():
    # Change to the directory where this script is located
    script_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(script_dir)
    
    # Find a free port
    try:
        port = find_free_port()
    except RuntimeError as e:
        print(f"Error: {e}")
        return
    
    # Get local IP
    local_ip = get_local_ip()
    
    # Create server
    Handler = CORSRequestHandler
    
    try:
        with socketserver.TCPServer(("", port), Handler) as httpd:
            print("\n" + "="*60)
            print("🚀 Evaluation Dashboard Server Started!")
            print("="*60)
            print(f"\n📊 Dashboard URL: http://localhost:{port}")
            if local_ip != "localhost":
                print(f"   (or from outside: http://{local_ip}:{port})")
            print(f"\n📁 Serving from: {script_dir}")
            print(f"\n💡 Access the dashboard at: http://localhost:{port}/index.html")
            print("\n⌨️  Press Ctrl+C to stop the server")
            print("="*60 + "\n")
            
            httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n\n👋 Server stopped. Goodbye!")
    except Exception as e:
        print(f"\n❌ Error starting server: {e}")

if __name__ == "__main__":
    main()

