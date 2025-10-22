# Bitcoin Analytics Dashboard

Interactive real-time dashboard for Bitcoin price and sentiment analysis built with Streamlit and Plotly.

## Features

### Auto-Refresh

**The dashboard automatically refreshes every 60 seconds to display live data.**

- Synchronized with continuous updater's price update interval (60 seconds)
- Updates all metrics: price, sentiment, news, Fear & Greed Index
- Works with or without continuous updater running (displays static data if updater stopped)
- No manual intervention required
- Manual refresh button available in sidebar if needed
- Browser tab must remain active for auto-refresh to work

### Real-Time Price Display

- Current Bitcoin price in USD or SGD
- Live exchange rate conversion (hourly updates)
- 24-hour high and low prices
- Trading volume (currency and BTC)
- Singapore Time (GMT+8) timestamps

### Interactive Price Chart

- OHLC candlestick visualization with Plotly
- Volume bar chart overlay
- Three time range options:
  - Last 24 hours (5-minute candles)
  - Last 7 days (1-hour candles)
  - Last 30 days (1-hour candles)
- Zoom, pan, and hover interactions
- Responsive full-width layout

### News Sentiment Analysis

- Aggregate sentiment trends over time
- Article distribution by sentiment (positive/negative/neutral)
- Sentiment volatility indicators
- Confidence metrics
- Three analysis periods:
  - Last 24 hours (hourly aggregates)
  - Last 7 days (daily aggregates)
  - Last 30 days (daily aggregates)
- Multi-source data (NewsAPI, CryptoCompare, Reddit)

### Latest News Feed

- Top 5 most recent Bitcoin articles
- 150-character article preview
- Source badges with color coding
- Sentiment scores and labels
- Smart timestamps: relative time for < 24 hours ("16h ago", "5m ago"), full date/time for older articles ("Oct 14, 2025 10:30")
- Clickable cards linking to full articles
- Scrollable container (380px max height)
- Hover effects and smooth transitions

### Fear & Greed Index

- Real-time market sentiment gauge from alternative.me
- Speedometer visualization (0-100 scale)
- Color-coded indicators:
  - Red (0-25): Extreme Fear
  - Orange (26-45): Fear
  - Yellow (46-55): Neutral
  - Light Green (56-75): Greed
  - Dark Green (76-100): Extreme Greed
- Update timestamp and source link

### Currency Selector

- Toggle between USD and SGD
- Live exchange rates from open.er-api.com
- Applies to: price display, high/low, volume
- Exchange rate indicator (e.g., "1 USD = 1.3450 SGD")

## Quick Start

### Launch Dashboard

```bash
# Using shell script (macOS/Linux)
./bin/run_dashboard.sh

# Using batch file (Windows)
bin\run_dashboard.bat

# Direct launch
streamlit run dashboard/app.py

# Custom port
streamlit run dashboard/app.py --server.port 8502
```

The dashboard opens automatically at `http://localhost:8501`

### Prerequisites

Ensure data is populated before launching:

```bash
# Quick setup (all-in-one script)
./bin/setup_all_data.sh

# Or manual setup
python -m scripts.init_historical_price
python -m scripts.pull_update_price
python -m scripts.load_price
python -m scripts.create_aggregates

# Optional: Load sentiment data
python -m scripts.news_sentiment.load_sentiment
python -m scripts.news_sentiment.update_sentiment --hours 720
```

### For Live Updates

Start the continuous updater in a separate terminal:

```bash
./bin/start_updater.sh
```

This provides:

- Price updates every 60 seconds
- Sentiment updates every 5 minutes
- Full sentiment refresh every 12 hours

## Dashboard Layout

```
┌──────────────────────────────────────────────────────────────┐
│              Bitcoin Analytics Dashboard                     │
├──────────────────────────────────────────────────────────────┤
│  Price  │  High   │   Low   │  Volume      │ Last Updated   │
│ $XXX.XX │ $XXX.XX │ $XXX.XX │ $XXX (X BTC) │ 10/15 13:30    │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│                  Bitcoin Price Chart                         │
│            (Interactive OHLC + Volume)                       │
│                    Full Width                                │
│                                                              │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│            News Sentiment Analysis                           │
│       (Sentiment Trends + Distribution Charts)               │
│                    Full Width                                │
│                                                              │
├───────────────────────┬──────────────────────────────────────┤
│  Fear & Greed Index   │        Latest News                   │
│    (Speedometer)      │  [Article Cards with Sentiment]      │
│      1/4 Width        │     (Scrollable, 3/4 Width)          │
└───────────────────────┴──────────────────────────────────────┘
```

## Sidebar Controls

### Currency Settings

**Display Currency**

- USD (United States Dollar) - default
- SGD (Singapore Dollar)

When SGD is selected, shows: "1 USD = X.XXXX SGD"

### Price Chart

**Time Range** (selectbox)

- Last 24 hours
- Last 7 days
- Last 30 days

Automatically uses optimal intervals:

- 24h: 5-minute candles (288 data points)
- 7d: 1-hour candles (168 data points)
- 30d: 1-hour candles (720 data points)

### Sentiment Analysis

**Analysis Period** (selectbox)

- Last 24 hours (hourly aggregates)
- Last 7 days (daily aggregates)
- Last 30 days (daily aggregates)

Data sources: NewsAPI, CryptoCompare, Reddit

### System Information

- Last updated timestamp (Singapore Time)
- Database connection status
- Refresh button (manual trigger)

## Configuration

### Theme Customization

Edit `dashboard/.streamlit/config.toml`:

```toml
[theme]
primaryColor = "#FF9500"           # Orange accent
backgroundColor = "#0E1117"         # Dark background
secondaryBackgroundColor = "#262730" # Card background
textColor = "#FAFAFA"              # White text
font = "sans serif"

[server]
port = 8501
enableCORS = false
headless = false

[browser]
gatherUsageStats = false
```

### Cache Settings

Dashboard caching strategy for performance:

```python
@st.cache_data(ttl=10)    # Latest price: 10 seconds
@st.cache_data(ttl=60)    # Price history: 1 minute
@st.cache_data(ttl=300)   # Sentiment data: 5 minutes
@st.cache_data(ttl=300)   # News articles: 5 minutes
@st.cache_data(ttl=3600)  # Exchange rates: 1 hour
@st.cache_data(ttl=3600)  # Fear & Greed: 1 hour
```

To clear cache: Press `C` key while dashboard is focused.

## Data Sources

### Price Data

- **API**: Bitstamp (real-time Bitcoin prices)
- **Database**: TimescaleDB (historical storage)
- **Update Frequency**: Every 60 seconds via continuous updater
- **Range**: January 2012 to present
- **Granularity**: 1-minute OHLCV data
- **Aggregates**: 5min, 15min, 1h, 1d, 1w, 1mo

### News Sentiment Data

- **APIs**:
  - NewsAPI (professional news, 30-day limit)
  - CryptoCompare (crypto-focused news)
  - Reddit (r/Bitcoin, r/CryptoCurrency, r/BitcoinMarkets)
- **Model**: FinBERT (ProsusAI/finbert) for financial sentiment
- **Database**: TimescaleDB with continuous aggregates
- **Update Frequency**:
  - Incremental: Every 5 minutes (2-hour lookback)
  - Full refresh: Every 12 hours (30-day lookback)
- **Deduplication**: By article URL

### Fear & Greed Index

- **Source**: Alternative.me API
- **Update Frequency**: Daily (updated once per day)
- **Cache Duration**: 1 hour in dashboard
- **Range**: 0-100 (Extreme Fear to Extreme Greed)
- **Factors**: Volatility, momentum, social media, surveys, dominance, trends

### Exchange Rates

- **Source**: open.er-api.com (free tier)
- **Pair**: USD/SGD
- **Update Frequency**: Hourly
- **Cache Duration**: 1 hour
- **Fallback**: 1.35 if API unavailable

## Troubleshooting

### Dashboard Won't Start

**Issue**: Port 8501 already in use

```bash
# Find process using port
lsof -i :8501  # macOS/Linux
netstat -ano | findstr :8501  # Windows

# Kill process
kill -9 <PID>  # macOS/Linux
taskkill /PID <PID> /F  # Windows

# Or use different port
streamlit run dashboard/app.py --server.port 8502
```

**Issue**: Module not found

```bash
# Activate virtual environment
source .venv/bin/activate  # macOS/Linux
.venv\Scripts\activate     # Windows

# Reinstall dependencies
pip install -r requirements.txt
```

### No Data Displaying

**Symptom**: "Loading..." or empty charts

**Solutions**:

1. Check database is running:

   ```bash
   docker ps | grep timescaledb
   ```

2. Verify data exists:

   ```bash
   docker exec timescaledb psql -U postgres -d postgres -c \
     "SELECT COUNT(*) FROM historical_price;"
   ```

3. Check aggregates exist:

   ```bash
   docker exec timescaledb psql -U postgres -d postgres -c \
     "SELECT view_name FROM timescaledb_information.continuous_aggregates;"
   ```

4. Reload data if needed:
   ```bash
   python -m scripts.load_price
   python -m scripts.create_aggregates
   ```

### Dashboard Not Updating

**Issue**: Old data or stale timestamps

**Solutions**:

1. Start continuous updater:

   ```bash
   ./bin/start_updater.sh
   ```

2. Manual data update:

   ```bash
   python -m scripts.pull_update_price
   python -m scripts.load_price
   ```

3. Check updater is running:

   ```bash
   ps aux | grep continuous_updater
   ```

4. Clear dashboard cache: Press `C` in dashboard

### Charts Not Rendering

**Issue**: Blank chart areas

**Solutions**:

1. Hard refresh browser: `Ctrl+Shift+R` (or `Cmd+Shift+R` on Mac)
2. Check browser console for errors: Press `F12`
3. Verify Plotly installed: `pip show plotly`
4. Clear Streamlit cache: `streamlit cache clear`
5. Restart dashboard

### Slow Performance

**Issue**: Dashboard feels sluggish

**Optimizations**:

1. Select shorter time range (24h instead of 30d)
2. Reduce browser tabs/extensions
3. Check database connection latency
4. Increase Docker resources (RAM/CPU)
5. Restart dashboard to refresh cache
6. Close other resource-intensive applications

### Footer Duplication

**Issue**: Multiple footers appearing

This was a known issue that has been fixed. If you still see it:

1. Pull latest code: `git pull origin main`
2. Clear browser cache: `Ctrl+Shift+R`
3. Restart dashboard

The fix uses session state to prevent duplicate rendering.

### API Rate Limits

**Issue**: "Could not fetch..." warnings

**Expected Behavior**:

- Exchange rates: Falls back to 1.35 if rate limit hit
- Fear & Greed: Cached for 1 hour to reduce calls
- News API: Free tier limited to 100 requests/day

**Solutions**:

- Add API keys to `.env` file for higher limits
- Reduce update frequency in continuous updater
- Use paid API tiers for production use

### News Article Timestamps Incorrect

**Issue**: Articles show publish time 8 hours ahead or "16h ago" doesn't match actual article time

**Cause**: Fixed timezone bug where timestamps were stored as local time (SGT) but labeled as UTC

**Solution**:

```bash
# Clear articles with incorrect timestamps
docker exec timescaledb psql -U postgres -d postgres -c "TRUNCATE news_articles CASCADE;"

# Reload with correct UTC timestamps
python -m scripts.news_sentiment.load_sentiment
python -m scripts.news_sentiment.update_sentiment --hours 720
```

**Note**: This issue has been fixed in the latest version. All timestamps now stored correctly as UTC.

## Development

### File Structure

```
dashboard/
├── app.py                 # Main Streamlit application
│   ├── main()            # Dashboard entry point
│   ├── create_price_chart()
│   ├── create_sentiment_chart()
│   └── create_fear_greed_gauge()
├── data_queries.py        # Database queries and API calls
│   ├── get_latest_price()
│   ├── get_price_history()
│   ├── get_sentiment_summary()
│   ├── get_latest_articles()
│   ├── get_fear_greed_index()
│   └── get_exchange_rate()
├── __init__.py            # Package initialization
├── .streamlit/
│   └── config.toml        # Theme and server config
└── README.md              # This file
```

### Adding New Features

**New Data Source**:

1. Add query function to `data_queries.py`
2. Use `@st.cache_data` decorator with appropriate TTL
3. Return pandas DataFrame or dict
4. Import and call in `app.py`

```python
# In data_queries.py
@st.cache_data(ttl=300)
def get_new_data():
    """Fetch new data with 5-minute cache"""
    engine = get_db_engine()
    query = "SELECT * FROM new_table"
    return pd.read_sql_query(query, engine)

# In app.py
from dashboard.data_queries import get_new_data

def main():
    data = get_new_data()
    st.dataframe(data)
```

**New Chart**:

```python
import plotly.graph_objects as go

def create_new_chart(df):
    """Create custom Plotly chart"""
    fig = go.Figure()

    fig.add_trace(go.Scatter(
        x=df['time'],
        y=df['value'],
        mode='lines',
        name='My Data'
    ))

    fig.update_layout(
        template='plotly_dark',
        height=400,
        hovermode='x unified'
    )

    return fig

# In main()
st.plotly_chart(create_new_chart(data), use_container_width=True)
```

**New Sidebar Control**:

```python
# In main() sidebar section
with st.sidebar:
    my_option = st.selectbox(
        "My Setting",
        ["Option 1", "Option 2"],
        help="Description here"
    )
```

### Code Style Guidelines

- Follow PEP 8 conventions
- Use type hints for function parameters
- Add docstrings to all functions
- Cache expensive operations with `@st.cache_data`
- Use `st.spinner()` for long-running operations
- Handle errors gracefully with try/except
- Log important events (not in production dashboard)

### Performance Tips

**Database Queries**:

- Always use continuous aggregates instead of raw data
- Limit query results with WHERE clauses on time
- Use appropriate aggregate level for time range

**Caching**:

- Short TTL (10-60s) for frequently changing data
- Long TTL (1h+) for external APIs
- Clear cache strategically (Press `C`)

**UI Rendering**:

- Use `st.columns()` for side-by-side layout
- Minimize computations in main thread
- Lazy load data only when needed
- Use `st.empty()` for dynamic content

## Keyboard Shortcuts

While dashboard is active in browser:

- **C**: Clear cache and rerun
- **R**: Rerun application
- **Ctrl+C** (in terminal): Stop dashboard server

## Known Limitations

1. **Initial Load Time**: First launch may take 3-5 seconds to load data
2. **Timezone**: All times displayed in Singapore Time (GMT+8)
3. **Auto-Refresh**: Dashboard automatically refreshes every 60 seconds (aligned with price updates)
4. **Mobile Layout**: Optimized for desktop, limited mobile support
5. **Historical Sentiment**: Limited by free API tier (30-day NewsAPI limit)
6. **Browser Tab Inactive**: Auto-refresh may pause when tab is not focused (browser behavior)
7. **Static Data Mode**: Dashboard works without continuous updater but shows static pre-loaded data

## Future Enhancements

- [ ] Dark/Light theme toggle
- [ ] Custom price alerts with notifications
- [ ] Export charts as PNG/PDF
- [ ] Export data to CSV/Excel
- [ ] More technical indicators (RSI, MACD, Bollinger Bands, EMA)
- [ ] Historical Fear & Greed chart
- [ ] Multi-cryptocurrency support (ETH, BNB, etc.)
- [ ] Advanced news filtering (by source, sentiment threshold)
- [ ] User preferences persistence (local storage)
- [ ] WebSocket connection for real-time updates
- [ ] Mobile-responsive layout improvements
- [ ] Comparison view (current vs previous period)

## Support

For dashboard-specific issues:

1. Check terminal output where dashboard is running
2. Review browser console (Press `F12`) for errors
3. Verify dependencies: `pip list | grep -E "streamlit|plotly|pandas"`
4. Try: `streamlit cache clear`
5. Restart dashboard: `./bin/run_dashboard.sh`

For database or data issues, refer to main `README.md` and `COMPLETE_SETUP_GUIDE.md`.

## Resources

- **Streamlit Documentation**: https://docs.streamlit.io
- **Plotly Python**: https://plotly.com/python/
- **TimescaleDB**: https://docs.timescale.com
- **FinBERT Model**: https://huggingface.co/ProsusAI/finbert
- **Alternative.me API**: https://alternative.me/crypto/fear-and-greed-index

---

Last updated: October 2025
