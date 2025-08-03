# AFTIS (Automated Financial Transaction Ingestion System)

A minimal self-hosted pipeline that converts BCA bank statement PDFs into database rows using n8n + Docker + Supabase.

## Quick Start

### 1. Setup Supabase Database
```bash
# Run this in your Supabase SQL editor
cat schema.sql | # copy and paste into Supabase
```

### 2. Configure Environment
```bash
cp .env.example .env
# Edit .env with your Supabase credentials
```

### 3. Start the Pipeline
```bash
docker-compose up -d
```

### 4. Import n8n Workflow
1. Open http://localhost:5678 (admin/admin123)
2. Go to Workflows → Import from File
3. Upload `aftis-workflow.json`
4. Activate the workflow

### 5. Test the System
```bash
# Test parser service directly
curl http://localhost:8080/health

# Drop a BCA e-statement PDF into the inbox volume
docker cp your-statement.pdf aftis-parser:/srv/aftis/inbox/

# Test scanning
curl http://localhost:8080/scan

# Check logs to see processing
docker-compose logs -f

# Verify data in Supabase dashboard
```

## How It Works

Every night at 02:00, the system:
1. Scans `inbox/` for `*.pdf` files
2. Copies each file to `tmp/` for processing
3. Runs `parse.py` to extract transactions as JSON
4. Bulk inserts the data into Supabase
5. Cleans up temporary files

## File Structure
```
├── docker-compose.yml     # n8n container stack
├── .env                   # supabase credentials
├── parse.py              # pdf → json parser
├── schema.sql            # database table DDL
├── aftis-workflow.json   # n8n workflow definition
├── inbox/                # drop PDFs here
├── tmp/                  # processing workspace
└── n8n_data/            # persistent n8n storage
```

## Manual Testing

Test the parser directly:
```bash
python parse.py inbox/your-statement.pdf
```

## Troubleshooting

- **No transactions extracted**: Check PDF format matches BCA e-statement layout
- **Database insert fails**: Verify Supabase credentials in `.env`
- **n8n workflow errors**: Check container logs with `docker-compose logs n8n`

## Dependencies

The parser requires:
- `tabula-py` (PDF table extraction)
- `pandas` (data processing)
- `numpy` (numerical operations)

Install manually: `pip install tabula-py pandas numpy`