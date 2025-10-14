-- 5-minute aggregates (for 5D view with 5-min candles)
DROP MATERIALIZED VIEW IF EXISTS price_5min CASCADE;

CREATE MATERIALIZED VIEW price_5min
WITH (timescaledb.continuous) AS
SELECT 
    time_bucket('5 minutes', time) AS bucket,
    FIRST(open, time) AS open,
    MAX(high) AS high,
    MIN(low) AS low,
    LAST(close, time) AS close,
    SUM(volume) AS volume
FROM historical_price
GROUP BY bucket
WITH NO DATA;

CALL refresh_continuous_aggregate('price_5min', NULL, NULL);

-- Continuous aggregate refresh policies
SELECT add_continuous_aggregate_policy('price_5min',
    start_offset => INTERVAL '1 hour',
    end_offset => INTERVAL '5 minutes',
    schedule_interval => INTERVAL '5 minutes');

-- Retention policies
SELECT add_retention_policy('price_5min', INTERVAL '6 months');