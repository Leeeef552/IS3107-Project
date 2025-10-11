-- Create continuous aggregates for different time views
-- These will be used by the dashboard to provide optimal data for each resolution

-- 1-minute aggregates (for 1D view with 1-min candles)
CREATE MATERIALIZED VIEW price_1min
WITH (timescaledb.continuous) AS
SELECT 
    time_bucket('1 minute', time) AS bucket,
    FIRST(open, time) as open,
    MAX(high) as high,
    MIN(low) as low,
    LAST(close, time) as close,
    SUM(volume) as volume
FROM historical_price
GROUP BY bucket;

-- 5-minute aggregates (for 5D view with 5-min candles)
CREATE MATERIALIZED VIEW price_5min
WITH (timescaledb.continuous) AS
SELECT 
    time_bucket('5 minutes', time) AS bucket,
    FIRST(open, time) as open,
    MAX(high) as high,
    MIN(low) as low,
    LAST(close, time) as close,
    SUM(volume) as volume
FROM historical_price
GROUP BY bucket;

-- 15-minute aggregates (for 1M view with 15-min candles)
CREATE MATERIALIZED VIEW price_15min
WITH (timescaledb.continuous) AS
SELECT 
    time_bucket('15 minutes', time) AS bucket,
    FIRST(open, time) as open,
    MAX(high) as high,
    MIN(low) as low,
    LAST(close, time) as close,
    SUM(volume) as volume
FROM historical_price
GROUP BY bucket;

-- 1-hour aggregates (for 1M view with 1-hour candles)
CREATE MATERIALIZED VIEW price_1h
WITH (timescaledb.continuous) AS
SELECT 
    time_bucket('1 hour', time) AS bucket,
    FIRST(open, time) as open,
    MAX(high) as high,
    MIN(low) as low,
    LAST(close, time) as close,
    SUM(volume) as volume
FROM historical_price
GROUP BY bucket;

-- Daily aggregates (for 6M, 1Y, 5Y views with daily candles)
CREATE MATERIALIZED VIEW price_1d
WITH (timescaledb.continuous) AS
SELECT 
    time_bucket('1 day', time) AS bucket,
    FIRST(open, time) as open,
    MAX(high) as high,
    MIN(low) as low,
    LAST(close, time) as close,
    SUM(volume) as volume
FROM historical_price
GROUP BY bucket;

-- Weekly aggregates (for 5Y view with weekly candles)
CREATE MATERIALIZED VIEW price_1w
WITH (timescaledb.continuous) AS
SELECT 
    time_bucket('1 week', time) AS bucket,
    FIRST(open, time) as open,
    MAX(high) as high,
    MIN(low) as low,
    LAST(close, time) as close,
    SUM(volume) as volume
FROM historical_price
GROUP BY bucket;

-- Monthly aggregates (for All view with monthly candles)
CREATE MATERIALIZED VIEW price_1mo
WITH (timescaledb.continuous) AS
SELECT 
    time_bucket('1 month', time) AS bucket,
    FIRST(open, time) as open,
    MAX(high) as high,
    MIN(low) as low,
    LAST(close, time) as close,
    SUM(volume) as volume
FROM historical_price
GROUP BY bucket;

-- Add refresh policies to keep aggregates up-to-date
SELECT add_continuous_aggregate_policy('price_1min',
    start_offset => INTERVAL '1 hour',
    end_offset => INTERVAL '1 minute',
    schedule_interval => INTERVAL '1 minute');

SELECT add_continuous_aggregate_policy('price_5min',
    start_offset => INTERVAL '1 hour',
    end_offset => INTERVAL '5 minutes',
    schedule_interval => INTERVAL '5 minutes');

SELECT add_continuous_aggregate_policy('price_15min',
    start_offset => INTERVAL '1 hour',
    end_offset => INTERVAL '15 minutes',
    schedule_interval => INTERVAL '15 minutes');

SELECT add_continuous_aggregate_policy('price_1h',
    start_offset => INTERVAL '1 day',
    end_offset => INTERVAL '1 hour',
    schedule_interval => INTERVAL '1 hour');

SELECT add_continuous_aggregate_policy('price_1d',
    start_offset => INTERVAL '1 month',
    end_offset => INTERVAL '1 day',
    schedule_interval => INTERVAL '1 day');

SELECT add_continuous_aggregate_policy('price_1w',
    start_offset => INTERVAL '2 months',
    end_offset => INTERVAL '1 week',
    schedule_interval => INTERVAL '1 week');

SELECT add_continuous_aggregate_policy('price_1mo',
    start_offset => INTERVAL '6 months',
    end_offset => INTERVAL '1 month',
    schedule_interval => INTERVAL '1 month');

-- Add data retention policies to manage storage
SELECT add_retention_policy('price_1min', INTERVAL '1 month');
SELECT add_retention_policy('price_5min', INTERVAL '6 months');
SELECT add_retention_policy('price_15min', INTERVAL '1 year');
SELECT add_retention_policy('price_1h', INTERVAL '2 years');
SELECT add_retention_policy('price_1d', INTERVAL '5 years');
SELECT add_retention_policy('price_1w', INTERVAL '5 years');
SELECT add_retention_policy('price_1mo', INTERVAL '10 years');