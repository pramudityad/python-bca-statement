#!/usr/bin/env python3
"""
AFTIS Parser HTTP Server
Provides REST API for PDF parsing with PostgreSQL integration
"""

import os
import json
import shutil
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import subprocess
import sys
import psycopg2
from psycopg2.extras import RealDictCursor
import logging

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def get_db_connection():
    """Get PostgreSQL database connection"""
    try:
        conn = psycopg2.connect(
            host=os.getenv('POSTGRES_HOST', 'postgres'),
            port=os.getenv('POSTGRES_PORT', '5432'),
            database=os.getenv('POSTGRES_DB', 'aftis'),
            user=os.getenv('POSTGRES_USER', 'aftis_user'),
            password=os.getenv('POSTGRES_PASSWORD', 'aftis_password')
        )
        return conn
    except Exception as e:
        logger.error(f"Database connection failed: {e}")
        return None

def insert_transactions(transactions):
    """Insert transactions into PostgreSQL database"""
    if not transactions:
        return False
    
    conn = get_db_connection()
    if not conn:
        return False
    
    try:
        cursor = conn.cursor()
        
        insert_query = """
            INSERT INTO transactions (date, description, detail, branch, amount, transaction_type, balance, account_number, period)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        
        for txn in transactions:
            cursor.execute(insert_query, (
                txn.get('date'),
                txn.get('description'),
                txn.get('detail'),
                txn.get('branch'),
                txn.get('amount'),
                txn.get('transaction_type'),
                txn.get('balance'),
                txn.get('account_number'),
                txn.get('period')
            ))
        
        conn.commit()
        logger.info(f"Inserted {len(transactions)} transactions into database")
        return True
        
    except Exception as e:
        logger.error(f"Database insert failed: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()

class AFTISHandler(BaseHTTPRequestHandler):
    
    def do_GET(self):
        """Handle GET requests for file scanning"""
        if self.path == '/scan':
            self.scan_inbox()
        elif self.path == '/health':
            self.health_check()
        elif self.path == '/db-health':
            self.db_health_check()
        elif self.path.startswith('/transactions'):
            self.get_transactions()
        else:
            self.send_error(404)
    
    def do_POST(self):
        """Handle POST requests for PDF parsing"""
        print(f"POST request to {self.path}")
        print(f"Headers: {dict(self.headers)}")
        if self.path == '/parse':
            self.parse_pdf()
        elif self.path == '/parse-and-store':
            self.parse_and_store_pdf()
        elif self.path == '/test':
            self.test_response()
        else:
            self.send_error(404)
    
    def test_response(self):
        """Simple test endpoint"""
        try:
            test_data = {'message': 'hello', 'count': 123}
            response_json = json.dumps(test_data)
            
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(response_json.encode())
        except Exception as e:
            self.send_error(500, str(e))
    
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
                try:
                    transactions = json.loads(result.stdout)
                    
                    # Create minimal, clean response
                    clean_transactions = []
                    for i, txn in enumerate(transactions[:3]):  # Only first 3 for testing
                        clean_txn = {
                            'id': i + 1,
                            'date': str(txn.get('date', '')).replace('/', '-') if txn.get('date') else '',
                            'amount': float(txn.get('amount', 0)) if txn.get('amount') else 0,
                            'type': str(txn.get('transaction_type', ''))[:2] if txn.get('transaction_type') else '',
                            'description': str(txn.get('description', ''))[:50] if txn.get('description') else ''  # Truncate long descriptions
                        }
                        clean_transactions.append(clean_txn)
                    
                    response_data = {
                        'success': True,
                        'count': len(clean_transactions),
                        'total': len(transactions),
                        'data': clean_transactions
                    }
                    
                    # Ensure clean JSON with no special characters
                    response_json = json.dumps(response_data, ensure_ascii=True, separators=(',', ':'))
                    
                    self.send_response(200)
                    self.send_header('Content-type', 'application/json')
                    self.end_headers()
                    self.wfile.write(response_json.encode('ascii'))
                    
                except json.JSONDecodeError as e:
                    self.send_error(500, f'JSON parse error: {str(e)}')
                except Exception as e:
                    self.send_error(500, f'Processing error: {str(e)}')
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
    
    def db_health_check(self):
        """Database health check endpoint"""
        try:
            conn = get_db_connection()
            if conn:
                cursor = conn.cursor()
                cursor.execute("SELECT 1")
                conn.close()
                
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({'database': 'healthy'}).encode())
            else:
                self.send_error(503, 'Database connection failed')
        except Exception as e:
            self.send_error(503, f'Database error: {str(e)}')
    
    def get_transactions(self):
        """Get transactions from database"""
        try:
            # Parse query parameters
            parsed_url = urlparse(self.path)
            query_params = parse_qs(parsed_url.query)
            
            limit = int(query_params.get('limit', ['100'])[0])
            account = query_params.get('account', [None])[0]
            period = query_params.get('period', [None])[0]
            
            conn = get_db_connection()
            if not conn:
                self.send_error(503, 'Database connection failed')
                return
            
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            
            # Build query
            query = "SELECT * FROM transactions WHERE 1=1"
            params = []
            
            if account:
                query += " AND account_number = %s"
                params.append(account)
            
            if period:
                query += " AND period = %s"
                params.append(period)
            
            query += " ORDER BY date DESC, created_at DESC LIMIT %s"
            params.append(limit)
            
            cursor.execute(query, params)
            transactions = cursor.fetchall()
            conn.close()
            
            # Convert to list of dicts for JSON serialization
            transactions_list = [dict(txn) for txn in transactions]
            
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(transactions_list, default=str).encode())
            
        except Exception as e:
            self.send_error(500, f'Error retrieving transactions: {str(e)}')
    
    def parse_and_store_pdf(self):
        """Parse a PDF file and store results in database"""
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
                try:
                    transactions = json.loads(result.stdout)
                    
                    # Store in database
                    db_success = insert_transactions(transactions)
                    
                    response_data = {
                        'success': True,
                        'parsed_count': len(transactions),
                        'database_stored': db_success,
                        'message': f"Parsed {len(transactions)} transactions" + 
                                 (", stored in database" if db_success else ", database storage failed")
                    }
                    
                    self.send_response(200)
                    self.send_header('Content-type', 'application/json')
                    self.end_headers()
                    self.wfile.write(json.dumps(response_data).encode())
                    
                except json.JSONDecodeError as e:
                    self.send_error(500, f'JSON parse error: {str(e)}')
                except Exception as e:
                    self.send_error(500, f'Processing error: {str(e)}')
            else:
                self.send_error(500, f'Parser error: {result.stderr}')
                
        except Exception as e:
            self.send_error(500, str(e))

def main():
    # Ensure directories exist
    os.makedirs('/srv/aftis/inbox', exist_ok=True)
    os.makedirs('/srv/aftis/tmp', exist_ok=True)
    
    server = HTTPServer(('0.0.0.0', 8080), AFTISHandler)
    print("AFTIS Parser Server starting on port 8080...")
    server.serve_forever()

if __name__ == "__main__":
    main()