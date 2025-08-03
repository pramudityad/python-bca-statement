# AFTIS (Automated Financial Transaction Ingestion System)

A minimal self-hosted pipeline that converts BCA bank statement PDFs into database rows using Docker + PostgreSQL with automated processing.

## Quick Start

### 1. Configure Environment
```bash
cp .env.example .env
# Edit .env with your PostgreSQL credentials (optional - defaults are provided)
```

### 2. Start the Services
```bash
docker-compose up -d
```

This will start:
- PostgreSQL database on port 5432
- Parser service on port 8080
- Auto-processor service (monitors inbox and processes PDFs automatically)

### 3. Automated Processing
```bash
# Simply copy PDFs to the local inbox directory
cp your-statement.pdf ./inbox/

# The auto-processor will:
# 1. Detect the new PDF file
# 2. Parse it automatically
# 3. Store transactions in the database
# 4. Delete the PDF file after successful processing
# 5. Move failed files to /srv/aftis/failed/
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
1. **Automated Processing**: Drop PDFs in `./inbox/` → automatically parsed → stored in database → files deleted
2. **PDF Parsing**: Extracts transaction data from BCA e-statement PDFs using tabula-py
3. **Database Storage**: Stores transactions in PostgreSQL with proper indexing
4. **REST API**: Provides endpoints for parsing, storing, and retrieving data
5. **File Management**: Auto-deletion of processed files, failed files moved to `failed/` directory

## Auto-Processor Configuration

Environment variables for the auto-processor service:
- `AUTO_DELETE_PDFS=true` - Delete files after successful processing (default: true)
- `PROCESS_DELAY_SECONDS=2` - Wait time before processing new files (default: 2)
- `MAX_RETRIES=3` - Number of retry attempts for failed processing (default: 3)

## API Endpoints

- `GET /health` - Service health check
- `GET /db-health` - Database connectivity check
- `GET /scan` - List PDF files in inbox
- `POST /parse` - Parse PDF and return JSON (no database storage)
- `POST /parse-and-store` - Parse PDF and store in database
- `DELETE /inbox/{filename}` - Delete a specific file from inbox
- `DELETE /inbox` - Delete all PDF files from inbox
- `GET /transactions` - Retrieve transactions with optional filters
  - Query parameters: `limit`, `account`, `period`

## File Structure
```
├── docker-compose.yml     # PostgreSQL + parser + auto-processor services
├── .env                   # PostgreSQL credentials
├── parse.py              # PDF → JSON parser
├── server.py             # HTTP API server with DELETE endpoints
├── auto-processor.py     # Automated PDF processing service
├── schema.sql            # PostgreSQL table DDL
├── Dockerfile            # Service containers
├── main.py               # Original standalone script
├── inbox/                # Drop PDFs here (auto-mounted volume)
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

- **No transactions extracted**: Check PDF format matches BCA e-statement layout
- **Database connection fails**: Check PostgreSQL container status with `docker-compose logs postgres`
- **Parser errors**: Check container logs with `docker-compose logs parser`
- **Auto-processor issues**: Check auto-processor logs with `docker-compose logs auto-processor`
- **Files not being processed**: Ensure auto-processor service is running and check logs
- **Port conflicts**: Modify ports in docker-compose.yml if needed
- **DELETE endpoints not working**: Rebuild containers with `docker-compose build` if using older images

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