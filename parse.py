#!/usr/bin/env python3
"""
AFTIS PDF Parser - Extracts BCA e-statement transactions to JSON
Usage: python parse.py <pdf_file_path>
"""

import sys
import json
from tabula import read_pdf
import pandas as pd
import numpy as np
from datetime import datetime


def clean_numeric_columns(dataframe, columns):
    for column in columns:
        dataframe[column] = dataframe[column].str.replace(',', '')
        dataframe[column] = pd.to_numeric(dataframe[column], errors='coerce')
        dataframe[column] = dataframe[column].astype('float')
    return dataframe


def union_source(dataframes):
    dfs = []
    for temp_df in dataframes:
        # Split DB/CR and amount into separate columns
        temp_df[['amount', 'type']] = temp_df[4].str.extract(r'([\d,]+(?:\.\d+)?)\s*(DB|CR)?')
        temp_df = temp_df.drop(temp_df.columns[4], axis=1)
        
        if len(temp_df.columns) == 7:
            temp_df.columns = ['date', 'desc', 'detail', 'branch', 'balance', 'amount', 'type']
            temp_df = temp_df[['date', 'desc', 'detail', 'branch', 'amount', 'type', 'balance']]
            dfs.append(temp_df)
    
    df = pd.concat(dfs, ignore_index=True)
    return df.fillna(value=np.nan)


def extract_transactions(dataframe):
    transactions = []
    details = []
    descs = []
    temp = {}
    
    # Add shifted columns for comparison
    dataframe['prev_amount'] = dataframe['amount'].shift(1)
    
    for index, row in dataframe.iterrows():
        # Skip certain types
        if row['desc'] in ['DR KOREKSI BUNGA', 'BUNGA', 'SALDO AWAL']:
            if row['desc'] in ['DR KOREKSI BUNGA', 'BUNGA'] and temp:
                transaction = {
                    "date": temp['date'],
                    "description": ' | '.join(descs) if descs else '',
                    "detail": ' | '.join(details) if details else '',
                    "branch": temp['branch'],
                    "amount": temp['amount'],
                    "transaction_type": temp['transaction_type'] if temp['transaction_type'] == 'DB' else 'CR',
                    "balance": temp['balance']
                }
                transactions.append(transaction)
                break
            continue
        
        # New transaction detected
        if (not pd.isna(row['amount'])) and ((pd.isna(row['prev_amount'])) or row['amount'] != row['prev_amount']):
            # Save previous transaction
            if temp:
                transaction = {
                    "date": temp['date'],
                    "description": ' | '.join(descs) if descs else '',
                    "detail": ' | '.join(details) if details else '',
                    "branch": temp['branch'],
                    "amount": temp['amount'],
                    "transaction_type": temp['transaction_type'] if temp['transaction_type'] == 'DB' else 'CR',
                    "balance": temp['balance']
                }
                transactions.append(transaction)
                details = []
                descs = []
                temp = {}
            
            temp = {
                'date': row['date'],
                'branch': row['branch'],
                'amount': row['amount'],
                'transaction_type': row['type'],
                'balance': row['balance']
            }
        
        # Collect descriptions and details
        if not pd.isna(row['desc']):
            descs.append(row['desc'])
        if not pd.isna(row['detail']):
            details.append(row['detail'])
    
    return transactions


def parse_pdf(pdf_path):
    try:
        # Extract header information
        header_df = read_pdf(
            pdf_path, 
            area=(70, 315, 141, 548), 
            pages='1', 
            pandas_options={'header': None, 'dtype': str}, 
            force_subprocess=True
        )[0]
        
        periode = header_df.loc[header_df[0] == 'PERIODE', 2].values[0]
        periode = ' '.join(reversed(periode.split()))
        account_number = header_df.loc[header_df[0] == 'NO. REKENING', 2].values[0]
        
        # Extract transaction tables
        dataframes = read_pdf(
            pdf_path,
            area=(231, 25, 797, 577),
            columns=[86, 184, 300, 340, 467],
            pages='all',
            pandas_options={'header': None, 'dtype': str},
            force_subprocess=True
        )
        
        # Process data
        df = union_source(dataframes)
        df = clean_numeric_columns(df, ['amount', 'balance'])
        
        transactions = extract_transactions(df)
        
        # Add metadata to each transaction
        for transaction in transactions:
            transaction['account_number'] = account_number
            transaction['period'] = periode
            
            # Convert date to ISO format if possible
            try:
                if transaction['date'] and not pd.isna(transaction['date']):
                    # Assuming DD/MM/YYYY format from BCA statements
                    date_obj = datetime.strptime(str(transaction['date']), '%d/%m/%Y')
                    transaction['date'] = date_obj.strftime('%Y-%m-%d')
            except:
                pass  # Keep original date if parsing fails
        
        return transactions
        
    except Exception as e:
        print(f"Error parsing PDF: {str(e)}", file=sys.stderr)
        return []


def main():
    if len(sys.argv) != 2:
        print("Usage: python parse.py <pdf_file_path>", file=sys.stderr)
        sys.exit(1)
    
    pdf_path = sys.argv[1]
    transactions = parse_pdf(pdf_path)
    
    # Clean up NaN values for valid JSON
    import math
    def clean_nan(obj):
        if isinstance(obj, dict):
            return {k: clean_nan(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [clean_nan(item) for item in obj]
        elif isinstance(obj, float) and math.isnan(obj):
            return None
        else:
            return obj
    
    clean_transactions = clean_nan(transactions)
    
    # Output JSON to stdout
    print(json.dumps(clean_transactions, indent=2, default=str))


if __name__ == "__main__":
    main()