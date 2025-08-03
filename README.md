# AFTIS (Automated Financial Transaction Ingestion System)

A minimal self-hosted pipeline that converts BCA bank statement PDFs into database rows using Docker + PostgreSQL.

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

### 3. Test the System
```bash
# Test parser service health
curl http://localhost:8080/health

# Test database connection
curl http://localhost:8080/db-health

# Drop a BCA e-statement PDF into the inbox volume
docker cp your-statement.pdf aftis-parser:/srv/aftis/inbox/

# Test scanning for PDFs
curl http://localhost:8080/scan

# Parse and store a PDF in database
curl -X POST http://localhost:8080/parse-and-store \
  -H "Content-Type: application/json" \
  -d '{"pdf_path": "/srv/aftis/inbox/your-statement.pdf"}'

# Retrieve stored transactions
curl "http://localhost:8080/transactions?limit=10"

# Check logs
docker-compose logs -f
```

## How It Works

The system provides:
1. **PDF Parsing**: Extracts transaction data from BCA e-statement PDFs
2. **Database Storage**: Stores transactions in PostgreSQL with proper indexing
3. **REST API**: Provides endpoints for parsing, storing, and retrieving data
4. **Data Export**: Maintains compatibility with Excel/CSV output

## API Endpoints

- `GET /health` - Service health check
- `GET /db-health` - Database connectivity check
- `GET /scan` - List PDF files in inbox
- `POST /parse` - Parse PDF and return JSON (no database storage)
- `POST /parse-and-store` - Parse PDF and store in database
- `GET /transactions` - Retrieve transactions with optional filters
  - Query parameters: `limit`, `account`, `period`

## File Structure
```
├── docker-compose.yml     # PostgreSQL + parser services
├── .env                   # PostgreSQL credentials
├── parse.py              # PDF → JSON parser
├── server.py             # HTTP API server
├── schema.sql            # PostgreSQL table DDL
├── Dockerfile            # Parser service container
├── main.py               # Original standalone script
├── inbox/                # Drop PDFs here (in container)
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
- **Port conflicts**: Modify ports in docker-compose.yml if needed

## Dependencies

The parser requires:
- `tabula-py` (PDF table extraction)
- `pandas` (data processing)
- `numpy` (numerical operations)
- `psycopg2-binary` (PostgreSQL connectivity)

Install manually: `pip install tabula-py pandas numpy psycopg2-binary`