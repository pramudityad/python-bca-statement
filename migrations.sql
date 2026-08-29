-- AFTIS runtime migrations (applied idempotently by server.py at startup)
-- Safe to re-run: every statement is idempotent.

-- Provenance + dedup ledger. The dual guard is deliberate:
--   file_hash            catches double-taps and retry-after-timeout of the same bytes
--   UNIQUE(account, period) catches a re-download of the same month, which myBCA
--                         can issue with different bytes (embedded PDF timestamps)
CREATE TABLE IF NOT EXISTS processed_files (
    id SERIAL PRIMARY KEY,
    file_hash    CHAR(64) UNIQUE,
    source_file  TEXT,
    account_number VARCHAR(20),
    period       VARCHAR(20),
    txn_count    INTEGER,
    ingested_at  TIMESTAMP DEFAULT NOW(),
    UNIQUE (account_number, period)
);

ALTER TABLE transactions ADD COLUMN IF NOT EXISTS file_hash CHAR(64);
ALTER TABLE transactions ADD COLUMN IF NOT EXISTS source_file TEXT;

CREATE INDEX IF NOT EXISTS idx_transactions_file_hash ON transactions(file_hash);

-- Backfill: protect months already ingested before file-level tracking existed.
-- Backfilled rows have a NULL file_hash, which is correct -- they predate tracking.
INSERT INTO processed_files (account_number, period, txn_count)
SELECT account_number, period, COUNT(*)
FROM transactions
WHERE account_number IS NOT NULL AND period IS NOT NULL
GROUP BY account_number, period
ON CONFLICT DO NOTHING;
