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

SELECT create_hypertable('historical_price', 'time', if_not_exists => TRUE);