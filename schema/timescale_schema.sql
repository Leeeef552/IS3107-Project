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

SELECT create_hypertable('historical_price','time', chunk_time_interval => INTERVAL '7 days');


CREATE UNIQUE INDEX IF NOT EXISTS historical_price_time_idx ON historical_price (time);