-- Enable TimescaleDB (if needed)
CREATE EXTENSION IF NOT EXISTS timescaledb;

-- ===================================================================
-- 1. Whale Transactions Table (Core)
-- ===================================================================

DROP TABLE IF EXISTS whale_transactions CASCADE;

CREATE TABLE whale_transactions (
    txid TEXT NOT NULL,
    block_hash TEXT NOT NULL,
    block_height INTEGER NOT NULL,
    detected_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    value_btc DOUBLE PRECISION NOT NULL,
    label TEXT CHECK (label IN ('Whale','Shark','Dolphin')),
    input_count INTEGER,
    output_count INTEGER,
    PRIMARY KEY (txid, block_height, detected_at)  -- ✅ add detected_at here
);

SELECT create_hypertable(
    'whale_transactions',
    'detected_at',
    chunk_time_interval => INTERVAL '7 days',
    if_not_exists => TRUE
);

CREATE INDEX IF NOT EXISTS idx_whale_block_hash ON whale_transactions(block_hash);
CREATE INDEX IF NOT EXISTS idx_whale_label ON whale_transactions(label);
CREATE INDEX IF NOT EXISTS idx_whale_detected_at_desc ON whale_transactions(detected_at DESC);


-- ===================================================================
-- 2. Whale Sentiment Table (Aggregated)
-- ===================================================================

DROP TABLE IF EXISTS whale_sentiment CASCADE;

CREATE TABLE IF NOT EXISTS whale_sentiment (
    block_height INTEGER PRIMARY KEY,
    block_hash TEXT,
    whale_count INTEGER NOT NULL DEFAULT 0,
    shark_count INTEGER NOT NULL DEFAULT 0,
    dolphin_count INTEGER NOT NULL DEFAULT 0,
    sentiment TEXT NOT NULL CHECK (sentiment IN ('bullish','bearish','neutral')),
    calculated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

