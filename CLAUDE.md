# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a Python script that processes MyBCA e-statement PDF files to extract transaction data and generate Excel reports. The script parses bank statement PDFs, extracts transaction information, calculates running balances, and outputs organized Excel files with proper formatting.

## Development Environment Setup

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
statements/          # Input folder for PDF files
main.py             # Main processing script
Pipfile             # Pipenv dependencies
{account_number}.xlsx  # Output Excel file
{account_number}_{period}.csv  # Output CSV files per period
```