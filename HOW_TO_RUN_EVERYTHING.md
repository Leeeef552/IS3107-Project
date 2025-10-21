# How to Run the Complete Bitcoin Analytics Dashboard with Whale Monitoring

## Complete System Overview

Your dashboard now includes:
1. ✅ Real-time Bitcoin prices
2. ✅ News sentiment analysis
3. ✅ Fear & Greed Index
4. ✅ **Whale transaction monitoring** (NEW!)

## Quick Start - Run Everything

### Option 1: Step-by-Step (Recommended First Time)

**Terminal 1** - Start continuous price & sentiment updater:
```bash
./bin/start_updater.sh
```

**Terminal 2** - Start whale monitor:
```bash
# Test mode (low threshold to see results quickly)
python scripts/test_whale_monitor.py

# OR production mode (50 BTC threshold)
python scripts/whale_monitor.py --min-btc 50
```

**Terminal 3** - Launch dashboard:
```bash
./bin/run_dashboard.sh
```

**Browser** - Open:
```
http://localhost:8501
```

### Option 2: Background Mode (For Long-Term Running)

```bash
# 1. Create logs directory
mkdir -p logs

# 2. Start all background services
./bin/start_updater.sh &
python scripts/whale_monitor.py --min-btc 50 > logs/whale.log 2>&1 &

# 3. Launch dashboard (runs in foreground)
./bin/run_dashboard.sh
```

## Dashboard Sections

When you open http://localhost:8501, you'll see:

1. **Price Metrics** (Top)
   - Current BTC price, high, low, volume
   - Multi-currency support (USD/SGD)

2. **Interactive Price Chart**
   - OHLCV candlesticks
   - Time ranges: 24h, 7d, 30d
   - Volume bars

3. **News Sentiment Analysis**
   - Aggregate sentiment trends
   - Article distribution (positive/negative/neutral)
   - Time periods: 24h, 7d, 30d

4. **Fear & Greed Index** + **Latest News** (Side-by-side)
   - Market sentiment gauge
   - Recent Bitcoin news with sentiment scores

5. **🐋 Whale Transaction Alerts** (NEW!)
   - 24-hour whale statistics
   - Total volume and transaction count
   - Largest whale transaction
   - Hourly trend charts
   - Recent whale transactions with mempool.space links

## Whale Monitoring Quick Test

**Before running the full dashboard**, test the whale monitor works:

```bash
# This runs with 0.01 BTC threshold - you'll see results in 1-2 minutes
python scripts/test_whale_monitor.py
```

Expected output:
```
🐋 Starting whale monitor (threshold: 0.01 BTC)
💎 Whale detected: 1.25 BTC ($136,962) - TX: 8a3f2b1c...
💎 Whale detected: 56.04 BTC ($6,140,134) - TX: 13f92cac...
```

Press `Ctrl+C` after seeing a few transactions, then check the database:

```bash
docker exec timescaledb psql -U postgres -d postgres -c \
  "SELECT detected_at, value_btc, value_usd FROM whale_transactions ORDER BY detected_at DESC LIMIT 5;"
```

## Choosing a Whale Threshold

| Threshold | Description | Frequency |
|-----------|-------------|-----------|
| 0.01 BTC | Testing only | Every few minutes |
| 10 BTC | Significant transactions | Few per hour |
| **50 BTC** | **Production default (recommended)** | **Few per day** |
| 100 BTC | Mega whales | Rare |

## Monitoring Status

### Check what's running:

```bash
# Check price updater
ps aux | grep continuous_updater

# Check whale monitor
ps aux | grep whale_monitor

# Check dashboard
ps aux | grep streamlit
```

### View logs:

```bash
# Whale monitor logs (if running in background)
tail -f logs/whale.log

# Dashboard shows logs in terminal where it's running
```

### Check database status:

```bash
# Price data
docker exec timescaledb psql -U postgres -d postgres -c \
  "SELECT COUNT(*) as rows, MAX(time) as latest FROM historical_price;"

# Whale data
docker exec timescaledb psql -U postgres -d postgres -c \
  "SELECT COUNT(*) as whales, SUM(value_btc) as total_btc FROM whale_transactions;"

# Sentiment data
docker exec timescaledb psql -U postgres -d postgres -c \
  "SELECT COUNT(*) as articles FROM news_articles;"
```

## Stopping Everything

```bash
# Stop all Python processes
pkill -f continuous_updater
pkill -f whale_monitor
pkill -f streamlit

# Or Ctrl+C in each terminal if running in foreground
```

## Configuration

### Whale Monitor Threshold

Edit when starting the whale monitor:

```bash
python scripts/whale_monitor.py --min-btc 100  # Only 100+ BTC transactions
```

### Dashboard Refresh Rate

The dashboard auto-refreshes every 60 seconds. This is configured in `dashboard/app.py`:

```python
time.sleep(60)  # Change this value to adjust refresh rate
st.rerun()
```

### Price Update Frequency

Default: Every 60 seconds. To change:

```bash
./bin/start_updater.sh 30  # Update every 30 seconds
```

## Troubleshooting

### Dashboard shows "No whale transactions detected"

**Check if whale monitor is running:**
```bash
ps aux | grep whale_monitor
```

**If not running, start it:**
```bash
python scripts/whale_monitor.py --min-btc 0.1  # Low threshold for testing
```

**Check database:**
```bash
docker exec timescaledb psql -U postgres -d postgres -c \
  "SELECT COUNT(*) FROM whale_transactions;"
```

### "Module not found" errors

```bash
# Activate virtual environment
source .venv/bin/activate  # or: source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
pip install aiohttp  # For whale monitor
```

### TimescaleDB not running

```bash
# Check Docker
docker ps | grep timescaledb

# Start if needed
docker start timescaledb

# Or create new container
docker run -d --name timescaledb \
  -e POSTGRES_USER=postgres \
  -e POSTGRES_PASSWORD=pass \
  -e POSTGRES_DB=postgres \
  -p 5432:5432 \
  timescale/timescaledb:latest-pg17
```

### Whale schema not initialized

```bash
docker exec -i timescaledb psql -U postgres -d postgres < schema/init_whale_db.sql
```

## Complete Startup Checklist

- [ ] TimescaleDB running (`docker ps | grep timescaledb`)
- [ ] Virtual environment activated (`source .venv/bin/activate`)
- [ ] Dependencies installed (`pip install -r requirements.txt && pip install aiohttp`)
- [ ] Database schema initialized (`./bin/setup_all_data.sh` OR manually init whale schema)
- [ ] Continuous updater running (`./bin/start_updater.sh`)
- [ ] Whale monitor running (`python scripts/whale_monitor.py`)
- [ ] Dashboard running (`./bin/run_dashboard.sh`)
- [ ] Browser open to `http://localhost:8501`

## Architecture Diagram

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
│  - 🐋 Whale Alerts (NEW!)                                      │
│                                                                 │
│  Auto-refresh: Every 60 seconds                                 │
└─────────────────────────────────────────────────────────────────┘
```

## Documentation

- **[README.md](README.md)** - Main project documentation
- **[WHALE_MONITOR_README.md](WHALE_MONITOR_README.md)** - Complete whale monitoring guide
- **[WHALE_MONITOR_EXPLAINED.md](WHALE_MONITOR_EXPLAINED.md)** - How whale detection works
- **This file** - How to run everything together

---

**You're all set!** Follow the Quick Start steps above to launch your complete Bitcoin analytics platform with whale monitoring! 🚀
