-- Monthly aggregates (for all-time view)
DROP MATERIALIZED VIEW IF EXISTS price_1mo CASCADE;

CREATE MATERIALIZED VIEW price_1mo
WITH (timescaledb.continuous) AS
SELECT 
    time_bucket('1 month', time) AS bucket,
    FIRST(open, time) AS open,
    MAX(high) AS high,
    MIN(low) AS low,
    LAST(close, time) AS close,
    SUM(volume) AS volume
FROM historical_price
GROUP BY bucket
WITH NO DATA;

CALL refresh_continuous_aggregate('price_1mo', NULL, NULL);

-- Continuous aggregate refresh policies
SELECT add_continuous_aggregate_policy('price_1mo',
    start_offset => INTERVAL '6 months',
    end_offset => INTERVAL '1 month',
    schedule_interval => INTERVAL '1 month');

-- Retention policies
SELECT add_retention_policy('price_1mo', INTERVAL '10 years');