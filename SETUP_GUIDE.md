# Complete Setup Guide - Bitcoin Analytics Platform

This guide covers the complete setup from start to finish, including Docker, Airflow, data loading, and the Streamlit dashboard.

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Environment Configuration](#environment-configuration)
3. [Docker Setup](#docker-setup)
4. [Airflow Setup and Data Loading](#airflow-setup-and-data-loading)
5. [Streamlit Dashboard](#streamlit-dashboard)
6. [Troubleshooting](#troubleshooting)

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

## Environment Configuration

### Step 1: Create Environment File

Copy the example environment file and configure it:

```bash
cd BT3107-Project
cp env.example .env
```

### Step 2: Configure Environment Variables

Edit `.env` with your settings. The minimum required configuration:

```bash
# Database Configuration (used by Docker containers)
TIMESCALE_HOST=timescaledb
TIMESCALE_PORT=5432
TIMESCALE_USER=postgres
TIMESCALE_PASSWORD=pass
TIMESCALE_DBNAME=postgres

# News API Keys (optional - for sentiment analysis features)
NEWS_API_KEY=your_newsapi_key_here
CRYPTOCOMPARE_API_KEY=your_cryptocompare_key_here
REDDIT_CLIENT_ID=your_reddit_client_id
REDDIT_CLIENT_SECRET=your_reddit_secret
REDDIT_USER_AGENT=BitcoinSentimentBot/1.0
ALPHA_VANTAGE_API_KEY=your_alphavantage_api_key

# Airflow Configuration
AIRFLOW_UID=50000
AIRFLOW_GID=0

# Local Directory Paths (for Airflow containers)
DATA_DIR=/opt/historical_data
SCHEMA_DIR=/opt/schema
AGGREGATES_DIR=/opt/aggregates
```

**Note:** News sentiment features work with or without API keys, but may have rate limits on free tiers.

---

## Docker Setup

### Step 1: Create Required Airflow Directories

Ensure the required directories exist for Airflow volume mounts:

```bash
mkdir -p airflow/logs airflow/plugins airflow/config
```

### Step 2: Build Docker Image

Build the custom Airflow image with all dependencies:

```bash
docker build -t bt3107-project .
```

This will:

- Use the official Airflow image as base
- Install all Python dependencies from `requirements.txt`
- Create the image needed for Airflow containers

### Step 3: Start All Services

Start all containers using Docker Compose:

```bash
docker compose up -d
```

This starts 8 containers:

- `postgres` - Airflow metadata database (port 5433)
- `redis` - Celery message broker (port 6379)
- `timescaledb` - TimescaleDB for Bitcoin data (port 5432)
- `airflow-webserver` - Airflow UI (port 8080)
- `airflow-scheduler` - DAG scheduler
- `airflow-worker` - Task executor
- `airflow-init` - Initialization (runs once, then exits)
- `flower` - Celery monitoring UI (port 5555)

**Wait 1-2 minutes** for all containers to be healthy. Check status:

```bash
docker compose ps
```

All services should show as "healthy" or "running".

### Step 4: Verify Services

**Check TimescaleDB:**

```bash
docker exec timescaledb psql -U postgres -d postgres -c "SELECT NOW();"
```

**Check Airflow webserver:**

```bash
curl http://localhost:8080/health
```

---

## Airflow Setup and Data Loading

### Step 1: Access Airflow UI

Open your browser to:

- **URL**: http://localhost:8080
- **Username**: `airflow`
- **Password**: `airflow`

### Step 2: Verify DAGs are Loaded

1. Go to the **DAGs** page in Airflow UI
2. In the **Tags** search bar, type `crypto`
3. You should see **5 DAGs**:
   - `price_init_dag` - Initializes historical price data
   - `news_init_dag` - Initializes news sentiment data
   - `whale_init_dag` - Initializes whale transaction monitoring
   - `batch_update_price_and_news` - Scheduled updates for price and sentiment
   - `batch_update_whale` - Scheduled updates for whale transactions

### Step 3: Run Initialization DAGs

**IMPORTANT:** Run DAGs in this order, one at a time:

#### 3.1. Initialize Price Data (Required)

1. Find `price_init_dag` in the DAG list
2. Click the **toggle switch** on the left to **unpause** it (it will turn blue)
3. Click the **play button** (▶️) to trigger a DAG run
4. Click on the DAG name to see task progress
5. Wait for all tasks to complete (green checkmarks)

This DAG will:

- Download historical Bitcoin price data (2012-present)
- Pull latest updates from Bitstamp API
- Load data into TimescaleDB
- Create continuous aggregates (1min, 5min, 1h, 1d, 1w, 1mo)

**Expected duration:** 10-30 minutes depending on data size

#### 3.2. Initialize News Sentiment Data (Optional)

1. Find `news_init_dag` in the DAG list
2. **Unpause** it (toggle switch)
3. Click **play button** to trigger a run
4. Monitor progress

This DAG will:

- Initialize sentiment database schema
- Fetch historical news articles
- Run FinBERT sentiment analysis
- Load sentiment data into TimescaleDB

**Expected duration:** 15-45 minutes depending on date range

#### 3.3. Initialize Whale Monitoring (Optional)

1. Find `whale_init_dag` in the DAG list
2. **Unpause** it (toggle switch)
3. Click **play button** to trigger a run
4. Monitor progress

This DAG will:

- Fetch recent Bitcoin blocks
- Extract large transactions
- Initialize whale database schema
- Load whale transactions into TimescaleDB

**Expected duration:** 5-15 minutes

**Note:** For testing, you can reduce the block count in the DAG file (`op_kwargs={"count": 10}`) to make it faster.

### Step 4: Enable Scheduled Updates (Optional)

Once initialization is complete, you can enable scheduled DAGs for automatic updates:

1. **`batch_update_price_and_news`** - Runs hourly to update price and sentiment
2. **`batch_update_whale`** - Runs periodically to update whale transactions

Unpause these DAGs if you want automatic background updates.

### Step 5: Verify Data is Loaded

Check that data exists in TimescaleDB:

```bash
# Check price data
docker exec timescaledb psql -U postgres -d postgres -c \
  "SELECT COUNT(*) as rows, MAX(time) as latest FROM historical_price;"

# Check sentiment data (if loaded)
docker exec timescaledb psql -U postgres -d postgres -c \
  "SELECT COUNT(*) as articles FROM news_articles;"

# Check whale data (if loaded)
docker exec timescaledb psql -U postgres -d postgres -c \
  "SELECT COUNT(*) as whales FROM whale_transactions;"
```

---

## Streamlit Dashboard

### Step 1: Set Up Python Environment

Create and activate a virtual environment:

**macOS/Linux:**

```bash
cd BT3107-Project
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

### Step 2: Install Dependencies

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

### Step 3: Update Environment for Local Python

The dashboard runs locally (not in Docker), so update `.env` with local database connection:

```bash
# For local Python scripts (dashboard, scripts)
TIMESCALE_HOST=localhost  # Change from 'timescaledb' to 'localhost'
TIMESCALE_PORT=5432
TIMESCALE_USER=postgres
TIMESCALE_PASSWORD=pass
TIMESCALE_DBNAME=postgres
```

**Note:** The Docker containers use `timescaledb` as hostname, but local Python scripts use `localhost`.

### Step 4: Launch Dashboard

**Option A: Using Shell Script (macOS/Linux)**

```bash
./bin/run_dashboard.sh
```

**Option B: Using Batch File (Windows)**

```cmd
bin\run_dashboard.bat
```

**Option C: Direct Launch**

```bash
streamlit run dashboard/app.py
```

### Step 5: Access Dashboard

Open your browser to:

- **URL**: http://localhost:8501

The dashboard will automatically refresh every 60 seconds and display:

- Real-time Bitcoin price metrics
- Interactive OHLCV price charts
- News sentiment analysis
- Fear & Greed Index
- Latest news articles
- Whale transaction alerts (if whale monitoring is enabled)

---

## Complete Startup Checklist

Follow this checklist to ensure everything is set up correctly:

- [ ] Docker Desktop is running
- [ ] `.env` file created and configured
- [ ] Docker image built (`docker build -t bt3107-project .`)
- [ ] All containers started (`docker compose up -d`)
- [ ] All containers healthy (`docker compose ps`)
- [ ] Airflow UI accessible at http://localhost:8080
- [ ] All 5 DAGs visible in Airflow UI (search by tag: `crypto`)
- [ ] `price_init_dag` completed successfully (green checkmarks)
- [ ] Price data verified in database (row count > 0)
- [ ] Python virtual environment created and activated
- [ ] Dependencies installed (`pip install -r requirements.txt`)
- [ ] `.env` updated with `localhost` for local Python scripts
- [ ] Streamlit dashboard accessible at http://localhost:8501
- [ ] Dashboard shows price data and charts

---

## Troubleshooting

### Airflow UI Not Accessible

**Problem:** Can't access http://localhost:8080

**Solution:**

```bash
# Check if webserver container is running
docker compose ps

# Check webserver logs
docker compose logs airflow-webserver

# Restart webserver
docker compose restart airflow-webserver

# Wait 30 seconds and try again
```

### DAGs Not Appearing in Airflow

**Problem:** DAGs don't show up in Airflow UI

**Solution:**

```bash
# Check if scheduler is running
docker compose ps | grep scheduler

# Check scheduler logs for errors
docker compose logs airflow-scheduler | tail -50

# Verify DAG files are in correct location
ls -la airflow/dags/

# Restart scheduler
docker compose restart airflow-scheduler
```

### DAG Tasks Failing

**Problem:** Tasks show as failed (red X) in Airflow

**Solution:**

1. Click on the failed task in Airflow UI
2. Click "Log" to see error messages
3. Common issues:
   - **Database connection errors**: Check TimescaleDB is running
   - **Missing dependencies**: Check `requirements.txt` is installed in Docker image
   - **File path errors**: Verify volume mounts in `docker-compose.yaml`

### Database Connection Failed

**Problem:** Dashboard can't connect to TimescaleDB

**Solution:**

```bash
# Check TimescaleDB is running
docker compose ps | grep timescaledb

# Check database logs
docker compose logs timescaledb

# Test connection
docker exec timescaledb psql -U postgres -d postgres -c "SELECT NOW();"

# Verify .env has correct host (localhost for local Python)
grep TIMESCALE_HOST .env
```

### No Price Data in Dashboard

**Problem:** Dashboard loads but shows no data

**Solution:**

```bash
# Check if price_init_dag completed successfully
# In Airflow UI, check price_init_dag has green checkmarks

# Verify data exists in database
docker exec timescaledb psql -U postgres -d postgres -c \
  "SELECT COUNT(*) FROM historical_price;"

# If count is 0, re-run price_init_dag in Airflow
```

### Port Already in Use

**Problem:** Port 8501 or 8080 already in use

**Solution:**

```bash
# Find process using port 8501
lsof -i :8501  # macOS/Linux
netstat -ano | findstr :8501  # Windows

# Kill the process or use different port
# For Streamlit:
streamlit run dashboard/app.py --server.port 8502

# For Airflow, change port in docker-compose.yaml:
# ports:
#   - "8081:8080"  # Change 8080 to 8081
```

### Container Health Checks Failing

**Problem:** Containers show as unhealthy

**Solution:**

```bash
# Check all container logs
docker compose logs

# Check specific service
docker compose logs timescaledb
docker compose logs airflow-webserver

# Restart all services
docker compose down
docker compose up -d

# Wait 2-3 minutes for health checks
```

### Permission Errors

**Problem:** Permission denied errors when creating files

**Solution:**

```bash
# Fix Airflow directory permissions
sudo chown -R 50000:0 airflow/logs airflow/plugins

# Or recreate directories
rm -rf airflow/logs airflow/plugins airflow/config
mkdir -p airflow/logs airflow/plugins airflow/config
```

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                    DATA SOURCES                             │
├─────────────────────────────────────────────────────────────┤
│  Bitstamp API    NewsAPI/CryptoCompare    Mempool.space     │
│  (Price Data)    (News Articles)          (Whale Txs)       │
└────────┬──────────────────┬────────────────────┬───────────┘
         │                  │                    │
         ▼                  ▼                    ▼
┌─────────────────────────────────────────────────────────────┐
│                  AIRFLOW ORCHESTRATION                      │
├─────────────────────────────────────────────────────────────┤
│  DAGs: price_init_dag, news_init_dag, whale_init_dag      │
│  Scheduled: batch_update_price_and_news, batch_update_whale │
└────────┬────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────┐
│                     TIMESCALEDB                            │
├─────────────────────────────────────────────────────────────┤
│  historical_price    news_articles    whale_transactions    │
│  price_1h/1d/1w     sentiment_1h/1d  whale_stats_1h/1d    │
└────────┬────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────┐
│                  STREAMLIT DASHBOARD                        │
├─────────────────────────────────────────────────────────────┤
│  - Price Charts       - Sentiment Analysis                 │
│  - Fear & Greed       - Latest News                         │
│  - Whale Alerts                                             │
│  Auto-refresh: Every 60 seconds                             │
└─────────────────────────────────────────────────────────────┘
```

---

## Next Steps

After completing setup:

1. **Monitor Airflow DAGs**: Check that scheduled DAGs run successfully
2. **Customize Dashboard**: Modify `dashboard/app.py` for custom visualizations
3. **Add Features**: Extend DAGs for additional data sources
4. **Set Up Alerts**: Configure email alerts in Airflow for failed DAGs

---

## Support

For issues:

1. Check this guide's troubleshooting section
2. Review Airflow task logs for specific errors
3. Verify all services are running: `docker compose ps`
4. Check database connectivity: `docker exec timescaledb psql -U postgres -d postgres -c "SELECT NOW();"`

For technical details on specific features:

- Whale monitoring: See `WHALE_MONITOR_EXPLAINED.md`
- Bitcoin addresses: See `BITCOIN_ADDRESSES_EXPLAINED.md`
