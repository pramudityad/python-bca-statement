-- AFTIS Transactions Table
-- PostgreSQL schema for BCA bank statement transactions

CREATE TABLE transactions (
    id SERIAL PRIMARY KEY,
    date DATE NOT NULL,
    description TEXT,
    detail TEXT,
    branch TEXT,
    amount DECIMAL(15,2) NOT NULL,
    transaction_type VARCHAR(2) CHECK (transaction_type IN ('DB', 'CR')),
    balance DECIMAL(15,2),
    account_number VARCHAR(20),
    period VARCHAR(20),
    processed_at TIMESTAMP DEFAULT NOW(),
    created_at TIMESTAMP DEFAULT NOW()
);

-- Create indexes for common queries
CREATE INDEX idx_transactions_date ON transactions(date);
CREATE INDEX idx_transactions_account ON transactions(account_number);
CREATE INDEX idx_transactions_period ON transactions(period);
CREATE INDEX idx_transactions_created_at ON transactions(created_at);

-- Create a view for monthly summaries
CREATE VIEW monthly_summary AS
SELECT 
    account_number,
    period,
    COUNT(*) as transaction_count,
    SUM(CASE WHEN transaction_type = 'DB' THEN amount ELSE 0 END) as total_debits,
    SUM(CASE WHEN transaction_type = 'CR' THEN amount ELSE 0 END) as total_credits,
    MIN(date) as period_start,
    MAX(date) as period_end,
    MAX(balance) as ending_balance
FROM transactions 
GROUP BY account_number, period;