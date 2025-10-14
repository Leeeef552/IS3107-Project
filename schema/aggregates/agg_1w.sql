-- Weekly aggregates (for 5Y view)
DROP MATERIALIZED VIEW IF EXISTS price_1w CASCADE;

CREATE MATERIALIZED VIEW price_1w
WITH (timescaledb.continuous) AS
SELECT 
    time_bucket('1 week', time) AS bucket,
    FIRST(open, time) AS open,
    MAX(high) AS high,
    MIN(low) AS low,
    LAST(close, time) AS close,
    SUM(volume) AS volume
FROM historical_price
GROUP BY bucket
WITH NO DATA;

CALL refresh_continuous_aggregate('price_1w', NULL, NULL);

-- Continuous aggregate refresh policies
SELECT add_continuous_aggregate_policy('price_1w',
    start_offset => INTERVAL '2 months',
    end_offset => INTERVAL '1 week',
    schedule_interval => INTERVAL '1 week');

-- Retention policies
SELECT add_retention_policy('price_1w', INTERVAL '5 years');
