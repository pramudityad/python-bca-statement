#!/usr/bin/env python3
"""
AFTIS Parser HTTP Server
Provides REST API for PDF parsing
"""

import os
import json
import shutil
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import subprocess
import sys

class AFTISHandler(BaseHTTPRequestHandler):
    
    def do_GET(self):
        """Handle GET requests for file scanning"""
        if self.path == '/scan':
            self.scan_inbox()
        elif self.path == '/health':
            self.health_check()
        else:
            self.send_error(404)
    
    def do_POST(self):
        """Handle POST requests for PDF parsing"""
        if self.path == '/parse':
            self.parse_pdf()
        else:
            self.send_error(404)
    
    def scan_inbox(self):
        """Scan inbox folder for PDF files"""
        try:
            inbox_path = '/srv/aftis/inbox'
            pdf_files = []
            
            if os.path.exists(inbox_path):
                for filename in os.listdir(inbox_path):
                    if filename.lower().endswith('.pdf'):
                        pdf_files.append(os.path.join(inbox_path, filename))
            
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({'files': pdf_files}).encode())
            
        except Exception as e:
            self.send_error(500, str(e))
    
    def parse_pdf(self):
        """Parse a PDF file"""
        try:
            # Get content length
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            data = json.loads(post_data.decode())
            
            pdf_path = data.get('pdf_path')
            if not pdf_path:
                self.send_error(400, 'pdf_path required')
                return
            
            # Copy to temp directory
            temp_path = f"/srv/aftis/tmp/{os.path.basename(pdf_path)}"
            shutil.copy2(pdf_path, temp_path)
            
            # Run parser
            result = subprocess.run([
                'python3', '/srv/aftis/parse.py', temp_path
            ], capture_output=True, text=True)
            
            # Clean up temp file
            if os.path.exists(temp_path):
                os.remove(temp_path)
            
            if result.returncode == 0:
                transactions = json.loads(result.stdout)
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({'transactions': transactions}).encode())
            else:
                self.send_error(500, f'Parser error: {result.stderr}')
                
        except Exception as e:
            self.send_error(500, str(e))
    
    def health_check(self):
        """Health check endpoint"""
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps({'status': 'healthy'}).encode())

def main():
    # Ensure directories exist
    os.makedirs('/srv/aftis/inbox', exist_ok=True)
    os.makedirs('/srv/aftis/tmp', exist_ok=True)
    
    server = HTTPServer(('0.0.0.0', 8080), AFTISHandler)
    print("AFTIS Parser Server starting on port 8080...")
    server.serve_forever()

if __name__ == "__main__":
    main()