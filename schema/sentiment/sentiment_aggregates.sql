-- Create continuous aggregates for sentiment at different time intervals
-- These align with the price data intervals for ML feature engineering

-- =====================================================================
-- 1-HOUR SENTIMENT AGGREGATES
-- =====================================================================
DROP MATERIALIZED VIEW IF EXISTS sentiment_1h CASCADE;

CREATE MATERIALIZED VIEW sentiment_1h
WITH (timescaledb.continuous) AS
SELECT 
    time_bucket('1 hour', time) AS bucket,
    COUNT(*) as article_count,
    AVG(sentiment_score) as avg_sentiment,
    STDDEV(sentiment_score) as sentiment_volatility,
    MIN(sentiment_score) as min_sentiment,
    MAX(sentiment_score) as max_sentiment,
    -- Weighted sentiment (by confidence)
    SUM(sentiment_score * confidence) / NULLIF(SUM(confidence), 0) as weighted_sentiment,
    -- Count by label
    COUNT(*) FILTER (WHERE sentiment_label = 'positive') as positive_count,
    COUNT(*) FILTER (WHERE sentiment_label = 'negative') as negative_count,
    COUNT(*) FILTER (WHERE sentiment_label = 'neutral') as neutral_count,
    -- Sentiment momentum (difference from previous period)
    AVG(confidence) as avg_confidence
FROM news_sentiment
GROUP BY bucket
WITH NO DATA;

-- Add refresh policy
SELECT add_continuous_aggregate_policy('sentiment_1h',
    start_offset => INTERVAL '1 day',
    end_offset => INTERVAL '1 hour',
    schedule_interval => INTERVAL '1 hour');

-- =====================================================================
-- 1-DAY SENTIMENT AGGREGATES
-- =====================================================================
DROP MATERIALIZED VIEW IF EXISTS sentiment_1d CASCADE;

CREATE MATERIALIZED VIEW sentiment_1d
WITH (timescaledb.continuous) AS
SELECT 
    time_bucket('1 day', time) AS bucket,
    COUNT(*) as article_count,
    AVG(sentiment_score) as avg_sentiment,
    STDDEV(sentiment_score) as sentiment_volatility,
    MIN(sentiment_score) as min_sentiment,
    MAX(sentiment_score) as max_sentiment,
    SUM(sentiment_score * confidence) / NULLIF(SUM(confidence), 0) as weighted_sentiment,
    COUNT(*) FILTER (WHERE sentiment_label = 'positive') as positive_count,
    COUNT(*) FILTER (WHERE sentiment_label = 'negative') as negative_count,
    COUNT(*) FILTER (WHERE sentiment_label = 'neutral') as neutral_count,
    AVG(confidence) as avg_confidence
FROM news_sentiment
GROUP BY bucket
WITH NO DATA;

SELECT add_continuous_aggregate_policy('sentiment_1d',
    start_offset => INTERVAL '1 month',
    end_offset => INTERVAL '1 day',
    schedule_interval => INTERVAL '1 day');

-- =====================================================================
-- 1-WEEK SENTIMENT AGGREGATES
-- =====================================================================
DROP MATERIALIZED VIEW IF EXISTS sentiment_1w CASCADE;

CREATE MATERIALIZED VIEW sentiment_1w
WITH (timescaledb.continuous) AS
SELECT 
    time_bucket('1 week', time) AS bucket,
    COUNT(*) as article_count,
    AVG(sentiment_score) as avg_sentiment,
    STDDEV(sentiment_score) as sentiment_volatility,
    MIN(sentiment_score) as min_sentiment,
    MAX(sentiment_score) as max_sentiment,
    SUM(sentiment_score * confidence) / NULLIF(SUM(confidence), 0) as weighted_sentiment,
    COUNT(*) FILTER (WHERE sentiment_label = 'positive') as positive_count,
    COUNT(*) FILTER (WHERE sentiment_label = 'negative') as negative_count,
    COUNT(*) FILTER (WHERE sentiment_label = 'neutral') as neutral_count,
    AVG(confidence) as avg_confidence
FROM news_sentiment
GROUP BY bucket
WITH NO DATA;

SELECT add_continuous_aggregate_policy('sentiment_1w',
    start_offset => INTERVAL '2 months',
    end_offset => INTERVAL '1 week',
    schedule_interval => INTERVAL '1 week');

-- =====================================================================
-- 1-MONTH SENTIMENT AGGREGATES
-- =====================================================================
DROP MATERIALIZED VIEW IF EXISTS sentiment_1mo CASCADE;

CREATE MATERIALIZED VIEW sentiment_1mo
WITH (timescaledb.continuous) AS
SELECT 
    time_bucket('1 month', time) AS bucket,
    COUNT(*) as article_count,
    AVG(sentiment_score) as avg_sentiment,
    STDDEV(sentiment_score) as sentiment_volatility,
    MIN(sentiment_score) as min_sentiment,
    MAX(sentiment_score) as max_sentiment,
    SUM(sentiment_score * confidence) / NULLIF(SUM(confidence), 0) as weighted_sentiment,
    COUNT(*) FILTER (WHERE sentiment_label = 'positive') as positive_count,
    COUNT(*) FILTER (WHERE sentiment_label = 'negative') as negative_count,
    COUNT(*) FILTER (WHERE sentiment_label = 'neutral') as neutral_count,
    AVG(confidence) as avg_confidence
FROM news_sentiment
GROUP BY bucket
WITH NO DATA;

SELECT add_continuous_aggregate_policy('sentiment_1mo',
    start_offset => INTERVAL '6 months',
    end_offset => INTERVAL '1 month',
    schedule_interval => INTERVAL '1 month');

-- =====================================================================
-- RETENTION POLICIES
-- =====================================================================
SELECT add_retention_policy('sentiment_1h', INTERVAL '3 months');
SELECT add_retention_policy('sentiment_1d', INTERVAL '2 years');
SELECT add_retention_policy('sentiment_1w', INTERVAL '5 years');
SELECT add_retention_policy('sentiment_1mo', INTERVAL '10 years');

-- =====================================================================
-- HELPER VIEW: JOIN SENTIMENT WITH PRICE DATA
-- Note: This view requires price_1h table from price data setup
-- If price data is not set up yet, this will be skipped
-- =====================================================================

-- Only create view if price_1h table exists
DO $$
BEGIN
    IF EXISTS (SELECT FROM pg_tables WHERE schemaname = 'public' AND tablename = 'price_1h') THEN
        CREATE OR REPLACE VIEW sentiment_price_features AS
        SELECT 
            p.bucket as time,
            p.open, p.high, p.low, p.close, p.volume,
            s.avg_sentiment,
            s.sentiment_volatility,
            s.weighted_sentiment,
            s.positive_count,
            s.negative_count,
            s.neutral_count,
            s.article_count,
            s.avg_confidence
        FROM price_1h p
        LEFT JOIN sentiment_1h s ON p.bucket = s.bucket
        ORDER BY p.bucket DESC;
        
        COMMENT ON VIEW sentiment_price_features IS 
        'Combined view of hourly price and sentiment data for ML feature engineering';
        
        RAISE NOTICE 'Created sentiment_price_features view (joined with price data)';
    ELSE
        RAISE NOTICE 'Skipping sentiment_price_features view - price_1h table not found. Set up price data first if you need this view.';
    END IF;
END $$;

