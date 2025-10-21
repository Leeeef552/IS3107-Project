# Bitcoin Whale Transaction Monitor

A real-time monitoring system for detecting and tracking large Bitcoin transactions ("whale" transactions) from the Bitcoin mempool.

## Overview

The Whale Monitor continuously polls the mempool.space API to detect large Bitcoin transactions as they occur, before they're even confirmed in a block. This gives you real-time insights into significant Bitcoin movements.

## Features

- **Real-time Detection**: Monitors Bitcoin mempool every 10 seconds
- **Configurable Threshold**: Set custom BTC amount to define "whale" transactions
- **Database Storage**: Stores all detected transactions in TimescaleDB with time-series optimization
- **USD Conversion**: Automatically converts BTC amounts to USD using live pricing from CoinGecko
- **Historical Analysis**: Continuous aggregates for hourly and daily whale activity stats
- **Auto-cleanup**: 1-year retention policy to manage database size

## Architecture

### Database Schema

**Main Table**: `whale_transactions`
- Stores individual whale transactions
- Hypertable optimized for time-series queries
- Indexes on txid, status, detection time, and BTC value

**Aggregates**:
- `whale_stats_1h` - Hourly whale transaction statistics
- `whale_stats_1d` - Daily whale transaction statistics
- `recent_whale_activity` - View of last 24 hours

### Components

1. **[schema/init_whale_db.sql](schema/init_whale_db.sql)** - Database schema and aggregates
2. **[scripts/whale_monitor.py](scripts/whale_monitor.py)** - Main monitoring service
3. **[dashboard/data_queries.py](dashboard/data_queries.py#L315-L445)** - Query functions for dashboard integration

## Installation

### 1. Install Required Dependencies

```bash
# Activate your virtual environment
source .venv/bin/activate  # or `source venv/bin/activate`

# Install async HTTP library
pip install aiohttp
```

### 2. Initialize Database Schema

The whale transaction tables are already initialized if you ran the setup! If not:

```bash
docker exec -i timescaledb psql -U postgres -d postgres < schema/init_whale_db.sql
```

Verify tables exist:

```bash
docker exec timescaledb psql -U postgres -d postgres -c "\\dt whale_transactions"
```

## Usage

### Quick Test (Recommended First Step)

Test with a **very low threshold** (0.01 BTC) to see transactions immediately:

```bash
python scripts/test_whale_monitor.py
```

You should see whale transactions detected within 1-2 minutes. Press `Ctrl+C` to stop.

Check results:

```bash
docker exec timescaledb psql -U postgres -d postgres -c \
  "SELECT detected_at, value_btc, value_usd, txid FROM whale_transactions ORDER BY detected_at DESC LIMIT 5;"
```

### Production Monitoring

Run with a realistic whale threshold (e.g., 50 BTC):

```bash
# Default threshold: 50 BTC
python scripts/whale_monitor.py

# Custom threshold: 100 BTC
python scripts/whale_monitor.py --min-btc 100

# Lower threshold: 10 BTC (will catch more transactions)
python scripts/whale_monitor.py --min-btc 10
```

### Run in Background

```bash
# Using nohup
nohup python scripts/whale_monitor.py --min-btc 50 > logs/whale_monitor.log 2>&1 &

# Or using screen
screen -S whale_monitor
python scripts/whale_monitor.py --min-btc 50
# Press Ctrl+A, then D to detach
```

## Querying Whale Data

### Recent Whale Transactions

```sql
SELECT
    detected_at,
    value_btc,
    value_usd,
    txid,
    status
FROM whale_transactions
ORDER BY detected_at DESC
LIMIT 10;
```

### Today's Whale Activity

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

### Hourly Whale Trends (Last 24h)

```sql
SELECT
    bucket,
    transaction_count,
    total_btc,
    total_usd,
    max_btc
FROM whale_stats_1h
WHERE bucket > NOW() - INTERVAL '24 hours'
ORDER BY bucket DESC;
```

### View Largest Whales Ever

```sql
SELECT
    detected_at,
    value_btc,
    value_usd,
    txid
FROM whale_transactions
ORDER BY value_btc DESC
LIMIT 10;
```

### Get Mempool.space Links

```sql
SELECT
    'https://mempool.space/tx/' || txid as explorer_link,
    value_btc,
    detected_at
FROM whale_transactions
ORDER BY detected_at DESC
LIMIT 5;
```

## Dashboard Integration (Optional)

The whale query functions are already added to `dashboard/data_queries.py`:

- `get_recent_whale_transactions(limit=10)` - Get recent whale txs
- `get_whale_stats(period_hours=24)` - Get summary statistics
- `get_whale_trend(interval='1 hour', limit=24)` - Get time-series data

To add to the Streamlit dashboard, you would add a new section in `dashboard/app.py`:

```python
from dashboard.data_queries import (
    get_recent_whale_transactions,
    get_whale_stats
)

# Add this section in main()
st.divider()
st.subheader("🐋 Whale Alerts")

whale_stats = get_whale_stats(period_hours=24)
if whale_stats and whale_stats['transaction_count'] > 0:
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("Whales (24h)", int(whale_stats['transaction_count']))
    with col2:
        st.metric("Total Volume", f"{whale_stats['total_btc']:,.2f} BTC")
    with col3:
        st.metric("Largest", f"{whale_stats['max_btc']:,.2f} BTC")
    with col4:
        st.metric("Average", f"{whale_stats['avg_btc']:,.2f} BTC")

    # Show recent transactions
    whales = get_recent_whale_transactions(limit=10)
    if not whales.empty:
        st.dataframe(whales[['detected_at', 'value_btc', 'value_usd', 'status', 'txid']])
else:
    st.info("No whale transactions detected yet. The monitor may be starting up.")
```

## Configuration

### Adjusting Threshold

The threshold determines what size transactions are considered "whale" activity:

- **0.01 BTC** (~$1,000) - Testing, will catch many transactions
- **10 BTC** (~$1M) - Significant transactions
- **50 BTC** (~$5M) - Large whale movements (default)
- **100 BTC** (~$10M) - Mega whales only
- **500+ BTC** (~$50M+) - Extremely rare, institutional-size

### API Rate Limits

- **Mempool.space**: No authentication required, polling every 10 seconds is respectful
- **CoinGecko**: Free tier, updates BTC price every 5 minutes

## Monitoring & Maintenance

### Check Monitor Status

```bash
# Check if running
ps aux | grep whale_monitor

# View recent logs
tail -f logs/whale_monitor.log
```

### Database Size

```sql
-- Check table size
SELECT pg_size_pretty(pg_total_relation_size('whale_transactions'));

-- Check row count
SELECT COUNT(*) FROM whale_transactions;
```

### Clear Old Data (Manual)

The retention policy automatically keeps 1 year of data. To manually clean up:

```sql
-- Delete transactions older than 30 days
DELETE FROM whale_transactions
WHERE detected_at < NOW() - INTERVAL '30 days';
```

## Troubleshooting

### No Transactions Detected

1. **Check threshold**: Lower it to 0.01 BTC for testing
2. **Verify internet connection**: Monitor needs access to mempool.space
3. **Check database connection**: Ensure TimescaleDB is running
4. **View logs**: Look for error messages in console or log file

### "Table does not exist" Error

```bash
# Reinitialize schema
docker exec -i timescaledb psql -U postgres -d postgres < schema/init_whale_db.sql
```

### Connection Errors

```bash
# Verify TimescaleDB is running
docker ps | grep timescaledb

# Test database connection
docker exec timescaledb psql -U postgres -d postgres -c "SELECT 1;"
```

## Example Output

```
🐋 Starting whale monitor (threshold: 0.01 BTC)
API: https://mempool.space/api/mempool/recent
2025-10-21 11:30:45 | INFO | Updated BTC price: $109,570.00
2025-10-21 11:30:52 | INFO | 💎 Whale detected: 1.25 BTC ($136,962) - TX: 8a3f2b1c...
2025-10-21 11:31:04 | INFO | 💎 Whale detected: 0.85 BTC ($93,134) - TX: 7e9d4a2b...
2025-10-21 11:31:15 | INFO | 💎 Whale detected: 2.50 BTC ($273,925) - TX: 3c6b8f1e...
```

## Future Enhancements

Potential additions to consider:

- [ ] Notification system (email, Telegram, Discord)
- [ ] Transaction confirmation tracking
- [ ] Whale address identification and tagging
- [ ] Exchange deposit/withdrawal detection
- [ ] Historical whale pattern analysis
- [ ] Correlation with price movements

## Resources

- **Mempool.space API**: https://mempool.space/docs/api
- **TimescaleDB Docs**: https://docs.timescale.com/
- **Bitcoin Transaction Explorer**: https://mempool.space/

## Support

For issues or questions:
1. Check the logs for error messages
2. Verify all dependencies are installed
3. Ensure database schema is initialized
4. Test with lower threshold first

---

**Note**: Whale transaction data is public blockchain information. This tool simply aggregates and analyzes publicly available data from the Bitcoin network.
