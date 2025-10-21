# Complete Setup & Usage Guide - Bitcoin Analytics Platform with Whale Monitoring

This comprehensive guide covers everything from initial setup to running the complete Bitcoin analytics platform with real-time whale transaction monitoring.

## Table of Contents

1. [System Overview](#system-overview)
2. [Prerequisites](#prerequisites)
3. [Initial Setup](#initial-setup)
4. [Running the Dashboard](#running-the-dashboard)
5. [Dashboard Features](#dashboard-features)
6. [Whale Monitoring](#whale-monitoring)
7. [Configuration](#configuration)
8. [Monitoring & Maintenance](#monitoring--maintenance)
9. [Troubleshooting](#troubleshooting)
10. [Advanced Usage](#advanced-usage)

---

## System Overview

Your Bitcoin analytics platform includes:

1. ✅ **Real-time Bitcoin Prices** - Live OHLCV data from Bitstamp API
2. ✅ **News Sentiment Analysis** - FinBERT-powered sentiment from multiple sources
3. ✅ **Fear & Greed Index** - Market sentiment gauge from alternative.me
4. ✅ **Whale Transaction Monitoring** - Real-time detection of large Bitcoin movements
5. ✅ **TimescaleDB Backend** - Optimized time-series data storage
6. ✅ **Interactive Streamlit Dashboard** - Real-time visualization with auto-refresh

### Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     DATA SOURCES                                │
├─────────────────────────────────────────────────────────────────┤
│  Bitstamp API     NewsAPI/CryptoCompare     Mempool.space      │
│  (Price Data)     (News Articles)           (Whale Txs)         │
└────────┬──────────────────┬────────────────────────┬────────────┘
         │                  │                        │
         ▼                  ▼                        ▼
┌─────────────────────────────────────────────────────────────────┐
│                  BACKGROUND SERVICES                            │
├─────────────────────────────────────────────────────────────────┤
│  continuous_updater.py    whale_monitor.py                     │
│  (Every 60s)              (Every 10s)                           │
└────────┬──────────────────────────────────────────┬─────────────┘
         │                                           │
         ▼                                           ▼
┌─────────────────────────────────────────────────────────────────┐
│                     TIMESCALEDB                                 │
├─────────────────────────────────────────────────────────────────┤
│  historical_price     news_articles      whale_transactions    │
│  price_1h/1d/1w       sentiment_1h/1d    whale_stats_1h/1d     │
└────────┬────────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────────┐
│                  STREAMLIT DASHBOARD                            │
├─────────────────────────────────────────────────────────────────┤
│  - Price Charts       - Sentiment Analysis                     │
│  - Fear & Greed       - Latest News                             │
│  - 🐋 Whale Alerts                                              │
│                                                                 │
│  Auto-refresh: Every 60 seconds                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## Prerequisites

### Required Software

**1. Python 3.8 or higher**

```bash
python --version  # Should show 3.8+
```

**2. Docker Desktop**

- Download from: https://www.docker.com/products/docker-desktop
- Install and ensure Docker is running
- Verify: `docker --version`

**3. Git**

```bash
git --version
```

**4. System Requirements**

- 8GB RAM minimum (16GB recommended)
- 10GB free disk space
- Internet connection for data downloads

---

## Initial Setup

### Step 1: Clone the Repository

```bash
git clone <repository-url>
cd BT3107-Project
```

### Step 2: Set Up Python Environment

**Option A: Create New Virtual Environment**

**macOS/Linux:**
```bash
python -m venv .venv
source .venv/bin/activate
```

**Windows (Command Prompt):**
```cmd
python -m venv .venv
.venv\Scripts\activate
```

**Windows (PowerShell):**
```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

### Step 3: Install Dependencies

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

This installs:
- `pandas`, `numpy` - Data processing
- `streamlit` - Dashboard framework
- `plotly` - Interactive charts
- `psycopg2-binary` - PostgreSQL driver
- `sqlalchemy` - Database ORM
- `transformers`, `torch` - FinBERT sentiment analysis
- `requests`, `aiohttp` - API calls
- `python-dotenv` - Environment management
- And more...

### Step 4: Set Up TimescaleDB

**Start TimescaleDB Docker Container:**

```bash
docker run -d --name timescaledb \
  -e POSTGRES_USER=postgres \
  -e POSTGRES_PASSWORD=pass \
  -e POSTGRES_DB=postgres \
  -p 5432:5432 \
  timescale/timescaledb:latest-pg17
```

**Verify it's running:**

```bash
docker ps | grep timescaledb
```

### Step 5: Configure API Keys (Optional)

Create a `.env` file for API keys:

```bash
cp env.example .env
nano .env  # Or use your preferred editor
```

Add your API keys:

```bash
# Database (already set up)
TIMESCALE_HOST=localhost
TIMESCALE_PORT=5432
TIMESCALE_USER=postgres
TIMESCALE_PASSWORD=pass
TIMESCALE_DBNAME=postgres

# News APIs (optional - has free tier limits)
NEWS_API_KEY=your_newsapi_key_here
CRYPTOCOMPARE_API_KEY=your_cryptocompare_key
REDDIT_CLIENT_ID=your_reddit_client_id
REDDIT_CLIENT_SECRET=your_reddit_secret
REDDIT_USER_AGENT=BitcoinSentimentBot/1.0
```

**Note:** News sentiment features work with or without API keys, but may have rate limits.

### Step 6: Initialize All Data (One Command!)

```bash
./bin/setup_all_data.sh
```

This automated script will:

1. ✅ Download historical Bitcoin price data (2012-present, ~500MB from Kaggle)
2. ✅ Pull latest updates from Bitstamp API
3. ✅ Load 7+ million price records into TimescaleDB
4. ✅ Create continuous aggregates (1min, 5min, 1h, 1d, 1w, 1mo)
5. ✅ **Initialize whale monitoring database** (NEW!)
6. ✅ Optionally load sentiment data (7-day backfill)

**Expected output:**

```
============================================
 Bitcoin Analytics - Complete Data Setup
============================================

Step 1/6: Downloading Historical Data
Step 2/6: Pulling Latest Price Data
Step 3/6: Loading Data into TimescaleDB
Step 4/6: Creating Continuous Aggregates
Step 5/6: Initializing Whale Monitoring     ← NEW!
Step 6/6: Sentiment Data (Optional)

[OK] Setup Complete!

Next steps:

1. Start continuous updates (Terminal 1):
   ./bin/start_updater.sh

2. Start whale monitor (Terminal 2):
   python scripts/whale_monitor.py --min-btc 50
   (Or test first: python scripts/test_whale_monitor.py)

3. Launch dashboard (Terminal 3):
   ./bin/run_dashboard.sh
```

---

## Running the Dashboard

### Option 1: Step-by-Step (Recommended First Time)

Open **3 terminals** and run these commands:

**Terminal 1** - Start continuous price & sentiment updater:
```bash
cd BT3107-Project
source .venv/bin/activate  # or: source venv/bin/activate
./bin/start_updater.sh
```

**Terminal 2** - Start whale monitor:
```bash
cd BT3107-Project
source .venv/bin/activate

# Test mode first (low threshold to see results quickly)
python scripts/test_whale_monitor.py

# Then stop (Ctrl+C) and run production mode
python scripts/whale_monitor.py --min-btc 50
```

**Terminal 3** - Launch dashboard:
```bash
cd BT3107-Project
source .venv/bin/activate
./bin/run_dashboard.sh
```

**Browser** - Open:
```
http://localhost:8501
```

### Option 2: Background Mode (Long-Term Running)

```bash
# Create logs directory
mkdir -p logs

# Start all services in background
source .venv/bin/activate
./bin/start_updater.sh &
python scripts/whale_monitor.py --min-btc 50 > logs/whale.log 2>&1 &

# Launch dashboard (foreground)
./bin/run_dashboard.sh
```

### Stopping Services

**Foreground mode:**
```bash
# Press Ctrl+C in each terminal
```

**Background mode:**
```bash
# Stop all services
pkill -f continuous_updater
pkill -f whale_monitor
pkill -f streamlit
```

---

## Dashboard Features

When you open http://localhost:8501, you'll see:

### 1. Price Metrics (Top Section)

- **Current BTC Price** with 24h change
- **High/Low** for the period
- **Volume** in BTC and selected currency
- **Multi-currency support** - Toggle between USD/SGD
- **Last updated timestamp** (Singapore Time)

### 2. Interactive Price Chart

- **OHLCV candlestick charts** with volume bars
- **Time range selector:**
  - Last 24 hours (5-min candles)
  - Last 7 days (1-hour candles)
  - Last 30 days (1-hour candles)
- **Responsive full-width layout**
- **Hover details** for each candle

### 3. News Sentiment Analysis

- **Aggregate sentiment trends** over time
- **Article distribution** (positive/negative/neutral stacked bars)
- **Time period selector:**
  - Last 24 hours (hourly buckets)
  - Last 7 days (daily buckets)
  - Last 30 days (daily buckets)
- **Data sources:** NewsAPI, CryptoCompare, Reddit

### 4. Fear & Greed Index

- **Real-time market sentiment gauge** (0-100 scale)
- **Color-coded indicator:**
  - Red (0-25): Extreme Fear
  - Orange (25-55): Fear/Neutral
  - Green (55-100): Greed/Extreme Greed
- **Source:** alternative.me API
- **Updates:** Once per day

### 5. Latest News

- **Top 5 recent Bitcoin articles**
- **Article preview** (150-character excerpts)
- **Smart timestamps:**
  - Relative time for < 24 hours ("16h ago")
  - Full date/time for older articles
- **Sentiment scores** for each article
- **Clickable cards** linking to full articles
- **Scrollable news feed**

### 6. 🐋 Whale Transaction Alerts (NEW!)

- **24-hour summary metrics:**
  - Number of whale transactions detected
  - Total BTC volume moved
  - Largest single whale transaction
  - Average whale transaction size

- **Dual trend charts:**
  - Top panel: Whale transaction count (hourly)
  - Bottom panel: Total BTC volume (hourly)

- **Recent transactions list:**
  - BTC amount & USD value
  - Detection time
  - Transaction status:
    - ⏳ Mempool (unconfirmed)
    - ✅ Confirmed (in block)
  - 🔗 Direct links to mempool.space blockchain explorer

- **Smart empty state:**
  - Instructions if no whales detected
  - Helpful commands to start monitoring

### 7. Auto-Refresh

- Dashboard automatically refreshes every **60 seconds**
- Synchronized with price updater interval
- Updates all sections: prices, sentiment, news, whales
- Manual refresh button in sidebar if needed
- Works with static data if updater isn't running

---

## Whale Monitoring

### Quick Test

Before running production monitoring, test that it works:

```bash
python scripts/test_whale_monitor.py
```

**Expected output within 1-2 minutes:**
```
🐋 Starting whale monitor (threshold: 0.01 BTC)
API: https://mempool.space/api/mempool/recent
💎 Whale detected: 1.25 BTC ($136,962) - TX: 8a3f2b1c...
💎 Whale detected: 56.04 BTC ($6,140,134) - TX: 13f92cac...
```

Press `Ctrl+C` after seeing transactions, then check the database:

```bash
docker exec timescaledb psql -U postgres -d postgres -c \
  "SELECT detected_at, value_btc, value_usd, SUBSTRING(txid, 1, 16) as tx
   FROM whale_transactions ORDER BY detected_at DESC LIMIT 5;"
```

### Production Monitoring

```bash
# Default: 50 BTC threshold (recommended)
python scripts/whale_monitor.py --min-btc 50

# Custom thresholds:
python scripts/whale_monitor.py --min-btc 10   # More sensitive
python scripts/whale_monitor.py --min-btc 100  # Mega whales only
```

### Choosing a Threshold

| Threshold | USD Value (~$110K BTC) | Description | Frequency |
|-----------|------------------------|-------------|-----------|
| 0.01 BTC | $1,100 | Testing only | Every few minutes |
| 1 BTC | $110,000 | Retail investors | Few per hour |
| 10 BTC | $1.1M | High net worth | Hourly |
| **50 BTC** | **$5.5M** | **Whales (default)** | **Few per day** |
| 100 BTC | $11M | Mega whales | Rare |
| 500 BTC | $55M | Institutional | Very rare |

### Background Mode

```bash
mkdir -p logs
nohup python scripts/whale_monitor.py --min-btc 50 > logs/whale.log 2>&1 &

# Check it's running
ps aux | grep whale_monitor

# View live logs
tail -f logs/whale.log

# Stop it
pkill -f whale_monitor
```

### How Whale Detection Works

The whale monitor:

1. **Polls mempool.space API** every 10 seconds
2. **Checks recent transactions** in Bitcoin's mempool (unconfirmed txs)
3. **Detects large transactions** exceeding your threshold
4. **Fetches BTC price** from CoinGecko every 5 minutes
5. **Calculates USD value** for each transaction
6. **Stores in database** with timestamp and status
7. **Updates continuous aggregates** hourly and daily

**Why mempool?** You see large transactions **before they're confirmed** (~10 min advance notice), giving real-time intelligence on whale movements.

For technical details, see: [WHALE_MONITOR_EXPLAINED.md](WHALE_MONITOR_EXPLAINED.md)

---

## Configuration

### Whale Monitor Threshold

Adjust when starting the monitor:

```bash
python scripts/whale_monitor.py --min-btc 100
```

### Dashboard Refresh Rate

Default: 60 seconds. To change, edit `dashboard/app.py`:

```python
time.sleep(60)  # Change this value
st.rerun()
```

### Price Update Frequency

Default: 60 seconds. To change:

```bash
./bin/start_updater.sh 30  # Update every 30 seconds
```

### Dashboard Settings

Configuration in `dashboard/.streamlit/config.toml`:

- Theme colors
- Server port (default: 8501)
- CORS settings
- File watcher options

---

## Monitoring & Maintenance

### Check Running Services

```bash
# Price updater
ps aux | grep continuous_updater

# Whale monitor
ps aux | grep whale_monitor

# Dashboard
ps aux | grep streamlit
```

### View Logs

```bash
# Whale monitor (if running in background)
tail -f logs/whale.log

# Dashboard logs appear in terminal where it's running
```

### Check Database Status

**Price data:**
```bash
docker exec timescaledb psql -U postgres -d postgres -c \
  "SELECT COUNT(*) as rows, MAX(time) as latest FROM historical_price;"
```

**Whale data:**
```bash
docker exec timescaledb psql -U postgres -d postgres -c \
  "SELECT COUNT(*) as whales, SUM(value_btc) as total_btc
   FROM whale_transactions;"
```

**Sentiment data:**
```bash
docker exec timescaledb psql -U postgres -d postgres -c \
  "SELECT COUNT(*) as articles FROM news_articles;"
```

**Continuous aggregates:**
```bash
docker exec timescaledb psql -U postgres -d postgres -c \
  "SELECT view_name FROM timescaledb_information.continuous_aggregates
   ORDER BY view_name;"
```

### Database Size

```bash
docker exec timescaledb psql -U postgres -d postgres -c \
  "SELECT pg_size_pretty(pg_database_size('postgres'));"
```

---

## Troubleshooting

### Dashboard shows "No whale transactions detected"

**Cause:** Whale monitor not running or threshold too high

**Solution:**
```bash
# Check if running
ps aux | grep whale_monitor

# If not running, start with low threshold for testing
python scripts/whale_monitor.py --min-btc 0.1

# Check database
docker exec timescaledb psql -U postgres -d postgres -c \
  "SELECT COUNT(*) FROM whale_transactions;"
```

### "Module not found" errors

**Solution:**
```bash
# Activate virtual environment
source .venv/bin/activate  # or: source venv/bin/activate

# Install all dependencies
pip install -r requirements.txt

# Install whale monitor dependency
pip install aiohttp
```

### TimescaleDB not running

**Solution:**
```bash
# Check Docker
docker ps | grep timescaledb

# Start if stopped
docker start timescaledb

# Or create new container
docker run -d --name timescaledb \
  -e POSTGRES_USER=postgres \
  -e POSTGRES_PASSWORD=pass \
  -e POSTGRES_DB=postgres \
  -p 5432:5432 \
  timescale/timescaledb:latest-pg17
```

### "Database connection failed"

**Solution:**
```bash
# Check Docker is running
docker ps

# Restart TimescaleDB
docker restart timescaledb

# Check logs
docker logs timescaledb

# Test connection
docker exec timescaledb psql -U postgres -d postgres -c "SELECT NOW();"
```

### No price data showing

**Solution:**
```bash
# Check if data exists
docker exec timescaledb psql -U postgres -d postgres -c \
  "SELECT COUNT(*) FROM historical_price;"

# If zero, re-run setup
./bin/setup_all_data.sh

# Check aggregates exist
docker exec timescaledb psql -U postgres -d postgres -c \
  "\\d+ price_1h"
```

### Whale schema not initialized

**Solution:**
```bash
# Manually initialize
docker exec -i timescaledb psql -U postgres -d postgres < schema/init_whale_db.sql

# Verify
docker exec timescaledb psql -U postgres -d postgres -c \
  "\\dt whale_transactions"
```

### Dashboard not updating

**Possible causes:**

1. **Continuous updater not running**
   ```bash
   ps aux | grep continuous_updater
   ./bin/start_updater.sh  # If not running
   ```

2. **Data is stale**
   - Check "Last Updated" timestamp in dashboard
   - Should be within last 60-120 seconds

3. **Database connectivity issues**
   ```bash
   docker ps | grep timescaledb
   docker restart timescaledb
   ```

### Port already in use (8501)

**Solution:**
```bash
# Find process using port 8501
lsof -i :8501

# Kill the process
kill -9 <PID>

# Or use different port
streamlit run dashboard/app.py --server.port 8502
```

---

## Advanced Usage

### Custom Data Queries

**Connect to database:**
```bash
docker exec -it timescaledb psql -U postgres -d postgres
```

**Example queries:**

**Top 10 largest whales:**
```sql
SELECT detected_at, value_btc, value_usd, SUBSTRING(txid, 1, 20) as tx
FROM whale_transactions
ORDER BY value_btc DESC
LIMIT 10;
```

**Today's whale activity:**
```sql
SELECT
  COUNT(*) as whale_count,
  SUM(value_btc) as total_btc,
  SUM(value_usd) as total_usd,
  AVG(value_btc) as avg_btc,
  MAX(value_btc) as largest_btc
FROM whale_transactions
WHERE detected_at > CURRENT_DATE;
```

**Hourly whale trends (last 24h):**
```sql
SELECT bucket, transaction_count, total_btc, max_btc
FROM whale_stats_1h
WHERE bucket > NOW() - INTERVAL '24 hours'
ORDER BY bucket DESC;
```

**Price volatility:**
```sql
SELECT
  bucket,
  close,
  (high - low) / low * 100 as volatility_percent
FROM price_1d
WHERE bucket > NOW() - INTERVAL '30 days'
ORDER BY volatility_percent DESC
LIMIT 10;
```

### Data Export

**Export whale transactions to CSV:**
```bash
docker exec timescaledb psql -U postgres -d postgres -c \
  "COPY (SELECT * FROM whale_transactions ORDER BY detected_at DESC LIMIT 1000)
   TO STDOUT WITH CSV HEADER" > whale_transactions.csv
```

**Export price data:**
```bash
docker exec timescaledb psql -U postgres -d postgres -c \
  "COPY (SELECT * FROM price_1d ORDER BY bucket DESC LIMIT 365)
   TO STDOUT WITH CSV HEADER" > btc_prices_daily.csv
```

### Manual Data Updates

**Update price data manually:**
```bash
python -m scripts.price.backfill_price
python -m scripts.price.load_price
```

**Update sentiment data:**
```bash
python -m scripts.news_sentiment.update_sentiment --hours 168  # 7 days
```

**Refresh aggregates:**
```bash
docker exec timescaledb psql -U postgres -d postgres -c \
  "CALL refresh_continuous_aggregate('price_1h', NULL, NULL);"
```

---

## Complete Startup Checklist

- [ ] TimescaleDB running (`docker ps | grep timescaledb`)
- [ ] Virtual environment activated (`source .venv/bin/activate`)
- [ ] Dependencies installed (`pip list | grep streamlit`)
- [ ] Database initialized (`./bin/setup_all_data.sh` completed)
- [ ] Continuous updater running (`ps aux | grep continuous_updater`)
- [ ] Whale monitor running (`ps aux | grep whale_monitor`)
- [ ] Dashboard running (`ps aux | grep streamlit`)
- [ ] Browser open to `http://localhost:8501`
- [ ] Whale section visible at bottom of dashboard
- [ ] Data updating (check "Last Updated" timestamp)

---

## Documentation

- **This file** - Complete setup and usage guide
- **[README.md](README.md)** - Project overview
- **[WHALE_MONITOR_EXPLAINED.md](WHALE_MONITOR_EXPLAINED.md)** - Technical deep dive on whale detection
- **[dashboard/README.md](dashboard/README.md)** - Dashboard-specific documentation

---

## Support

For issues or questions:

1. Check this guide's troubleshooting section
2. Verify all services are running
3. Check database connectivity
4. Review logs for error messages
5. Ensure API keys are configured (if using news features)

---

**You're all set!** Your Bitcoin analytics platform with whale monitoring is ready to launch. Start with the [Running the Dashboard](#running-the-dashboard) section and enjoy real-time Bitcoin intelligence! 🚀🐋
