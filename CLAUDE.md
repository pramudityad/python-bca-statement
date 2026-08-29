# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a Python script that processes eStatement e-statement PDF files to extract transaction data and generate Excel reports. The script parses bank statement PDFs, extracts transaction information, calculates running balances, and outputs organized Excel files with proper formatting.

## Development Environment Setup

### Docker Setup (Recommended)

The project includes a Dockerized auto-processing system with web interface:

```bash
# Quick start with automatic port conflict resolution
./start.sh

# Manual startup (check ports first)
./check-ports.sh
docker-compose up -d

# Stop services
docker-compose down
```

### Local Development Setup

Use pipenv for dependency management:

```bash
pip install pipenv
pipenv shell
pipenv install
```

Run the main script:
```bash
python main.py
```

## Port Configuration

The Docker services use configurable ports via environment variables:

- `AFTIS_PORT`: Web interface port (default: 8080)
- `POSTGRES_PORT`: Database port (default: 5432)

### Handling Port Conflicts

If ports are already in use:

1. **Automatic Resolution**: Use `./start.sh` for automatic port conflict handling
2. **Manual Configuration**: Set custom ports in `.env` file:
   ```bash
   echo "AFTIS_PORT=8081" >> .env
   echo "POSTGRES_PORT=5433" >> .env
   ```
3. **Check Conflicts**: Use `./check-ports.sh` to detect and resolve conflicts

## Share-Sheet Upload (Primary Path)

The primary ingestion path is a one-tap Android share-sheet upload that replaces Syncthing as the everyday handoff:

```
myBCA → Downloads → long-press → Share → "AFTIS" (HTTP Shortcuts app)
      → POST https://<host>.ts.net/upload?filename=… over Tailscale
      → server.py: hash → dedup check → parse → insert → JSON toast
```

Key facts for developers:

- **Transport**: The phone (HTTP Shortcuts, `ch.rmy.android.http_shortcuts`) POSTs the PDF as the **raw request body**. No multipart parsing anywhere.
- **Auth**: Every write endpoint (`/upload`, `/parse`, `/parse-and-store`, both `DELETE`s) requires `X-Auth-Token` matching `AFTIS_UPLOAD_TOKEN`. Fails closed: if the token is unset, writes are denied.
- **Dedup ledger**: `processed_files` table. `file_hash` (SHA-256) catches double-taps/retries; `UNIQUE(account_number, period)` catches a myBCA re-download of the same month with different bytes. `?force=1` bypasses both (deliberate re-import).
- **Uploads land in `/srv/aftis/uploads/`**, deliberately outside `INBOX_PATH`, so the watchdog never double-parses an upload.
- **Failed uploads** are moved to `{INBOX_PATH}/failed/` (host-visible via the bind mount) and the endpoint returns a 4xx/5xx with the reason.
- **`GET /`** serves a minimal browser upload page that POSTs the same raw-body request via `fetch`.
- **`server.py` is stdlib-only** (`ThreadingHTTPServer`). Code lives in `/app` (Dockerfile `WORKDIR /app`); `/srv/aftis` is data only.
- Migrations: `server.py` applies `migrations.sql` idempotently at startup (needed because `schema.sql` only runs on a fresh `postgres_data` volume).

## Architecture

The codebase has two layers:

### Standalone script (`main.py`)

### Core Functions
- `union_source()`: Consolidates PDF table data and extracts amount/transaction type
- `extract_transactions()`: Groups related transaction rows and creates transaction records
- `calculate_balance()`: Computes running balance based on debit/credit transactions
- `save_to_excel()`: Outputs data to Excel with Indonesian Rupiah formatting
- `reorder_sheets()`: Sorts Excel sheets chronologically by period

### Docker pipeline (`parse.py` → `server.py` → PostgreSQL)
- `parse.py` (invoked as a subprocess by `server.py`): tabula-py extraction, header (period/account) from fixed PDF coordinates, transaction grouping. Exits non-zero when nothing is extracted — strict failure semantics, never a silent success.
- `server.py`: stdlib HTTP server (`ThreadingHTTPServer`) exposing `/upload`, `/parse`, `/parse-and-store`, `/transactions`, etc. Core parse+store logic lives in `parse_and_store_pdf_path()`, shared by the HTTP handlers and the upload path.
- `auto-processor.py`: watchdog on `INBOX_PATH` (plus 60s rescan), calls `/parse-and-store`, deletes on success, parks failures in `{INBOX_PATH}/failed/`.

### Data Flow
1. PDF files are read from `statements/` folder using tabula-py (standalone) or arrive via upload/Syncthing inbox (Docker)
2. Header information (period, account number) extracted from specific PDF coordinates
3. Transaction tables parsed from defined PDF areas with column boundaries
4. Raw data cleaned and processed into structured transactions
5. Balance calculations performed based on initial balance and transaction types
6. Output saved as both Excel (with sheets per period) and CSV files

### Input Requirements
- PDF files must be eStatement e-statements placed in `statements/` folder
- PDFs should contain standard eStatement format with consistent table structure
- Initial balance extracted from "SALDO AWAL" row in the data

### Output Format
- Excel file named by account number (e.g., `6815134099.xlsx`)
- Each statement period becomes a separate Excel sheet
- Sheets ordered chronologically (newest first)
- Currency columns formatted as Indonesian Rupiah
- CSV files generated per period for additional processing

## Dependencies

Key libraries:
- `tabula-py`: PDF table extraction
- `pandas`: Data manipulation and analysis
- `openpyxl`: Excel file handling and formatting
- `tqdm`: Progress bar for file processing
- `numpy`: Numerical operations

## File Structure Expectations

```
inbox/               # Default input folder for PDF files (configurable via INBOX_HOST_PATH)
inbox/failed/        # Host-visible failure dir (auto-processor + failed uploads)
statements/          # Input folder for PDF files (local processing)
main.py             # Main processing script (standalone)
parse.py            # PDF → JSON parser (Docker pipeline subprocess)
server.py           # HTTP API server (upload + parse endpoints)
auto-processor.py   # Watchdog inbox processor
Pipfile             # Pipenv dependencies
docker-compose.yml   # Docker services configuration
Dockerfile          # Container image (code at /app, data at /srv/aftis)
schema.sql          # PostgreSQL DDL (fresh databases only)
migrations.sql      # Idempotent runtime migrations (applied by server.py)
start.sh            # Enhanced startup script with port conflict handling
check-ports.sh      # Port conflict detection and resolution
.env                 # Environment configuration (create from .env.example)
syncthing-example.md # Example configuration for Syncthing directories
{account_number}.xlsx  # Output Excel file
{account_number}_{period}.csv  # Output CSV files per period
```

> Note: `watch-pdfs.py` and `copy-pdfs.sh` (pre-bind-mount `docker cp` ingestion) were removed in favor of the bind-mounted inbox; the share-sheet upload is the primary path.

## Configurable Inbox Directory

The system supports monitoring any directory for PDF files, not just the default `./inbox/` folder. This is particularly useful for:

- **Syncthing Integration**: Monitor synchronized directories like `/var/syncthing/myBCA/`
- **Network Shares**: Process files from mounted NAS or shared drives
- **Cloud Storage**: Monitor Dropbox, Google Drive, or OneDrive folders
- **Automated Workflows**: Integration with other tools that drop files in specific locations

### Configuration Options

Set these environment variables in your `.env` file:

- `INBOX_HOST_PATH`: The directory on your host system to monitor (default: `./inbox`)
- `INBOX_PATH`: The path inside Docker containers (default: `/srv/aftis/inbox`, rarely needs changing)

### Example Configurations

1. **Syncthing Directory**:
   ```bash
   INBOX_HOST_PATH=/var/syncthing/myBCA
   ```

2. **Network Share**:
   ```bash
   INBOX_HOST_PATH=/mnt/nas/bank-statements
   ```

3. **Cloud Storage**:
   ```bash
   INBOX_HOST_PATH=/home/user/Dropbox/BCA-Statements
   ```

### Setup Steps for Custom Directory

1. Create and configure your `.env` file:
   ```bash
   cp .env.example .env
   echo "INBOX_HOST_PATH=/your/custom/path" >> .env
   ```

2. Ensure directory permissions:
   ```bash
   sudo mkdir -p /your/custom/path
   sudo chown $USER:$USER /your/custom/path
   chmod 755 /your/custom/path
   ```

3. Start the system:
   ```bash
   ./start.sh
   ```

The startup script will display the configured inbox path, confirming your custom directory is being monitored.

## Auto-Processing System

The Docker setup includes an auto-processing system that:

- Monitors configurable inbox directory for new PDF files (supports any local or network path)
- Automatically processes PDFs when detected via file system events
- Extracts transactions and stores in PostgreSQL database
- Provides web interface for viewing results
- Includes periodic scanning (every 60s) to catch missed files
- Handles file conflicts and processing retries
- Works seamlessly with external sync tools (Syncthing, Dropbox, rsync, etc.)

The primary path is the **share-sheet upload** (see the Share-Sheet Upload section) — the inbox/watchdog remains as a fallback that needs no phone-side daemon.

### Auto-Processor Features

- **File Monitoring**: Real-time detection of new PDF files
- **Configurable Inbox**: Custom input directory via `INBOX_PATH` environment variable
- **Retry Logic**: Configurable retry attempts for failed processing
- **Periodic Scanning**: Background scanning for missed files (configurable interval)
- **Error Handling**: Failed files moved to `{INBOX_PATH}/failed/` directory (host-visible)
- **Logging**: Comprehensive logging of processing activities

Configuration via environment variables:
- `INBOX_PATH`: Input directory for PDF files (default: /srv/aftis/inbox)
- `INBOX_HOST_PATH`: Host directory to mount as inbox (default: ./inbox)
- `AUTO_DELETE_PDFS`: Delete successfully processed files (default: true)
- `PROCESS_DELAY_SECONDS`: Wait time before processing new files (default: 2)
- `MAX_RETRIES`: Maximum retry attempts for failed files (default: 3)
- `SCAN_INTERVAL_SECONDS`: Periodic scan interval for missed files (default: 60)
- `AFTIS_UPLOAD_TOKEN`: Shared secret for write endpoints; the auto-processor sends it as `X-Auth-Token` to `/parse-and-store`