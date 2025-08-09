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

## Architecture

The codebase is a single-file Python script (`main.py`) with the following key components:

### Core Functions
- `union_source()`: Consolidates PDF table data and extracts amount/transaction type
- `extract_transactions()`: Groups related transaction rows and creates transaction records
- `calculate_balance()`: Computes running balance based on debit/credit transactions
- `save_to_excel()`: Outputs data to Excel with Indonesian Rupiah formatting
- `reorder_sheets()`: Sorts Excel sheets chronologically by period

### Data Flow
1. PDF files are read from `statements/` folder using tabula-py
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
statements/          # Input folder for PDF files (local processing)
main.py             # Main processing script
Pipfile             # Pipenv dependencies
docker-compose.yml   # Docker services configuration
start.sh            # Enhanced startup script with port conflict handling
check-ports.sh      # Port conflict detection and resolution
.env                 # Environment configuration (create from .env.example)
syncthing-example.md # Example configuration for Syncthing directories
{account_number}.xlsx  # Output Excel file
{account_number}_{period}.csv  # Output CSV files per period
```

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

### Auto-Processor Features

- **File Monitoring**: Real-time detection of new PDF files
- **Configurable Inbox**: Custom input directory via `INBOX_PATH` environment variable
- **Retry Logic**: Configurable retry attempts for failed processing
- **Periodic Scanning**: Background scanning for missed files (configurable interval)
- **Error Handling**: Failed files moved to `failed/` directory
- **Logging**: Comprehensive logging of processing activities

Configuration via environment variables:
- `INBOX_PATH`: Input directory for PDF files (default: /srv/aftis/inbox)
- `INBOX_HOST_PATH`: Host directory to mount as inbox (default: ./inbox)
- `AUTO_DELETE_PDFS`: Delete successfully processed files (default: true)
- `PROCESS_DELAY_SECONDS`: Wait time before processing new files (default: 2)
- `MAX_RETRIES`: Maximum retry attempts for failed files (default: 3)
- `SCAN_INTERVAL_SECONDS`: Periodic scan interval for missed files (default: 60)