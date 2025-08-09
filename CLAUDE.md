# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a Python script that processes MyBCA e-statement PDF files to extract transaction data and generate Excel reports. The script parses bank statement PDFs, extracts transaction information, calculates running balances, and outputs organized Excel files with proper formatting.

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
- PDF files must be MyBCA e-statements placed in `statements/` folder
- PDFs should contain standard MyBCA format with consistent table structure
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
inbox/               # Input folder for PDF files (Docker auto-processing)
statements/          # Input folder for PDF files (local processing)
main.py             # Main processing script
Pipfile             # Pipenv dependencies
docker-compose.yml   # Docker services configuration
start.sh            # Enhanced startup script with port conflict handling
check-ports.sh      # Port conflict detection and resolution
.env                 # Environment configuration (create from .env.example)
{account_number}.xlsx  # Output Excel file
{account_number}_{period}.csv  # Output CSV files per period
```

## Auto-Processing System

The Docker setup includes an auto-processing system that:

- Monitors `inbox/` folder for new PDF files
- Automatically processes PDFs when detected
- Extracts transactions and stores in PostgreSQL database
- Provides web interface for viewing results
- Includes periodic scanning (every 60s) to catch missed files
- Handles file conflicts and processing retries

### Auto-Processor Features

- **File Monitoring**: Real-time detection of new PDF files
- **Retry Logic**: Configurable retry attempts for failed processing
- **Periodic Scanning**: Background scanning for missed files (configurable interval)
- **Error Handling**: Failed files moved to `failed/` directory
- **Logging**: Comprehensive logging of processing activities

Configuration via environment variables:
- `AUTO_DELETE_PDFS`: Delete successfully processed files (default: true)
- `PROCESS_DELAY_SECONDS`: Wait time before processing new files (default: 2)
- `MAX_RETRIES`: Maximum retry attempts for failed files (default: 3)
- `SCAN_INTERVAL_SECONDS`: Periodic scan interval for missed files (default: 60)