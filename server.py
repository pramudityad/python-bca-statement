#!/usr/bin/env python3
"""
AFTIS Parser HTTP Server
Provides REST API for PDF parsing with PostgreSQL integration
"""

import os
import json
import time
import shutil
import hashlib
import uuid
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import subprocess
import sys
import psycopg2
from psycopg2.extras import RealDictCursor
import logging

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Where the code lives (Phase 0: code moved out of the shared-data volume)
PARSE_SCRIPT = os.getenv('PARSE_SCRIPT', '/app/parse.py')
MAX_UPLOAD_BYTES = int(os.getenv('MAX_UPLOAD_BYTES', str(20 * 1024 * 1024)))


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


def data_root():
    """Data lives in a named volume; code lives in /app (Phase 0)."""
    return os.getenv('DATA_ROOT', '/srv/aftis')


def inbox_path():
    return os.getenv('INBOX_PATH', '/srv/aftis/inbox')


def uploads_path():
    """Upload landing dir. Deliberately OUTSIDE INBOX_PATH so the watchdog's
    on_created never fires on an upload and double-parses it."""
    return os.path.join(data_root(), 'uploads')


def failed_path():
    """Failure dir under the inbox bind mount so failures are visible and
    retryable from the host without docker exec."""
    return os.path.join(inbox_path(), 'failed')


def insert_transactions(transactions, file_hash=None, source_file=None):
    """Insert transactions into PostgreSQL database.

    Returns True on success OR when there is nothing to insert (empty list) --
    "empty" is not a failure, only a database error is. Returns False on failure.
    """
    if not transactions:
        return True

    conn = get_db_connection()
    if not conn:
        return False

    try:
        cursor = conn.cursor()

        insert_query = """
            INSERT INTO transactions (date, description, detail, branch, amount, transaction_type, balance, account_number, period, file_hash, source_file)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
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
                txn.get('period'),
                file_hash,
                source_file
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


def record_processed_file(file_hash, source_file, account_number, period, txn_count):
    """Record a successfully ingested file in the processed_files ledger."""
    if not file_hash:
        return False
    conn = get_db_connection()
    if not conn:
        return False
    try:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO processed_files (file_hash, source_file, account_number, period, txn_count)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (account_number, period) DO UPDATE
            SET file_hash = EXCLUDED.file_hash,
                source_file = EXCLUDED.source_file,
                txn_count = EXCLUDED.txn_count,
                ingested_at = NOW()
        """, (file_hash, source_file, account_number, period, txn_count))
        conn.commit()
        logger.info(f"Recorded processed file {source_file} (period {period}, {txn_count} txns)")
        return True
    except Exception as e:
        logger.error(f"Failed to record processed file: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()


def file_hash_exists(file_hash):
    """True if these exact bytes were already ingested (double-tap / retry)."""
    if not file_hash:
        return False
    conn = get_db_connection()
    if not conn:
        return False
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT 1 FROM processed_files WHERE file_hash = %s", (file_hash,))
        return cursor.fetchone() is not None
    except Exception as e:
        logger.error(f"Failed to check file hash: {e}")
        return False
    finally:
        conn.close()


def period_exists(account_number, period):
    """True if this (account, period) was already ingested (re-download guard)."""
    if not account_number or not period:
        return False
    conn = get_db_connection()
    if not conn:
        return False
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT 1 FROM processed_files WHERE account_number = %s AND period = %s",
            (account_number, period)
        )
        return cursor.fetchone() is not None
    except Exception as e:
        logger.error(f"Failed to check period: {e}")
        return False
    finally:
        conn.close()


def apply_migrations():
    """Apply migrations.sql at startup. Idempotent, safe to re-run."""
    migrations_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'migrations.sql')
    if not os.path.exists(migrations_path):
        logger.warning(f"Migrations file not found: {migrations_path}")
        return

    try:
        with open(migrations_path) as f:
            sql = f.read()

        # Strip comment lines, then split on statement terminators
        lines = [l for l in sql.splitlines() if not l.strip().startswith('--')]
        statements = [s.strip() for s in '\n'.join(lines).split(';') if s.strip()]

        conn = get_db_connection()
        if not conn:
            logger.error("Cannot apply migrations: database unreachable")
            return
        conn.autocommit = True
        cursor = conn.cursor()
        for stmt in statements:
            cursor.execute(stmt)
        conn.close()
        logger.info(f"Applied {len(statements)} migration statement(s)")
    except Exception as e:
        logger.error(f"Migration failed: {e}")


def run_parser(pdf_path):
    """Run parse.py on a PDF. Returns (returncode, stdout, stderr).

    tmp name is uuid-suffixed so concurrent requests (ThreadingHTTPServer)
    cannot collide on the same basename.
    """
    temp_path = os.path.join(data_root(), 'tmp', f"{uuid.uuid4().hex}.pdf")
    try:
        shutil.copy2(pdf_path, temp_path)
        result = subprocess.run(
            ['python3', PARSE_SCRIPT, temp_path],
            capture_output=True, text=True, timeout=120
        )
        return result.returncode, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return 1, '', 'parser timed out'
    except Exception as e:
        logger.error(f"Failed to run parser: {e}")
        return 1, '', str(e)
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)


def parse_and_store_pdf_path(pdf_path, file_hash=None, source_file=None, force=False):
    """Core parse + store, callable from both /parse-and-store and /upload.

    Returns a dict: success, status, plus parsed_count/account_number/period
    on success or error/reason on failure. success is True only when the parser
    exited 0, transactions were extracted, AND the insert succeeded.
    """
    returncode, stdout, stderr = run_parser(pdf_path)
    if returncode != 0:
        reason = (stderr or stdout or '').strip()
        return {
            'success': False,
            'status': 'parse_failed',
            'error': reason or f'parser exited with code {returncode}'
        }

    try:
        transactions = json.loads(stdout)
    except json.JSONDecodeError as e:
        return {'success': False, 'status': 'parse_failed', 'error': f'parser output was not valid JSON: {e}'}

    if not transactions:
        return {'success': False, 'status': 'parse_failed', 'error': 'no transactions extracted'}

    account_number = transactions[0].get('account_number')
    period = transactions[0].get('period')

    # Re-download guard: same month, different bytes
    if not force and period_exists(account_number, period):
        return {
            'success': False, 'status': 'already_ingested',
            'reason': 'period already ingested',
            'account_number': account_number, 'period': period
        }

    if not insert_transactions(transactions, file_hash, source_file):
        return {'success': False, 'status': 'db_failed', 'error': 'database storage failed'}

    if file_hash:
        record_processed_file(file_hash, source_file, account_number, period, len(transactions))

    return {
        'success': True, 'status': 'ok',
        'parsed_count': len(transactions),
        'account_number': account_number, 'period': period
    }


class AFTISHandler(BaseHTTPRequestHandler):

    def send_json(self, code, payload):
        body = json.dumps(payload, default=str).encode()
        self.send_response(code)
        self.send_header('Content-type', 'application/json')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def require_auth(self):
        """Fail closed: writes require a matching X-Auth-Token. If no token is
        configured at all, deny every write."""
        expected = os.getenv('AFTIS_UPLOAD_TOKEN', '')
        provided = self.headers.get('X-Auth-Token', '')
        if expected and provided and provided == expected:
            return True
        if not expected:
            logger.warning("AFTIS_UPLOAD_TOKEN is not configured; denying write request")
        return False

    def path_allowed(self, pdf_path):
        """A server-side pdf_path is only trusted inside the inbox or uploads dirs."""
        abs_path = os.path.abspath(pdf_path)
        allowed = [os.path.abspath(inbox_path()), os.path.abspath(uploads_path())]
        return any(abs_path.startswith(p + os.sep) for p in allowed)

    def do_GET(self):
        """Handle GET requests for file scanning"""
        path = urlparse(self.path).path
        if path == '/':
            self.index_page()
        elif path == '/scan':
            self.scan_inbox()
        elif path == '/health':
            self.health_check()
        elif path == '/db-health':
            self.db_health_check()
        elif path.startswith('/transactions'):
            self.get_transactions()
        else:
            self.send_error(404)

    def do_POST(self):
        """Handle POST requests for PDF parsing"""
        print(f"POST request to {self.path}")
        print(f"Headers: {dict(self.headers)}")
        path = urlparse(self.path).path
        if path == '/upload':
            if not self.require_auth():
                self.send_error(401, 'Unauthorized')
                return
            self.upload_pdf()
        elif path == '/parse':
            if not self.require_auth():
                self.send_error(401, 'Unauthorized')
                return
            self.parse_pdf()
        elif path == '/parse-and-store':
            if not self.require_auth():
                self.send_error(401, 'Unauthorized')
                return
            self.parse_and_store_pdf()
        elif path == '/test':
            self.test_response()
        else:
            self.send_error(404)

    def do_DELETE(self):
        """Handle DELETE requests"""
        if not self.require_auth():
            self.send_error(401, 'Unauthorized')
            return
        if self.path.startswith('/inbox/'):
            self.delete_inbox_file()
        elif self.path == '/inbox':
            self.clear_inbox()
        else:
            self.send_error(404)

    def index_page(self):
        """Minimal browser fallback: POST the raw file body to /upload."""
        html = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>AFTIS Upload</title>
<style>
  body { font-family: system-ui, sans-serif; max-width: 40rem; margin: 3rem auto; padding: 0 1rem; }
  pre { background: #f4f4f4; padding: 1rem; border-radius: 6px; overflow-x: auto; white-space: pre-wrap; }
  button { padding: .6rem 1.2rem; font-size: 1rem; cursor: pointer; }
</style>
</head>
<body>
<h1>AFTIS Upload</h1>
<p>Select a BCA eStatement PDF and upload it. The parse result is shown below.</p>
<input type="file" id="file" accept="application/pdf">
<button id="go">Upload</button>
<pre id="out">—</pre>
<script>
  const tokenKey = 'aftis_upload_token';
  function getToken() {
    let t = localStorage.getItem(tokenKey);
    if (!t) { t = prompt('AFTIS upload token:'); if (t) localStorage.setItem(tokenKey, t); }
    return t;
  }
  document.getElementById('go').addEventListener('click', async () => {
    const fileInput = document.getElementById('file');
    const out = document.getElementById('out');
    const file = fileInput.files[0];
    if (!file) { out.textContent = 'No file selected'; return; }
    const token = getToken();
    if (!token) { out.textContent = 'No token set'; return; }
    out.textContent = 'Uploading...';
    try {
      const resp = await fetch('/upload?filename=' + encodeURIComponent(file.name), {
        method: 'POST',
        headers: { 'X-Auth-Token': token },
        body: file
      });
      const text = await resp.text();
      out.textContent = resp.status + ' ' + text;
    } catch (e) {
      out.textContent = 'Error: ' + e;
    }
  });
</script>
</body>
</html>
"""
        body = html.encode('utf-8')
        self.send_response(200)
        self.send_header('Content-type', 'text/html; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def health_check(self):
        """Health check endpoint"""
        self.send_json(200, {'status': 'healthy'})

    def db_health_check(self):
        """Database health check endpoint"""
        try:
            conn = get_db_connection()
            if conn:
                cursor = conn.cursor()
                cursor.execute("SELECT 1")
                conn.close()
                self.send_json(200, {'database': 'healthy'})
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

            self.send_json(200, transactions_list)

        except Exception as e:
            self.send_error(500, f'Error retrieving transactions: {str(e)}')

    def scan_inbox(self):
        """Scan inbox folder for PDF files"""
        try:
            pdf_files = []

            if os.path.exists(inbox_path()):
                for filename in os.listdir(inbox_path()):
                    if filename.lower().endswith('.pdf'):
                        pdf_files.append(os.path.join(inbox_path(), filename))

            self.send_json(200, {'files': pdf_files})

        except Exception as e:
            self.send_error(500, str(e))

    def parse_pdf(self):
        """Parse a PDF file (no database storage)"""
        try:
            # Get content length
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            data = json.loads(post_data.decode())

            pdf_path = data.get('pdf_path')
            if not pdf_path:
                self.send_error(400, 'pdf_path required')
                return

            if not self.path_allowed(pdf_path):
                self.send_error(403, 'Access denied')
                return

            returncode, stdout, stderr = run_parser(pdf_path)

            if returncode != 0:
                self.send_error(422, (stderr or stdout or 'parser failed').strip()[:500])
                return

            try:
                transactions = json.loads(stdout)

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
                body = response_json.encode('ascii')
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.send_header('Content-Length', str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            except json.JSONDecodeError as e:
                self.send_error(500, f'JSON parse error: {str(e)}')
            except Exception as e:
                self.send_error(500, f'Processing error: {str(e)}')

        except Exception as e:
            self.send_error(500, str(e))

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

            if not self.path_allowed(pdf_path):
                self.send_error(403, 'Access denied')
                return

            result = parse_and_store_pdf_path(pdf_path)

            if result['success']:
                self.send_json(200, {
                    'success': True,
                    'parsed_count': result['parsed_count'],
                    'database_stored': True,
                    'message': f"Parsed {result['parsed_count']} transactions, stored in database"
                })
            elif result.get('status') == 'already_ingested':
                self.send_json(409, {
                    'success': False,
                    'status': 'already_ingested',
                    'reason': result.get('reason'),
                    'account_number': result.get('account_number'),
                    'period': result.get('period')
                })
            else:
                self.send_json(422, {
                    'success': False,
                    'status': result.get('status'),
                    'error': result.get('error')
                })

        except json.JSONDecodeError as e:
            self.send_error(500, f'JSON parse error: {str(e)}')
        except Exception as e:
            self.send_error(500, f'Processing error: {str(e)}')

    def upload_pdf(self):
        """Raw-body upload endpoint for the phone share sheet / browser page."""
        try:
            query = parse_qs(urlparse(self.path).query)
            filename = os.path.basename(query.get('filename', ['upload.pdf'])[0] or 'upload.pdf')
            force = query.get('force', ['0'])[0].lower() in ('1', 'true', 'yes')

            content_length = int(self.headers.get('Content-Length') or 0)
            if content_length <= 0:
                self.send_error(400, 'Empty request body')
                return
            if content_length > MAX_UPLOAD_BYTES:
                self.send_error(413, f'File too large (max {MAX_UPLOAD_BYTES} bytes)')
                return

            body = self.rfile.read(content_length)
            if not body.startswith(b'%PDF-'):
                self.send_error(400, 'Not a PDF file (missing %PDF- header)')
                return

            file_hash = hashlib.sha256(body).hexdigest()

            # Double-tap / retry-after-timeout: same bytes, already ingested.
            if not force and file_hash_exists(file_hash):
                logger.info(f"Duplicate upload ignored (hash {file_hash[:12]}...)")
                self.send_json(200, {
                    'status': 'already_ingested',
                    'reason': 'duplicate content',
                    'file_hash': file_hash
                })
                return

            os.makedirs(uploads_path(), exist_ok=True)
            upload_path = os.path.join(uploads_path(), f"{uuid.uuid4().hex}.pdf")
            with open(upload_path, 'wb') as f:
                f.write(body)

            result = parse_and_store_pdf_path(upload_path, file_hash=file_hash, source_file=filename, force=force)

            if result['success']:
                os.remove(upload_path)
                logger.info(f"Upload {filename}: parsed {result['parsed_count']} txns for {result['period']}")
                self.send_json(200, {
                    'status': 'ok',
                    'account_number': result['account_number'],
                    'period': result['period'],
                    'parsed_count': result['parsed_count'],
                    'message': f"Parsed {result['parsed_count']} transactions for {result['period']}"
                })
                return

            # Re-download of an already-ingested month: data is already stored,
            # so discard the upload rather than park it in failed/.
            if result.get('status') == 'already_ingested':
                os.remove(upload_path)
                self.send_json(409, {
                    'status': 'already_ingested',
                    'reason': result.get('reason'),
                    'account_number': result.get('account_number'),
                    'period': result.get('period')
                })
                return

            # Real failure: park the file where the host can see it, and say why.
            failed_dir = failed_path()
            os.makedirs(failed_dir, exist_ok=True)
            dest = os.path.join(failed_dir, filename)
            if os.path.exists(dest):
                base, ext = os.path.splitext(filename)
                dest = os.path.join(failed_dir, f"{base}_{int(time.time())}{ext}")
            shutil.move(upload_path, dest)
            logger.warning(f"Upload {filename} failed ({result.get('status')}); moved to {dest}")

            self.send_json(422, {
                'status': result.get('status'),
                'error': result.get('error'),
                'failed_file': os.path.basename(dest)
            })

        except Exception as e:
            self.send_error(500, str(e))

    def test_response(self):
        """Simple test endpoint"""
        try:
            self.send_json(200, {'message': 'hello', 'count': 123})
        except Exception as e:
            self.send_error(500, str(e))

    def delete_inbox_file(self):
        """Delete a specific file from inbox"""
        try:
            # Extract filename from path /inbox/filename.pdf
            filename = self.path.split('/')[-1]
            file_path = os.path.join(inbox_path(), filename)

            if not os.path.exists(file_path):
                self.send_error(404, f'File {filename} not found')
                return

            # Security check: ensure file is in inbox directory
            if not os.path.abspath(file_path).startswith(os.path.abspath(inbox_path()) + os.sep):
                self.send_error(403, 'Access denied')
                return

            os.remove(file_path)
            logger.info(f"Deleted file: {filename}")

            self.send_json(200, {
                'success': True,
                'message': f'File {filename} deleted successfully'
            })

        except OSError as e:
            self.send_error(500, f'Failed to delete file: {str(e)}')
        except Exception as e:
            self.send_error(500, str(e))

    def clear_inbox(self):
        """Delete all PDF files from inbox"""
        try:
            deleted_files = []

            if not os.path.exists(inbox_path()):
                self.send_error(404, 'Inbox directory not found')
                return

            for filename in os.listdir(inbox_path()):
                if filename.lower().endswith('.pdf'):
                    file_path = os.path.join(inbox_path(), filename)
                    try:
                        os.remove(file_path)
                        deleted_files.append(filename)
                        logger.info(f"Deleted file: {filename}")
                    except OSError as e:
                        logger.error(f"Failed to delete {filename}: {e}")

            self.send_json(200, {
                'success': True,
                'deleted_files': deleted_files,
                'count': len(deleted_files),
                'message': f'Deleted {len(deleted_files)} PDF files from inbox'
            })

        except Exception as e:
            self.send_error(500, str(e))


def main():
    # Ensure directories exist
    os.makedirs(inbox_path(), exist_ok=True)
    os.makedirs(os.path.join(data_root(), 'tmp'), exist_ok=True)
    os.makedirs(uploads_path(), exist_ok=True)
    os.makedirs(failed_path(), exist_ok=True)

    # Apply runtime migrations (idempotent)
    apply_migrations()

    port = int(os.getenv('AFTIS_PORT', '8080'))
    server = ThreadingHTTPServer(('0.0.0.0', port), AFTISHandler)
    print(f"AFTIS Parser Server starting on port {port}...")
    server.serve_forever()


if __name__ == "__main__":
    main()
