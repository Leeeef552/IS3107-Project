-- 1-minute aggregates (for 1D view with 1-min candles)
DROP MATERIALIZED VIEW IF EXISTS price_1min CASCADE;

CREATE MATERIALIZED VIEW price_1min
WITH (timescaledb.continuous) AS
SELECT 
    time_bucket('1 minute', time) AS bucket,
    FIRST(open, time) AS open,
    MAX(high) AS high,
    MIN(low) AS low,
    LAST(close, time) AS close,
    SUM(volume) AS volume
FROM historical_price
GROUP BY bucket
WITH NO DATA;

-- Continuous aggregate refresh policies
SELECT add_continuous_aggregate_policy('price_1min',
    start_offset => INTERVAL '1 hour',
    end_offset => INTERVAL '1 minute',
    schedule_interval => INTERVAL '1 minute');

-- Retention policies
SELECT add_retention_policy('price_1min', INTERVAL '1 month');
