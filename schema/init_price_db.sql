CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;

DROP TABLE IF EXISTS historical_price CASCADE;

CREATE TABLE historical_price (
    time TIMESTAMPTZ NOT NULL,
    open DOUBLE PRECISION,
    high DOUBLE PRECISION,
    low DOUBLE PRECISION,
    close DOUBLE PRECISION,
    volume DOUBLE PRECISION,
    PRIMARY KEY (time)
);

SELECT create_hypertable('historical_price', 'time', chunk_time_interval => INTERVAL '7 days');

CREATE UNIQUE INDEX IF NOT EXISTS historical_price_time_idx ON historical_price (time);

-- enable columnstore compression
ALTER TABLE historical_price
SET (
    timescaledb.compress,
    timescaledb.compress_segmentby = 'time'
);

-- Add compression policy
SELECT add_compression_policy('historical_price', INTERVAL '6 months');
