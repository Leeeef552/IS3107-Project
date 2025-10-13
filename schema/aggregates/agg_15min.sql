-- 15-minute aggregates (for 1M view with 15-min candles)
DROP MATERIALIZED VIEW IF EXISTS price_15min CASCADE;

CREATE MATERIALIZED VIEW price_15min
WITH (timescaledb.continuous) AS
SELECT 
    time_bucket('15 minutes', time) AS bucket,
    FIRST(open, time) AS open,
    MAX(high) AS high,
    MIN(low) AS low,
    LAST(close, time) AS close,
    SUM(volume) AS volume
FROM historical_price
GROUP BY bucket
WITH NO DATA;

-- Continuous aggregate refresh policies
SELECT add_continuous_aggregate_policy('price_15min',
    start_offset => INTERVAL '1 hour',
    end_offset => INTERVAL '15 minutes',
    schedule_interval => INTERVAL '15 minutes');

-- Retention policies
SELECT add_retention_policy('price_15min', INTERVAL '1 year');
