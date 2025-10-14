-- Initialize News Sentiment Database Schema
-- This schema stores news articles and their sentiment scores for Bitcoin price prediction

CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;

-- Drop existing tables if they exist
DROP TABLE IF EXISTS news_articles CASCADE;
DROP TABLE IF EXISTS news_sentiment CASCADE;

-- =====================================================================
-- RAW NEWS ARTICLES TABLE
-- Stores individual news articles with metadata
-- =====================================================================
CREATE TABLE news_articles (
    article_id SERIAL PRIMARY KEY,
    published_at TIMESTAMPTZ NOT NULL,
    title TEXT NOT NULL,
    content TEXT,
    url TEXT UNIQUE,
    source VARCHAR(100),
    author VARCHAR(255),
    keywords TEXT[],
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_news_articles_published_at ON news_articles (published_at DESC);
CREATE INDEX idx_news_articles_source ON news_articles (source);

-- =====================================================================
-- NEWS SENTIMENT HYPERTABLE
-- Stores sentiment scores for each article
-- =====================================================================
CREATE TABLE news_sentiment (
    time TIMESTAMPTZ NOT NULL,
    article_id INTEGER REFERENCES news_articles(article_id) ON DELETE CASCADE,
    sentiment_score DOUBLE PRECISION NOT NULL,  -- -1 (negative) to +1 (positive)
    sentiment_label VARCHAR(20),  -- 'positive', 'negative', 'neutral'
    confidence DOUBLE PRECISION,  -- confidence score 0-1
    model_used VARCHAR(50),  -- 'finbert', 'vader', etc.
    PRIMARY KEY (time, article_id)
);

-- Convert to hypertable with 7-day chunks
SELECT create_hypertable('news_sentiment', 'time', chunk_time_interval => INTERVAL '7 days');

-- Create index for efficient queries
CREATE INDEX idx_news_sentiment_time ON news_sentiment (time DESC);
CREATE INDEX idx_news_sentiment_score ON news_sentiment (sentiment_score);

-- Enable compression
ALTER TABLE news_sentiment
SET (
    timescaledb.compress,
    timescaledb.compress_segmentby = 'article_id'
);

-- Add compression policy (compress data older than 30 days)
SELECT add_compression_policy('news_sentiment', INTERVAL '30 days');

