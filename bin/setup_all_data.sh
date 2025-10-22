#!/bin/bash

# ============================================================================
# Complete Data Setup Script
# ============================================================================
# This script does ALL the data loading in one command:
# - Downloads historical price data
# - Pulls latest updates from Bitstamp
# - Loads data into TimescaleDB
# - Creates continuous aggregates
# - Optionally loads sentiment data
# ============================================================================

set -e

# Navigate to project root (parent of bin/)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_ROOT"

echo "============================================"
echo " Bitcoin Analytics - Complete Data Setup"
echo "============================================"
echo ""

# Check if virtual environment is active
if [ -d "venv" ]; then
    echo "Activating virtual environment..."
    source venv/bin/activate
elif [ -d ".venv" ]; then
    echo "Activating virtual environment..."
    source .venv/bin/activate
elif [ ! -z "$VIRTUAL_ENV" ]; then
    echo "Using existing virtual environment: $VIRTUAL_ENV"
elif [ ! -z "$CONDA_DEFAULT_ENV" ]; then
    echo "Using conda environment: $CONDA_DEFAULT_ENV"
fi

echo ""

# Check Docker and TimescaleDB
echo "Checking Docker and TimescaleDB..."
if ! docker ps | grep -q timescaledb; then
    echo "ERROR: TimescaleDB is not running"
    echo ""
    echo "Start it with:"
    echo "  docker start timescaledb"
    echo ""
    echo "Or create it with:"
    echo "  docker run -d --name timescaledb \\"
    echo "    -e POSTGRES_USER=postgres \\"
    echo "    -e POSTGRES_PASSWORD=pass \\"
    echo "    -e POSTGRES_DB=postgres \\"
    echo "    -p 5432:5432 \\"
    echo "    timescale/timescaledb:latest-pg17"
    exit 1
fi
echo "[OK] TimescaleDB is running"
echo ""

# Step 1: Download historical data
echo "============================================"
echo "Step 1/5: Downloading Historical Data"
echo "============================================"
echo "This downloads ~500MB from Kaggle..."
echo ""
python -m scripts.price.init_historical_price
echo ""
echo "[OK] Historical data downloaded"
echo ""

# Step 2: Pull latest updates
echo "============================================"
echo "Step 2/5: Pulling Latest Price Data"
echo "============================================"
echo "Fetching latest prices from Bitstamp API..."
echo ""
python -m scripts.price.backfill_price
echo ""
echo "[OK] Latest price data pulled"
echo ""

# Step 3: Load into database
echo "============================================"
echo "Step 3/5: Loading Data into TimescaleDB"
echo "============================================"
echo "This may take 3-10 minutes for full history..."
echo ""
python -m scripts.price.load_price
echo ""
echo "[OK] Price data loaded into database"
echo ""

# Step 4: Create continuous aggregates
echo "============================================"
echo "Step 4/5: Creating Continuous Aggregates"
echo "============================================"
echo "Creating time-based aggregates (1min, 5min, 1h, 1d, 1w, 1mo)..."
echo ""

for file in schema/aggregates/*.sql; do
    echo "  Creating $(basename $file)..."
    docker exec -i timescaledb psql -U postgres -d postgres < "$file" > /dev/null 2>&1 || true
done

echo ""
echo "[OK] Continuous aggregates created"
echo ""

# Step 5: Initialize whale monitoring database
echo "============================================"
echo "Step 5/6: Initializing Whale Monitoring"
echo "============================================"
echo "Setting up whale transaction tracking..."
echo ""

docker exec -i timescaledb psql -U postgres -d postgres < schema/init_whale_db.sql > /dev/null 2>&1

echo "[OK] Whale monitoring database initialized"
echo ""

# Step 6: Sentiment data (optional)
echo "============================================"
echo "Step 6/6: Sentiment Data (Optional)"
echo "============================================"
read -p "Do you want to load sentiment data? (y/n) " -n 1 -r
echo ""

if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo ""
    echo "Initializing sentiment database..."
    python -m scripts.news_sentiment.load_sentiment
    echo ""
    echo "Fetching and analyzing last 7 days of news..."
    echo "(This downloads FinBERT model ~400MB on first run)"
    echo ""
    python -m scripts.news_sentiment.update_sentiment --backfill 7
    echo ""
    echo "[OK] Sentiment data loaded"
else
    echo "Skipping sentiment data"
fi

echo ""
echo "============================================"
echo " Setup Complete!"
echo "============================================"
echo ""
echo "Verification:"

# Verify data
PRICE_COUNT=$(docker exec timescaledb psql -U postgres -d postgres -t -c "SELECT COUNT(*) FROM historical_price;" | xargs)
AGG_COUNT=$(docker exec timescaledb psql -U postgres -d postgres -t -c "SELECT COUNT(*) FROM timescaledb_information.continuous_aggregates WHERE view_name LIKE 'price_%';" | xargs)

echo "  [OK] Price records: $PRICE_COUNT"
echo "  [OK] Aggregates: $AGG_COUNT"
echo ""

echo "Next steps:"
echo ""
echo "1. Start continuous updates (Terminal 1):"
echo "   ./bin/start_updater.sh"
echo ""
echo "2. Start whale monitor (Terminal 2):"
echo "   python scripts/whale_monitor.py --min-btc 50"
echo "   (Or test first: python scripts/test_whale_monitor.py)"
echo ""
echo "3. Launch dashboard (Terminal 3):"
echo "   ./bin/run_dashboard.sh"
echo ""
echo "Dashboard will be available at: http://localhost:8501"
echo ""
echo "============================================"

