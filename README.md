# AFTIS (Automated Financial Transaction Ingestion System)

A minimal self-hosted pipeline that converts BCA bank statement PDFs into database rows using Docker + PostgreSQL with automated processing.

Two ingestion paths exist:
- **Share-sheet upload (primary)** — one tap from the myBCA Android app via the share sheet → Tailscale → `POST /upload`, works from anywhere, with a success/failure toast as real confirmation.
- **Filesystem inbox (fallback)** — drop PDFs in a watched directory (Syncthing, Dropbox, NAS, …) and the auto-processor ingests them.

## Quick Start

### 🚀 Automated Startup (Recommended)
```bash
# One-command startup with automatic port conflict resolution
./start.sh
```

### 🔧 Manual Setup
```bash
# 1. Check for port conflicts
./check-ports.sh

# 2. Configure environment (optional)
cp .env.example .env
# Edit .env with custom ports/credentials if needed
# AFTIS_UPLOAD_TOKEN is required for the share-sheet path

# 3. Start services
docker-compose up -d
```

This will start:
- PostgreSQL database (no host port; only reachable inside the Docker network)
- Parser service with web interface (localhost only, exposed to the tailnet via `tailscale serve`)
- Auto-processor service (monitors inbox and processes PDFs automatically)

## Share-Sheet Upload From Your Phone (Primary Path)

Statements live only in the myBCA Android app until you push them — this path replaces Syncthing as the one-tap, works-from-anywhere handoff.

### 1. Set up Tailscale
```bash
# On the server: install tailscale, then expose the parser on the tailnet
sudo tailscale up
tailscale serve --bg 8080
# Note the resulting https://<host>.ts.net URL (it gets a real TLS cert)
```
Install the Tailscale app on your Android phone and sign in with the same account so both devices are on one tailnet.

### 2. Configure the upload token
```bash
openssl rand -hex 32   # generate a secret
# add it to .env:
# AFTIS_UPLOAD_TOKEN=<the secret>
./start.sh
```

### 3. Install HTTP Shortcuts and create the shortcut
Install the free/open-source [HTTP Shortcuts](https://play.google.com/store/apps/details?id=ch.rmy.android.http_shortcuts) app and create a shortcut:

- **Method**: `POST`
- **URL**: `https://<host>.ts.net/upload?filename={{file_name}}`
- **Request body**: *File* — pick the share-sheet payload
- **Header**: `X-Auth-Token: <the secret>`
- Enable **share target** (so it appears in the Android share sheet)
- Enable **response display** so the parse result shows as a toast

### 4. Use it
In the myBCA app, long-press a statement → **Share** → **AFTIS**. Expect:
- ✅ success toast with the period and transaction count
- ♻️ same PDF shared again → `already_ingested` (no duplicate rows)
- ⛔ a non-statement PDF → red failure toast; the file lands in `{INBOX_HOST_PATH}/failed/` on the host

### Retiring Syncthing
Keep the Syncthing inbox fallback for a month or two until the upload path has proven itself, then:
1. Uninstall/disable Syncthing on the phone.
2. Stop syncing the inbox directory (or leave `INBOX_HOST_PATH` pointing at it — nothing else changes).
3. The watchdog inbox path remains a supported fallback indefinitely; it needs no phone-side daemon.

### Browser fallback
The web interface (`http://localhost:8080/` or `https://<host>.ts.net/`) serves a tiny upload page that POSTs the raw file body to the same endpoint — same dedup, same failure handling.

### 3. Automated Processing

#### Default Configuration
```bash
# Simply copy PDFs to the local inbox directory
cp your-statement.pdf ./inbox/

# The auto-processor will:
# 1. Detect the new PDF file
# 2. Parse it automatically
# 3. Store transactions in the database
# 4. Delete the PDF file after successful processing
# 5. Move failed files to {INBOX_HOST_PATH}/failed/ (host-visible)
```

#### Custom Inbox Directory (e.g., Syncthing)
```bash
# Configure for external directory like /var/syncthing/eStatement
echo "INBOX_HOST_PATH=/var/syncthing/eStatement" >> .env
./start.sh

# Now the system will monitor your custom directory instead of ./inbox/
# Perfect for Syncthing, Dropbox, or any shared folder setup
```

### 4. Manual API Usage (Optional)
```bash
# Test parser service health
curl http://localhost:8080/health

# Test database connection
curl http://localhost:8080/db-health

# Scan for PDFs in inbox
curl http://localhost:8080/scan

# Parse and store a specific PDF
curl -X POST http://localhost:8080/parse-and-store \
  -H "Content-Type: application/json" \
  -d '{"pdf_path": "/srv/aftis/inbox/your-statement.pdf"}'

# Delete a specific file from inbox
curl -X DELETE http://localhost:8080/inbox/filename.pdf

# Clear all PDFs from inbox
curl -X DELETE http://localhost:8080/inbox

# Retrieve stored transactions
curl "http://localhost:8080/transactions?limit=10"

# Check logs
docker-compose logs -f
```

## How It Works

The system provides:
1. **Automated Processing**: Drop PDFs in configurable inbox directory → automatically parsed → stored in database → files deleted
2. **Configurable Inbox**: Use any directory (local, network shares, Syncthing, etc.) as input folder
3. **PDF Parsing**: Extracts transaction data from BCA e-statement PDFs using tabula-py
4. **Database Storage**: Stores transactions in PostgreSQL with proper indexing
5. **REST API**: Provides endpoints for parsing, storing, and retrieving data
6. **File Management**: Auto-deletion of processed files, failed files moved to `failed/` directory

## Configuration

### Port Configuration
- `AFTIS_PORT=8080` - Parser service web interface port
- `POSTGRES_PORT=5432` - PostgreSQL database port

### Auto-Processor Configuration
- `INBOX_HOST_PATH=./inbox` - Host directory to monitor for PDF files (default: ./inbox)
- `INBOX_PATH=/srv/aftis/inbox` - Container internal path (usually no need to change)
- `AUTO_DELETE_PDFS=true` - Delete files after successful processing (default: true)
- `PROCESS_DELAY_SECONDS=2` - Wait time before processing new files (default: 2)
- `MAX_RETRIES=3` - Number of retry attempts for failed processing (default: 3)
- `SCAN_INTERVAL_SECONDS=60` - Periodic scan interval for missed files (default: 60)

### Upload Configuration
- `AFTIS_UPLOAD_TOKEN=<secret>` - Shared secret required on every write endpoint (`/upload`, `/parse`, `/parse-and-store`, both `DELETE`s). The phone shortcut and browser page send it as the `X-Auth-Token` header.
- Failed uploads are parked in `{INBOX_HOST_PATH}/failed/` so they are visible and retryable from the host.

### Inbox Directory Examples
```bash
# Default local directory
INBOX_HOST_PATH=./inbox

# Syncthing directory  
INBOX_HOST_PATH=/var/syncthing/eStatement

# Network share
INBOX_HOST_PATH=/mnt/nas/bank-statements

# Dropbox directory
INBOX_HOST_PATH=/home/user/Dropbox/BCA-Statements
```

### Port Conflict Handling

**If ports are already in use**, the system provides multiple solutions:

1. **Automatic Resolution**: Use `./start.sh` - automatically detects conflicts and uses available ports
2. **Manual Port Check**: Use `./check-ports.sh` - shows conflicts and suggests alternative ports  
3. **Custom Configuration**: Set custom ports in `.env` file:
   ```bash
   echo "AFTIS_PORT=8081" >> .env
   echo "POSTGRES_PORT=5433" >> .env
   docker-compose up -d
   ```

## API Endpoints

- `GET /` - Minimal browser upload page (raw-body `fetch` to `/upload`)
- `GET /health` - Service health check
- `GET /db-health` - Database connectivity check
- `GET /scan` - List PDF files in inbox
- `POST /upload?filename=…&force=0` - Raw-body PDF upload (share sheet / browser). Dedupes by SHA-256; `force=1` bypasses dedup for deliberate re-import. Returns 200 on success, `200 already_ingested` for a duplicate file, `409 already_ingested` for an already-ingested month, 422 with the reason on parse/storage failure.
- `POST /parse` - Parse PDF and return JSON (no database storage)
- `POST /parse-and-store` - Parse PDF and store in database
- `DELETE /inbox/{filename}` - Delete a specific file from inbox
- `DELETE /inbox` - Delete all PDF files from inbox
- `GET /transactions` - Retrieve transactions with optional filters
  - Query parameters: `limit`, `account`, `period`

All write endpoints require the `X-Auth-Token` header matching `AFTIS_UPLOAD_TOKEN`. The parser is bound to `127.0.0.1` on the host and exposed to the tailnet only via `tailscale serve`; PostgreSQL has no host port at all.

## File Structure
```
├── docker-compose.yml     # PostgreSQL + parser + auto-processor services  
├── .env                   # Environment configuration (copy from .env.example)
├── .env.example          # Environment template with defaults
├── start.sh              # Enhanced startup script with port conflict handling
├── check-ports.sh        # Port conflict detection and resolution utility
├── parse.py              # PDF → JSON parser
├── server.py             # HTTP API server (upload + parse endpoints)
├── auto-processor.py     # Automated PDF processing service (enhanced)
├── schema.sql            # PostgreSQL table DDL (fresh databases)
├── migrations.sql        # Idempotent runtime migrations (existing databases)
├── Dockerfile            # Service containers
├── main.py               # Original standalone script
├── inbox/                # Default PDF directory (configurable via INBOX_HOST_PATH)
└── tmp/                  # Processing workspace
```

## Manual Testing

Test the parser directly:
```bash
# Using the original standalone script
python main.py

# Using the API parser
python parse.py statements/your-statement.pdf
```

## Database Access

Connect to PostgreSQL directly:
```bash
# Using docker exec
docker exec -it aftis-postgres psql -U aftis_user -d aftis

# Using local client (if installed)
psql postgresql://aftis_user:aftis_password@localhost:5432/aftis
```

## Troubleshooting

### Common Issues

- **Port conflicts**: Use `./start.sh` for automatic resolution or `./check-ports.sh` to diagnose
- **No transactions extracted**: Check PDF format matches BCA e-statement layout
- **Files not auto-processing**: Check auto-processor logs and ensure container is running
- **Database connection fails**: Verify PostgreSQL container health

### Detailed Diagnostics

```bash
# Check service status
docker-compose ps

# View logs
docker-compose logs -f                    # All services
docker-compose logs -f auto-processor     # Auto-processor only
docker-compose logs -f parser             # Parser service only
docker-compose logs -f postgres           # Database only

# Check port availability
./check-ports.sh

# Test API endpoints
curl http://localhost:8080/health         # Service health
curl http://localhost:8080/db-health      # Database connectivity
curl http://localhost:8080/scan           # Inbox contents

# Restart services
docker-compose restart
docker-compose down && docker-compose up -d

# Rebuild containers (after code changes)
docker-compose build --no-cache
```

### Auto-Processor Issues

- **Files not detected**: Check if containers have access to your configured inbox directory (`INBOX_HOST_PATH`)
- **Custom directory not working**: Ensure directory exists and has proper permissions (`chmod 755`)
- **Processing failures**: Check for PDF format compatibility and container logs; failed files land in `{INBOX_HOST_PATH}/failed/`
- **Missed files**: Auto-processor now includes periodic scanning (every 60s by default)
- **Port conflicts in internal services**: Auto-processor will retry with exponential backoff

### Directory Permission Issues
```bash
# Ensure your custom inbox directory is accessible
sudo mkdir -p /your/custom/path
sudo chown $USER:$USER /your/custom/path
chmod 755 /your/custom/path

# For Syncthing directories
sudo chown $USER:$USER /var/syncthing/eStatement
chmod 755 /var/syncthing/eStatement
```

## Dependencies

The services require:
- `tabula-py` (PDF table extraction)
- `pandas` (data processing)
- `numpy` (numerical operations)
- `psycopg2-binary` (PostgreSQL connectivity)
- `requests` (HTTP client for auto-processor)
- `watchdog` (file system monitoring)

All dependencies are automatically installed in Docker containers.

Manual installation: `pip install tabula-py pandas numpy psycopg2-binary requests watchdog`