-- Daily aggregates (for 6M, 1Y, 5Y views)
DROP MATERIALIZED VIEW IF EXISTS price_1d CASCADE;

CREATE MATERIALIZED VIEW price_1d
WITH (timescaledb.continuous) AS
SELECT 
    time_bucket('1 day', time) AS bucket,
    FIRST(open, time) AS open,
    MAX(high) AS high,
    MIN(low) AS low,
    LAST(close, time) AS close,
    SUM(volume) AS volume
FROM historical_price
GROUP BY bucket
WITH NO DATA;

CALL refresh_continuous_aggregate('price_1d', NULL, NULL);

SELECT add_continuous_aggregate_policy('price_1d',
    start_offset => INTERVAL '1 month',
    end_offset => INTERVAL '1 day',
    schedule_interval => INTERVAL '1 day');

SELECT add_retention_policy('price_1d', INTERVAL '5 years');
