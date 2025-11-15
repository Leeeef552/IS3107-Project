-- ===================================================================
-- 1. Whale Transactions (smart-money rows)
-- ===================================================================

DROP TABLE IF EXISTS whale_transactions CASCADE;

CREATE TABLE whale_transactions (
    txid TEXT NOT NULL,
    block_hash TEXT NOT NULL,
    block_height INTEGER NOT NULL,
    block_timestamp TIMESTAMPTZ NOT NULL,
    detected_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    value_btc DOUBLE PRECISION NOT NULL,
    label TEXT CHECK (label IN ('Whale','Shark','Dolphin')),
    input_count INTEGER,
    output_count INTEGER,
    fee_sats BIGINT,
    input_sum_btc DOUBLE PRECISION,
    output_sum_btc DOUBLE PRECISION,
    external_out_btc DOUBLE PRECISION,
    to_exchange BOOLEAN,
    from_exchange BOOLEAN,
    vsize INTEGER,
    weight INTEGER,
    output_addresses TEXT[]
);

-- Create hypertable BEFORE constraints
SELECT create_hypertable(
    'whale_transactions',
    'block_timestamp',
    chunk_time_interval => INTERVAL '7 days',
    if_not_exists => TRUE
);

-- Primary key must include the time partition column
ALTER TABLE whale_transactions ADD CONSTRAINT whale_tx_pk PRIMARY KEY (txid, block_height, block_timestamp);

-- Recommended indexes
CREATE INDEX IF NOT EXISTS idx_whale_block_hash ON whale_transactions(block_hash);
CREATE INDEX IF NOT EXISTS idx_whale_label ON whale_transactions(label);
CREATE INDEX IF NOT EXISTS idx_whale_block_ts_desc ON whale_transactions(block_timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_whale_to_ex ON whale_transactions(to_exchange);
CREATE INDEX IF NOT EXISTS idx_whale_from_ex ON whale_transactions(from_exchange);
CREATE INDEX IF NOT EXISTS idx_whale_output_addr_gin ON whale_transactions USING GIN (output_addresses);

-- Optional: Enable compression for older chunks
ALTER TABLE whale_transactions SET (
    timescaledb.compress,
    timescaledb.compress_orderby = 'block_timestamp DESC',
    timescaledb.compress_segmentby = 'label'
);

-- ===================================================================
-- 2. Block Metrics (per-block aggregates)
-- ===================================================================

DROP TABLE IF EXISTS block_metrics CASCADE;

CREATE TABLE block_metrics (
    block_height INTEGER NOT NULL,
    block_hash TEXT NOT NULL,
    block_timestamp TIMESTAMPTZ NOT NULL,

    tx_count INTEGER,
    size INTEGER,
    weight INTEGER,
    fill_ratio DOUBLE PRECISION,

    fee_total_sats BIGINT,
    avg_fee_rate_sat_vb DOUBLE PRECISION,
    median_fee_rate_sat_vb DOUBLE PRECISION,

    whale_weighted_flow DOUBLE PRECISION,
    whale_total_external_btc DOUBLE PRECISION,
    to_exchange_btc DOUBLE PRECISION,
    from_exchange_btc DOUBLE PRECISION,
    top5_concentration DOUBLE PRECISION,
    consolidation_index DOUBLE PRECISION,
    distribution_index DOUBLE PRECISION,

    labeled_tx_count INTEGER,
    whale_count INTEGER,
    shark_count INTEGER,
    dolphin_count INTEGER,

    calculated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Hypertable
SELECT create_hypertable(
    'block_metrics',
    'block_timestamp',
    chunk_time_interval => INTERVAL '7 days',
    if_not_exists => TRUE
);

-- Primary key
ALTER TABLE block_metrics
    ADD CONSTRAINT block_metrics_pk PRIMARY KEY (block_height, block_timestamp);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_bm_ts_desc ON block_metrics(block_timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_bm_hash ON block_metrics(block_hash);

-- Compression and retention
ALTER TABLE block_metrics SET (
    timescaledb.compress,
    timescaledb.compress_orderby = 'block_timestamp DESC'
);

-- ===================================================================
-- 3. Whale Sentiment (final score + explainability)
-- ===================================================================

DROP TABLE IF EXISTS whale_sentiment CASCADE;

CREATE TABLE whale_sentiment (
    block_height INTEGER NOT NULL,
    block_hash TEXT,
    block_timestamp TIMESTAMPTZ,

    whale_count INTEGER NOT NULL DEFAULT 0,
    shark_count INTEGER NOT NULL DEFAULT 0,
    dolphin_count INTEGER NOT NULL DEFAULT 0,

    score DOUBLE PRECISION NOT NULL,
    sentiment TEXT NOT NULL CHECK (sentiment IN ('bullish','bearish','neutral')),

    whale_flow_component DOUBLE PRECISION,
    exchange_pressure_component DOUBLE PRECISION,
    fee_pressure_component DOUBLE PRECISION,
    utilization_component DOUBLE PRECISION,

    calculated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Hypertable creation
SELECT create_hypertable(
    'whale_sentiment',
    'block_timestamp',
    chunk_time_interval => INTERVAL '7 days',
    if_not_exists => TRUE
);

-- Primary key
ALTER TABLE whale_sentiment
    ADD CONSTRAINT whale_sentiment_pk PRIMARY KEY (block_height, block_timestamp);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_ws_sentiment_block_ts_desc
    ON whale_sentiment (sentiment, block_timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_ws_block_ts_desc
    ON whale_sentiment(block_timestamp DESC);

-- Compression
ALTER TABLE whale_sentiment SET (
    timescaledb.compress,
    timescaledb.compress_orderby = 'block_timestamp DESC'
);