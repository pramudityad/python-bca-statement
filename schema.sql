-- AFTIS Transactions Table
-- Run this in your Supabase SQL editor to create the transactions table

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

-- Create index for common queries
CREATE INDEX idx_transactions_date ON transactions(date);
CREATE INDEX idx_transactions_account ON transactions(account_number);
CREATE INDEX idx_transactions_period ON transactions(period);

-- Enable RLS (Row Level Security) - optional but recommended
ALTER TABLE transactions ENABLE ROW LEVEL SECURITY;

-- Create policy to allow service role full access
CREATE POLICY "Service role can manage transactions" ON transactions
FOR ALL USING (auth.role() = 'service_role');