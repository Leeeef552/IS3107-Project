-- Whale Transaction Monitoring Database Schema
-- Stores large Bitcoin transactions detected from mempool

DROP TABLE IF EXISTS whale_transactions CASCADE;

CREATE TABLE whale_transactions (
    txid TEXT NOT NULL,
    detected_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    value_btc DOUBLE PRECISION NOT NULL,
    value_usd DOUBLE PRECISION,
    btc_price_at_detection DOUBLE PRECISION,
    status TEXT DEFAULT 'mempool',  -- mempool, confirmed, or dropped
    confirmation_time TIMESTAMPTZ,
    block_height INTEGER,
    fee_btc DOUBLE PRECISION,
    input_count INTEGER,
    output_count INTEGER,
    input_addresses TEXT[],   -- Array of source addresses
    output_addresses TEXT[],  -- Array of destination addresses
    primary_input_address TEXT,  -- Main input address (usually first)
    primary_output_address TEXT, -- Main output address (usually largest)
    notes TEXT,
    PRIMARY KEY (txid, detected_at)
);

-- Create hypertable for time-series optimization
SELECT create_hypertable(
    'whale_transactions',
    'detected_at',
    chunk_time_interval => INTERVAL '7 days'
);

-- Create indexes for fast queries
CREATE INDEX idx_whale_txid ON whale_transactions(txid);
CREATE INDEX idx_whale_status ON whale_transactions(status);
CREATE INDEX idx_whale_detected_at_desc ON whale_transactions(detected_at DESC);
CREATE INDEX idx_whale_value_btc_desc ON whale_transactions(value_btc DESC);

-- Add retention policy: keep whale transactions for 1 year
SELECT add_retention_policy('whale_transactions', INTERVAL '1 year', if_not_exists => TRUE);

-- Continuous aggregate for hourly whale statistics
DROP MATERIALIZED VIEW IF EXISTS whale_stats_1h CASCADE;

CREATE MATERIALIZED VIEW whale_stats_1h
WITH (timescaledb.continuous) AS
SELECT
    time_bucket('1 hour', detected_at) AS bucket,
    COUNT(*) AS transaction_count,
    SUM(value_btc) AS total_btc,
    SUM(value_usd) AS total_usd,
    AVG(value_btc) AS avg_btc,
    MAX(value_btc) AS max_btc,
    MIN(value_btc) AS min_btc,
    AVG(btc_price_at_detection) AS avg_btc_price
FROM whale_transactions
GROUP BY bucket
WITH NO DATA;

-- Refresh the aggregate
CALL refresh_continuous_aggregate('whale_stats_1h', NULL, NULL);

-- Add continuous aggregate policy (refresh every hour)
SELECT add_continuous_aggregate_policy('whale_stats_1h',
    start_offset => INTERVAL '3 hours',
    end_offset => INTERVAL '1 hour',
    schedule_interval => INTERVAL '1 hour',
    if_not_exists => TRUE
);

-- Daily aggregate for longer-term analysis
DROP MATERIALIZED VIEW IF EXISTS whale_stats_1d CASCADE;

CREATE MATERIALIZED VIEW whale_stats_1d
WITH (timescaledb.continuous) AS
SELECT
    time_bucket('1 day', detected_at) AS bucket,
    COUNT(*) AS transaction_count,
    SUM(value_btc) AS total_btc,
    SUM(value_usd) AS total_usd,
    AVG(value_btc) AS avg_btc,
    MAX(value_btc) AS max_btc,
    MIN(value_btc) AS min_btc
FROM whale_transactions
GROUP BY bucket
WITH NO DATA;

CALL refresh_continuous_aggregate('whale_stats_1d', NULL, NULL);

SELECT add_continuous_aggregate_policy('whale_stats_1d',
    start_offset => INTERVAL '7 days',
    end_offset => INTERVAL '1 day',
    schedule_interval => INTERVAL '1 day',
    if_not_exists => TRUE
);

-- Create a view for recent whale activity (last 24 hours)
CREATE OR REPLACE VIEW recent_whale_activity AS
SELECT
    txid,
    detected_at,
    value_btc,
    value_usd,
    btc_price_at_detection,
    status,
    confirmation_time,
    EXTRACT(EPOCH FROM (confirmation_time - detected_at))/60 AS confirmation_minutes
FROM whale_transactions
WHERE detected_at > NOW() - INTERVAL '24 hours'
ORDER BY detected_at DESC;
