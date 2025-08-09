# AFTIS (Automated Financial Transaction Ingestion System)

A minimal self-hosted pipeline that converts BCA bank statement PDFs into database rows using Docker + PostgreSQL with automated processing.

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

# 3. Start services
docker-compose up -d
```

This will start:
- PostgreSQL database (default port 5432, configurable)
- Parser service with web interface (default port 8080, configurable)
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

## Configuration

### Port Configuration
- `AFTIS_PORT=8080` - Parser service web interface port
- `POSTGRES_PORT=5432` - PostgreSQL database port

### Auto-Processor Configuration
- `AUTO_DELETE_PDFS=true` - Delete files after successful processing (default: true)
- `PROCESS_DELAY_SECONDS=2` - Wait time before processing new files (default: 2)
- `MAX_RETRIES=3` - Number of retry attempts for failed processing (default: 3)
- `SCAN_INTERVAL_SECONDS=60` - Periodic scan interval for missed files (default: 60)

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
├── .env                   # Environment configuration (copy from .env.example)
├── .env.example          # Environment template with defaults
├── start.sh              # Enhanced startup script with port conflict handling
├── check-ports.sh        # Port conflict detection and resolution utility
├── parse.py              # PDF → JSON parser
├── server.py             # HTTP API server with DELETE endpoints
├── auto-processor.py     # Automated PDF processing service (enhanced)
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

- **Files not detected**: Check if containers have access to `./inbox/` directory
- **Processing failures**: Check for PDF format compatibility and container logs
- **Missed files**: Auto-processor now includes periodic scanning (every 60s by default)
- **Port conflicts in internal services**: Auto-processor will retry with exponential backoff

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