# Complete Setup Guide - Bitcoin Price & Sentiment Analysis Platform

This guide provides step-by-step instructions to set up the entire Bitcoin analytics platform from scratch, including database, data pipelines, and interactive dashboard.

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Environment Setup](#environment-setup)
3. [Database Setup](#database-setup)
4. [Data Initialization](#data-initialization)
5. [Dashboard Launch](#dashboard-launch)
6. [Continuous Updates](#continuous-updates)
7. [Verification](#verification)
8. [Troubleshooting](#troubleshooting)

---

## Prerequisites

### Required Software

**1. Python 3.8 or higher**

```bash
python --version  # Should show 3.8+
```

**2. Docker Desktop**

- Download from: https://www.docker.com/products/docker-desktop
- Install and ensure Docker is running before proceeding
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

## Environment Setup

### Step 1: Clone the Repository

```bash
git clone <repository-url>
cd BT3107-Project
```

### Step 2: Set Up Python Environment

**Option A: Use Existing Environment**

If you're already in a virtual environment (conda or venv), skip to Step 3.

```bash
# Check if you're in an environment
echo $VIRTUAL_ENV           # For venv
echo $CONDA_DEFAULT_ENV     # For conda
```

**Option B: Create New Virtual Environment**

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

**Database & Storage**

- `psycopg2-binary` - PostgreSQL adapter
- `sqlalchemy` - SQL toolkit and ORM
- `pandas` - Data manipulation
- `pyarrow` - Parquet file support

**Sentiment Analysis**

- `transformers` - FinBERT model
- `torch` - PyTorch framework
- `vaderSentiment` - Rule-based sentiment
- `praw` - Reddit API wrapper

**Dashboard & Visualization**

- `streamlit` - Dashboard framework
- `plotly` - Interactive charts
- `pytz` - Timezone handling
- `watchdog` - File monitoring

**Data Fetching**

- `requests` - HTTP requests
- `python-dotenv` - Environment variables
- `kaggle` - Kaggle API (optional)

### Step 4: Configure API Keys

Create a `.env` file by copying the template:

```bash
cp env.example .env
```

Edit `.env` with your API keys:

```bash
# Database Configuration (default for local Docker)
DB_HOST=localhost
DB_PORT=5432
DB_NAME=postgres
DB_USER=postgres
DB_PASSWORD=pass

# API Keys (optional, but recommended)
NEWS_API_KEY=your_newsapi_key_here
CRYPTOCOMPARE_API_KEY=your_cryptocompare_key
REDDIT_CLIENT_ID=your_reddit_client_id
REDDIT_CLIENT_SECRET=your_reddit_secret
REDDIT_USER_AGENT=BitcoinSentimentBot/1.0

# Kaggle (optional, for alternative data sources)
KAGGLE_USERNAME=your_kaggle_username
KAGGLE_KEY=your_kaggle_api_key
```

**Getting API Keys:**

- **NewsAPI**: Free tier at https://newsapi.org/register (100 requests/day)
- **CryptoCompare**: Free tier at https://www.cryptocompare.com/cryptopian/api-keys
- **Reddit**: Create app at https://www.reddit.com/prefs/apps
- **Kaggle**: Get from https://www.kaggle.com/settings (for Kaggle datasets)

---

## Database Setup

### Step 1: Start TimescaleDB Container

Pull and run the TimescaleDB Docker container:

```bash
docker pull timescale/timescaledb:latest-pg17

docker run -d \
  --name timescaledb \
  -e POSTGRES_USER=postgres \
  -e POSTGRES_PASSWORD=pass \
  -e POSTGRES_DB=postgres \
  -p 5432:5432 \
  timescale/timescaledb:latest-pg17
```

**Windows (PowerShell):**

```powershell
docker run -d `
  --name timescaledb `
  -e POSTGRES_USER=postgres `
  -e POSTGRES_PASSWORD=pass `
  -e POSTGRES_DB=postgres `
  -p 5432:5432 `
  timescale/timescaledb:latest-pg17
```

### Step 2: Verify Database Connection

```bash
docker exec timescaledb psql -U postgres -c "SELECT version();"
```

You should see PostgreSQL and TimescaleDB version information.

### Step 3: Check Container Status

```bash
docker ps
```

You should see the `timescaledb` container running on port 5432.

---

## Data Initialization

You can initialize all data with a single command or step-by-step.

### Option A: Quick Setup (Recommended)

Run the automated setup script:

```bash
./bin/setup_all_data.sh
```

This script will:

1. Initialize database schema for price data
2. Download historical Bitcoin price data (2012-present)
3. Load data into TimescaleDB
4. Create all continuous aggregates (5min, 1h, 1d, 1w, 1mo)
5. Optionally initialize news sentiment data

Follow the prompts to complete setup.

### Option B: Manual Step-by-Step Setup

**Price Data**

```bash
# Step 1: Initialize price database schema
python -m scripts.price.init_historical_price

# Step 2: Pull latest price data from Bitstamp
python -m scripts.price.pull_update_price

# Step 3: Load price data into TimescaleDB
python -m scripts.price.load_price

# Step 4: Create continuous aggregates
python -m scripts.price.create_aggregates
```

**News Sentiment Data (Optional)**

```bash
# Step 1: Initialize sentiment database schema
python -m scripts.news_sentiment.load_sentiment

# Step 2: Backfill 30 days of news sentiment
python -m scripts.news_sentiment.update_sentiment --hours 720
```

Note: Free API tiers provide limited historical data:

- NewsAPI: Last 30 days maximum
- Reddit: Recent posts only
- CryptoCompare: Limited history on free tier

### Verification

Check data was loaded successfully:

```bash
# Check price data
docker exec timescaledb psql -U postgres -d postgres -c \
  "SELECT COUNT(*) as total_rows, MIN(time) as earliest, MAX(time) as latest FROM historical_price;"

# Check sentiment data (if loaded)
docker exec timescaledb psql -U postgres -d postgres -c \
  "SELECT COUNT(*) as total_articles FROM news_sentiment;"

# Check continuous aggregates
docker exec timescaledb psql -U postgres -d postgres -c \
  "SELECT view_name FROM timescaledb_information.continuous_aggregates;"
```

---

## Dashboard Launch

### Step 1: Launch the Dashboard

```bash
./bin/run_dashboard.sh
```

**Windows:**

```cmd
bin\run_dashboard.bat
```

**Direct Launch (if scripts don't work):**

```bash
streamlit run dashboard/app.py
```

### Step 2: Access Dashboard

The dashboard will automatically open in your browser at:

```
http://localhost:8501
```

If it doesn't open automatically, manually navigate to the URL.

### Step 3: Dashboard Overview

The dashboard displays:

**Top Section: Live Price Metrics**

- Current Bitcoin price (USD/SGD selectable)
- 24-hour high and low
- Trading volume in selected currency
- Last updated timestamp (Singapore Time GMT+8)

**Price Chart Section**

- Interactive OHLC candlestick chart with volume
- Time range selector: Last 24 hours, Last 7 days, Last 30 days
- Automatic interval selection (5min/1hour/1day)
- Zoom and pan controls

**News Sentiment Analysis**

- Aggregate sentiment trends over time
- Article distribution by sentiment (positive/negative/neutral)
- Time period selector matching price chart options

**Bottom Section (Side-by-Side)**

- Fear & Greed Index: Real-time market sentiment gauge (0-100)
- Latest News: Top 5 Bitcoin articles with sentiment scores, previews, and links

**Sidebar Controls**

- Currency selector (USD/SGD with live exchange rates)
- Price chart time range
- Sentiment analysis period
- Last updated timestamp

### Dashboard Features

- **Auto-refresh**: Automatically refreshes every 60 seconds (synchronized with price updates)
- **Responsive**: Works on desktop and tablet screens
- **Interactive**: Click and drag to zoom on charts
- **Live data**: Updates from continuous updater if running
- **Session state**: Maintains selections across refreshes

---

## Continuous Updates

For real-time operation, run the continuous updater in a separate terminal.

### Step 1: Start Continuous Updater

```bash
./bin/start_updater.sh
```

**Windows:**

```cmd
bin\start_updater.bat
```

**Custom Update Interval:**

```bash
./bin/start_updater.sh 30    # Update every 30 seconds
./bin/start_updater.sh 120   # Update every 2 minutes
```

### Step 2: What the Updater Does

**Price Updates (Every 60 seconds)**

- Fetches latest Bitcoin price from Bitstamp API
- Inserts only new data points (incremental)
- Refreshes continuous aggregates automatically

**News Sentiment Updates**

- Incremental: Every 5 minutes (fetches last 2 hours)
- Full refresh: Every 12 hours (fetches last 30 days)
- Automatic deduplication of articles

### Step 3: Monitoring the Updater

The updater logs show:

```
Update #1 - 2025-10-15 13:49:18
Step 1: Pulling latest price data from Bitstamp...
Step 2: Loading NEW price data into TimescaleDB...
✓ Inserted 12 new rows
Step 3: Checking for new articles and analyzing sentiment...
✓ Added 5 new articles
Update completed successfully. Next update in 60s...
```

### Step 4: Stopping the Updater

Press `Ctrl+C` in the terminal running the updater.

---

## Verification

### Check Price Data

```bash
# Total rows
docker exec timescaledb psql -U postgres -d postgres -c \
  "SELECT COUNT(*) FROM historical_price;"

# Latest price
docker exec timescaledb psql -U postgres -d postgres -c \
  "SELECT time, close FROM historical_price ORDER BY time DESC LIMIT 1;"

# Check aggregates
docker exec timescaledb psql -U postgres -d postgres -c \
  "SELECT * FROM price_1h ORDER BY bucket DESC LIMIT 5;"
```

### Check Sentiment Data

```bash
# Total articles
docker exec timescaledb psql -U postgres -d postgres -c \
  "SELECT COUNT(*) FROM news_sentiment;"

# Latest articles
docker exec timescaledb psql -U postgres -d postgres -c \
  "SELECT time, AVG(sentiment_score) FROM news_sentiment GROUP BY time ORDER BY time DESC LIMIT 5;"

# Daily sentiment summary
docker exec timescaledb psql -U postgres -d postgres -c \
  "SELECT * FROM sentiment_1d ORDER BY bucket DESC LIMIT 7;"
```

### Verify Dashboard Data

1. Open dashboard at `http://localhost:8501`
2. Check that current price is displayed
3. Verify price chart shows historical data
4. Confirm sentiment analysis section has data
5. Check Fear & Greed Index loads
6. Verify news articles appear with sentiment scores

---

## Troubleshooting

### Docker Issues

**Container won't start:**

```bash
# Check if port 5432 is already in use
lsof -i :5432  # macOS/Linux
netstat -ano | findstr :5432  # Windows

# Stop conflicting process or use different port
docker run -d --name timescaledb -p 5433:5432 ...
```

**Container stops immediately:**

```bash
# Check logs
docker logs timescaledb

# Common issues:
# - Insufficient memory: Increase Docker memory limit
# - Corrupted data: Remove container and recreate
docker rm timescaledb
```

### Database Connection Errors

**"could not connect to server":**

```bash
# Verify container is running
docker ps

# Restart container
docker restart timescaledb

# Check database is accessible
docker exec timescaledb psql -U postgres -c "SELECT 1;"
```

**"relation does not exist":**

```bash
# Recreate database schema
python -m scripts.load_price

# Recreate aggregates
python -m scripts.create_aggregates
```

### Price Data Issues

**No historical data:**

```bash
# Check parquet file exists
ls -lh historical_data/btcusd_1-min_data.parquet

# Re-download if missing
python -m scripts.init_historical_price

# Reload into database
python -m scripts.load_price
```

**Price not updating:**

```bash
# Check continuous updater is running
ps aux | grep continuous_updater

# Restart updater
./bin/start_updater.sh

# Manually pull latest data
python -m scripts.pull_update_price
python -m scripts.load_price
```

### Sentiment Analysis Issues

**No news articles:**

```bash
# Check API keys in .env file
cat .env | grep API

# Manually fetch news
python -m scripts.news_sentiment.fetch_news

# Load sentiment data
python -m scripts.news_sentiment.update_sentiment --hours 24
```

**Sentiment not displaying:**

```bash
# Check sentiment aggregates exist
docker exec timescaledb psql -U postgres -d postgres -c \
  "\d sentiment_1d"

# Refresh aggregates manually
docker exec timescaledb psql -U postgres -d postgres -c \
  "CALL refresh_continuous_aggregate('sentiment_1d', NULL, NULL);"
```

**Article timestamps incorrect (showing 8 hours ahead):**

This was a timezone bug that has been fixed. If you see incorrect timestamps:

```bash
# Clear articles with wrong timestamps
docker exec timescaledb psql -U postgres -d postgres -c "TRUNCATE news_articles CASCADE;"

# Reload with correct UTC timestamps
python -m scripts.news_sentiment.load_sentiment
python -m scripts.news_sentiment.update_sentiment --hours 720
```

The fix ensures all article timestamps are stored as UTC in the database.

### Dashboard Issues

**Port 8501 already in use:**

```bash
# Find and kill process
lsof -i :8501
kill -9 <PID>

# Or use different port
streamlit run dashboard/app.py --server.port 8502
```

**Dashboard shows no data:**

1. Verify database connection in dashboard logs
2. Check data exists in database
3. Clear Streamlit cache: Press `C` in dashboard
4. Restart dashboard

**Dashboard not auto-refreshing:**

- Dashboard automatically refreshes every 60 seconds (aligned with continuous updater)
- Works with static data if updater is not running
- If refresh seems stuck, check browser console for errors (Press `F12`)
- Manual refresh: Press `R` in browser or use "Refresh Now" button in sidebar

### API Rate Limiting

**NewsAPI rate limit exceeded:**

```bash
# Increase update interval
./bin/start_updater.sh 300  # 5 minutes

# Use other sources (CryptoCompare, Reddit don't require NewsAPI)
```

**Too many requests errors:**

- Add API keys to `.env` for higher limits
- Reduce update frequency
- Check logs for actual API usage

### Memory Issues

**"Killed" or OOM errors:**

```bash
# Increase Docker memory limit (Docker Desktop settings)
# Minimum: 4GB, Recommended: 8GB

# Reduce batch size in scripts
# Edit configs/config.py: BATCH_SIZE = 1000 (down from 10000)
```

### Virtual Environment Issues

**Module not found:**

```bash
# Ensure virtual environment is activated
source .venv/bin/activate  # Linux/Mac
.venv\Scripts\activate     # Windows

# Reinstall requirements
pip install -r requirements.txt
```

**Permission denied on shell scripts:**

```bash
# Make scripts executable
chmod +x bin/*.sh

# Or run with bash explicitly
bash bin/run_dashboard.sh
```

---

## Next Steps

After successful setup:

1. **Let updater run** to build historical sentiment data over time
2. **Explore dashboard features** - try different time ranges and currencies
3. **Monitor performance** - check update logs and database size
4. **Customize** - modify dashboard layout or add features in `dashboard/app.py`
5. **Export data** - use query scripts for analysis and ML models

---

## Getting Help

**For detailed documentation:**

- Main README: `README.md`
- Dashboard docs: `dashboard/README.md`
- Script usage: `python -m scripts.<script_name> --help`

**Common resources:**

- TimescaleDB docs: https://docs.timescale.com
- Streamlit docs: https://docs.streamlit.io
- FinBERT model: https://huggingface.co/ProsusAI/finbert

**System information:**

```bash
# Python version
python --version

# Docker version
docker --version

# Database version
docker exec timescaledb psql -U postgres -c "SELECT version();"

# Installed packages
pip list
```

---

## Summary Commands

**Quick start from scratch:**

```bash
# 1. Start database
docker run -d --name timescaledb -e POSTGRES_PASSWORD=pass -p 5432:5432 timescale/timescaledb:latest-pg17

# 2. Initialize all data
./bin/setup_all_data.sh

# 3. Start updater (Terminal 1)
./bin/start_updater.sh

# 4. Launch dashboard (Terminal 2)
./bin/run_dashboard.sh
```

**Daily operation:**

```bash
# Terminal 1: Updater (keep running)
./bin/start_updater.sh

# Terminal 2: Dashboard (access at http://localhost:8501)
./bin/run_dashboard.sh
```

**Maintenance:**

```bash
# Check database size
docker exec timescaledb psql -U postgres -c "\l+"

# Backup database
docker exec timescaledb pg_dump -U postgres postgres > backup.sql

# Clean old Docker images
docker system prune
```

You're now ready to use the Bitcoin Price & Sentiment Analysis Platform!
