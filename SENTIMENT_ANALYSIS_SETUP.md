# Bitcoin News Sentiment Analysis - Complete Setup Guide

## Table of Contents

1. [Overview](#overview)
2. [Prerequisites](#prerequisites)
3. [Getting API Keys](#getting-api-keys)
4. [Installation](#installation)
5. [Database Setup](#database-setup)
6. [Usage](#usage)
7. [ML Feature Extraction](#ml-feature-extraction)
8. [Automated Updates](#automated-updates)
9. [Database Schema](#database-schema)
10. [Troubleshooting](#troubleshooting)

---

## Overview

This sentiment analysis system provides:

- **Multiple Free News Sources**: NewsAPI, CryptoCompare, Reddit
- **State-of-the-art Sentiment Analysis**: FinBERT model (97.4% accuracy on financial text)
- **TimescaleDB Integration**: Hypertables and continuous aggregates
- **Time Intervals**: 1 hour, 1 day, 1 week, 1 month
- **ML-Ready Features**: Combined price and sentiment data

### Architecture

```
News Sources (NewsAPI, CryptoCompare, Reddit)
            |
            v
    fetch_news.py (aggregation & deduplication)
            |
            v
    analyze_sentiment.py (FinBERT analysis)
            |
            v
    TimescaleDB (news_articles + news_sentiment)
            |
            v
    Continuous Aggregates (1h, 1d, 1w, 1mo)
            |
            v
    sentiment_price_features (joined with price data)
```

---

## Prerequisites

- TimescaleDB running in Docker
- Python 3.8+ with virtual environment
- NewsAPI key (free tier: 100 requests/day, used for daily+ intervals only)
- **Price data system** (optional - only needed if you want combined price+sentiment features)
  - If you don't have price data set up, sentiment analysis will work independently
  - The `sentiment_price_features` view will be skipped during setup (this is normal)

## Important Notes

- **NewsAPI Usage**: Only used for daily/weekly/monthly intervals (24+ hours lookback), capped at 30 days maximum
- **Hourly Updates**: Use CryptoCompare + Reddit for hourly sentiment (NewsAPI skipped)
- **Monthly Updates**: NewsAPI fetches only last 30 days (not full 6 months) due to free tier limitations

---

## Getting API Keys

Required and recommended API keys:

### Required: NewsAPI (Professional News - Daily Intervals)

**Free Tier**: 100 requests/day, 1 month history

1. Go to https://newsapi.org/register
2. Sign up with email
3. Verify email and copy API key
4. Used for daily, weekly, and monthly sentiment updates

**Note**: NewsAPI is only used for daily+ intervals (24+ hours lookback), automatically capped at 30 days maximum to comply with free tier limitations.

### Recommended: CryptoCompare (Crypto News - All Intervals)

**Free Tier**: 100,000 calls/month

1. Go to https://www.cryptocompare.com
2. Create account
3. Navigate to https://www.cryptocompare.com/cryptopian/api-keys
4. Create new API key

### Recommended: Reddit (Community Sentiment - All Intervals)

**Free Tier**: Completely free, 60 requests/minute

1. Go to https://www.reddit.com/prefs/apps
2. Click "create another app"
3. Fill in:
   - name: Bitcoin Sentiment Bot
   - app type: script
   - redirect uri: http://localhost:8080
4. Note the client_id (under "personal use script") and secret

**Recommendation**: Get all three for comprehensive coverage. NewsAPI is automatically skipped for hourly updates and capped at 30 days for all other intervals.

---

## Installation

### Step 1: Install Dependencies

```bash
# Activate your virtual environment
source .venv/bin/activate  # Linux/macOS
# or
.venv\Scripts\activate  # Windows

# Install new packages
pip install -r requirements.txt
```

**Note**: First run will download FinBERT model (~440MB) automatically.

### Step 2: Configure Environment Variables

Create a `.env` file in project root (use `env.example` as template):

```bash
# Database Configuration (from existing price setup)
TIMESCALE_HOST=localhost
TIMESCALE_PORT=5432
TIMESCALE_USER=postgres
TIMESCALE_PASSWORD=pass
TIMESCALE_DBNAME=postgres

# News API Keys (add at least ONE)
NEWS_API_KEY=your_newsapi_key_here
CRYPTOCOMPARE_API_KEY=your_cryptocompare_key_here
REDDIT_CLIENT_ID=your_reddit_client_id
REDDIT_CLIENT_SECRET=your_reddit_client_secret
REDDIT_USER_AGENT=BitcoinSentimentBot/1.0
```

---

## Database Setup

### Initialize Sentiment Database

```bash
python -m scripts.news_sentiment.load_sentiment
```

This creates:

- `news_articles` - stores article metadata
- `news_sentiment` - hypertable for sentiment scores
- `sentiment_1h`, `sentiment_1d`, `sentiment_1w`, `sentiment_1mo` - continuous aggregates
- `sentiment_price_features` - view combining price and sentiment (only if price data exists)

**Note**: If you see warnings about "price_1h does not exist", that's normal if you haven't set up price data yet. Sentiment analysis will work independently.

### Backfill Historical Data

```bash
# Backfill last 7 days of sentiment data
python -m scripts.news_sentiment.update_sentiment --backfill 7
```

**Note**: NewsAPI free tier only allows 1 month of historical data.

---

## Usage

### Update Sentiment Data

#### Option 1: Update Specific Time Interval (Recommended)

```bash
# Update hourly sentiment (last 6 hours)
python -m scripts.news_sentiment.update_interval_sentiment --interval 1h --update

# Update daily sentiment (last 7 days)
python -m scripts.news_sentiment.update_interval_sentiment --interval 1d --update

# Update weekly sentiment (last 4 weeks)
python -m scripts.news_sentiment.update_interval_sentiment --interval 1w --update

# Update monthly sentiment (last 6 months)
python -m scripts.news_sentiment.update_interval_sentiment --interval 1mo --update

# Just view existing data (no update)
python -m scripts.news_sentiment.update_interval_sentiment --interval 1h --view
```

**Time Intervals and Lookback Periods:**

- `1h` (Hourly): Last 6 hours, broken down per hour
- `1d` (Daily): Last 7 days, broken down per day
- `1w` (Weekly): Last 4 weeks, broken down per week
- `1mo` (Monthly): Last 6 months, broken down per month

**Standardized Output Columns** (same for all intervals):

- **Time**: Time period label
- **Articles**: Number of articles in that period
- **Sentiment**: Average sentiment score (-1 to +1)
- **Volatility**: Standard deviation (higher = more disagreement)
- **Positive**: Count of positive articles
- **Negative**: Count of negative articles
- **Neutral**: Count of neutral articles
- **Confidence**: Average model confidence (0 to 1)

#### Option 2: Update All Intervals at Once

```bash
# Update all intervals with a single command
python -m scripts.news_sentiment.update_all_intervals
```

This fetches news from the last 6 months and updates all time intervals automatically.

#### Option 3: Manual Update (Advanced)

```bash
# Update last 1 hour (production)
python -m scripts.news_sentiment.update_sentiment --hours 1

# Update last 24 hours (testing)
python -m scripts.news_sentiment.update_sentiment --hours 24

# Backfill last 7 days
python -m scripts.news_sentiment.update_sentiment --backfill 7

# Skip aggregate refresh (faster for testing)
python -m scripts.news_sentiment.update_sentiment --hours 1 --skip-refresh
```

### Update Both Price and Sentiment

```bash
# Integrated update (recommended)
python -m scripts.news_sentiment.integrated_update

# With custom time range
python -m scripts.news_sentiment.integrated_update --hours 2

# Update only sentiment
python -m scripts.news_sentiment.integrated_update --sentiment-only
```

### Verify Data

Connect to database:

```bash
docker exec -it timescaledb psql -U postgres -d postgres
```

Query recent sentiment:

```sql
-- Check article count
SELECT COUNT(*) FROM news_articles;

-- View hourly sentiment
SELECT
    bucket,
    avg_sentiment,
    article_count,
    positive_count,
    negative_count
FROM sentiment_1h
ORDER BY bucket DESC
LIMIT 10;

-- Combined price and sentiment
SELECT
    time,
    close as price,
    avg_sentiment,
    article_count
FROM sentiment_price_features
WHERE time > NOW() - INTERVAL '24 hours'
ORDER BY time DESC;
```

---

## ML Feature Extraction

### Export Features to CSV

```bash
# Daily features (recommended for 1-7 day predictions)
python -m scripts.news_sentiment.query_sentiment_features \
    --interval daily \
    --days 180 \
    --output features_daily.csv

# Hourly features (for intraday predictions)
python -m scripts.news_sentiment.query_sentiment_features \
    --interval hourly \
    --days 30 \
    --output features_hourly.csv

# Weekly features (for long-term predictions)
python -m scripts.news_sentiment.query_sentiment_features \
    --interval weekly \
    --weeks 52 \
    --output features_weekly.csv
```

### Available Features

**Price Features**:

- open, high, low, close, volume

**Sentiment Features**:

- avg_sentiment: Average sentiment score (-1 to +1)
- weighted_sentiment: Confidence-weighted sentiment
- sentiment_volatility: Standard deviation (uncertainty measure)
- positive_count, negative_count, neutral_count: Distribution
- article_count: News volume
- avg_confidence: Model confidence

**Derived Features** (auto-generated):

- price_return, price_change
- close_ma7, close_ma30: Moving averages
- sentiment_change, sentiment_momentum
- pos_neg_ratio: Positive/negative article ratio

### Use in Python

```python
import pandas as pd
from sqlalchemy import create_engine

# Connect to database
engine = create_engine('postgresql://postgres:pass@localhost:5432/postgres')

# Query features
query = """
SELECT * FROM sentiment_price_features
WHERE time > NOW() - INTERVAL '30 days'
ORDER BY time ASC
"""

df = pd.read_sql(query, engine)

# Prepare for ML
feature_cols = [
    'avg_sentiment', 'weighted_sentiment', 'sentiment_volatility',
    'positive_count', 'negative_count', 'article_count',
    'close', 'volume'
]

# Create target (next day's return)
df['target'] = df['close'].shift(-1) / df['close'] - 1

# Split features and target
X = df[feature_cols].dropna()
y = df['target'].dropna()
```

---

## Automated Updates

### Option 1: Cron Job (Linux/macOS)

```bash
# Edit crontab
crontab -e

# Add this line (runs every hour at minute 5)
5 * * * * cd /path/to/BT3107-Project && /path/to/.venv/bin/python -m scripts.news_sentiment.integrated_update --scheduled >> logs/update.log 2>&1
```

### Option 2: Task Scheduler (Windows)

1. Open Task Scheduler
2. Create Basic Task
3. Trigger: Daily, repeat every 1 hour
4. Action: Start a program
   - Program: `C:\path\to\.venv\Scripts\python.exe`
   - Arguments: `-m scripts.integrated_update --scheduled`
   - Start in: `C:\path\to\BT3107-Project`

### Option 3: Manual Integration

Add to your existing price update script:

```python
from scripts.update_sentiment import sync_with_price_update

# After updating price data
update_price_data()

# Sync sentiment data
sync_with_price_update()
```

---

## Database Schema

### Tables

#### news_articles

```sql
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
```

#### news_sentiment (Hypertable)

```sql
CREATE TABLE news_sentiment (
    time TIMESTAMPTZ NOT NULL,
    article_id INTEGER REFERENCES news_articles(article_id),
    sentiment_score DOUBLE PRECISION NOT NULL,  -- -1 to +1
    sentiment_label VARCHAR(20),  -- 'positive', 'negative', 'neutral'
    confidence DOUBLE PRECISION,  -- 0 to 1
    model_used VARCHAR(50),  -- 'finbert', 'vader'
    PRIMARY KEY (time, article_id)
);
```

### Continuous Aggregates

All time intervals (1h, 1d, 1w, 1mo) include:

- bucket: Time bucket
- article_count: Number of articles
- avg_sentiment: Average sentiment score
- sentiment_volatility: Standard deviation
- min_sentiment, max_sentiment: Range
- weighted_sentiment: Confidence-weighted average
- positive_count, negative_count, neutral_count: Distribution
- avg_confidence: Average model confidence

### Helper View

```sql
CREATE VIEW sentiment_price_features AS
SELECT
    p.bucket as time,
    p.open, p.high, p.low, p.close, p.volume,
    s.avg_sentiment, s.sentiment_volatility,
    s.weighted_sentiment, s.positive_count,
    s.negative_count, s.neutral_count,
    s.article_count, s.avg_confidence
FROM price_1h p
LEFT JOIN sentiment_1h s ON p.bucket = s.bucket
ORDER BY p.bucket DESC;
```

---

## Troubleshooting

### Warning: "relation price_1h does not exist"

**Cause**: Price data tables not set up yet

**Solution**: This is expected and safe to ignore if you're only using sentiment analysis. The sentiment system will work fine independently.

If you want combined price+sentiment features:

```bash
# Set up price data first (from main README)
python -m scripts.init_historical_price
python -m scripts.pull_update_price
python -m scripts.load_price

# Then re-run sentiment setup
python -m scripts.news_sentiment.load_sentiment
```

### No Articles Fetched

**Cause**: Missing API keys or no Bitcoin news in time range

**Solution**:

1. Check `.env` file for correct API keys
2. Verify API keys are active (check email for verification)
3. Try longer time range: `--hours 48`
4. Check API rate limits (wait 24h if exceeded)

### Failed to Load FinBERT

**Cause**: First-time model download failed

**Solution**:

```bash
# Download manually
python -c "from transformers import AutoTokenizer, AutoModelForSequenceClassification; AutoTokenizer.from_pretrained('ProsusAI/finbert'); AutoModelForSequenceClassification.from_pretrained('ProsusAI/finbert')"
```

### Database Connection Failed

**Cause**: TimescaleDB not running

**Solution**:

```bash
# Start TimescaleDB
docker start timescaledb

# Or create new instance
docker run -d --name timescaledb \
    -e POSTGRES_USER=postgres \
    -e POSTGRES_PASSWORD=pass \
    -e POSTGRES_DB=postgres \
    -p 5432:5432 \
    timescale/timescaledb:latest-pg17
```

### Rate Limit Exceeded

**Free Tier Limits**:

- NewsAPI: 100 requests/day
- CryptoCompare: 100,000 calls/month
- Reddit: 60 requests/minute

**Solution**: Reduce update frequency or wait for limit reset (usually 24 hours)

### Low Sentiment Accuracy

**Solution**:

1. Use `weighted_sentiment` instead of `avg_sentiment`
2. Filter for high confidence scores: `WHERE avg_confidence > 0.8`
3. Require minimum article count: `WHERE article_count > 5`

---

## Best Practices

### For Development

- Update sentiment daily or every few hours
- Use `--skip-refresh` for faster testing
- Export features regularly to track changes

### For Production

- Set up hourly automated updates
- Monitor logs for errors
- Use error alerting (email/Slack)
- Regular database backups

### For ML Models

- Use `weighted_sentiment` for better accuracy
- Consider `sentiment_volatility` as uncertainty indicator
- Higher `article_count` = more reliable sentiment
- Combine multiple time intervals for ensemble models
- Handle missing sentiment data (fill with 0 = neutral)

---

## Performance

### Update Speed

- Fetch 100 articles: ~5-10 seconds
- FinBERT analysis (100 articles): ~30-60 seconds (CPU), ~10-20 seconds (GPU)
- Database insertion: ~1-2 seconds
- Aggregate refresh: ~5-10 seconds
- **Total per update**: ~1-2 minutes

### Storage

- Price data (1min, per year): ~50 MB
- News articles (per year): ~100-200 MB
- Sentiment scores (per year): ~20-50 MB
- Aggregates: ~5-10 MB

---

## Additional Information

### Sentiment Model Details

**FinBERT**:

- Model: ProsusAI/finbert
- Pre-trained on: 1.8M+ financial sentences
- Accuracy: 97.4% on FinancialPhraseBank
- Output: 3-class (positive/negative/neutral) + confidence
- Performance: ~500ms per article (CPU)

**VADER** (fallback):

- Lexicon-based, optimized for social media
- Output: Compound score (-1 to +1)
- Performance: <10ms per article

### News Sources

1. **NewsAPI**: Professional news from 80,000+ sources worldwide
2. **CryptoCompare**: Crypto-focused news and analysis
3. **Reddit**: Community discussions from r/Bitcoin, r/CryptoCurrency, r/BitcoinMarkets

Articles are automatically:

- Filtered for Bitcoin relevance
- Deduplicated by URL
- Timestamped and stored

---

## Quick Reference

### Common Commands

```bash
# Initialize database
python -m scripts.news_sentiment.load_sentiment

# Update specific time interval
python -m scripts.news_sentiment.update_interval_sentiment --interval 1h --update    # Hourly (6h lookback)
python -m scripts.news_sentiment.update_interval_sentiment --interval 1d --update    # Daily (7d lookback)
python -m scripts.news_sentiment.update_interval_sentiment --interval 1w --update    # Weekly (4w lookback)
python -m scripts.news_sentiment.update_interval_sentiment --interval 1mo --update   # Monthly (6mo lookback)

# Update all intervals at once
python -m scripts.news_sentiment.update_all_intervals

# View interval sentiment (no update)
python -m scripts.news_sentiment.update_interval_sentiment --interval 1h --view

# View comprehensive summary
python -m scripts.news_sentiment.view_sentiment_summary

# Update price + sentiment
python -m scripts.news_sentiment.integrated_update

# Export ML features
python -m scripts.news_sentiment.query_sentiment_features --days 30 --output features.csv
```

### Important Files

- `scripts/news_sentiment/fetch_news.py` - News aggregation
- `scripts/news_sentiment/analyze_sentiment.py` - Sentiment analysis
- `scripts/news_sentiment/load_sentiment.py` - Database initialization
- `scripts/news_sentiment/update_sentiment.py` - Update pipeline
- `scripts/news_sentiment/update_interval_sentiment.py` - Update/view specific intervals
- `scripts/news_sentiment/update_all_intervals.py` - Update all intervals at once
- `scripts/news_sentiment/view_sentiment_summary.py` - View comprehensive summary
- `scripts/news_sentiment/query_sentiment_features.py` - Feature extraction
- `scripts/news_sentiment/integrated_update.py` - Combined price + sentiment update
- `schema/sentiment/init_sentiment_db.sql` - Database schema
- `schema/sentiment/sentiment_aggregates.sql` - Continuous aggregates

---

## Support

For issues:

1. Check logs in the project directory
2. Verify `.env` file configuration
3. Ensure TimescaleDB is running: `docker ps | grep timescaledb`
4. Review this guide's troubleshooting section
5. Check API key status on provider websites
