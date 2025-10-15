#!/bin/bash

# ============================================================================
# Bitcoin Analytics Dashboard Launcher
# ============================================================================
# Launches the Streamlit dashboard for Bitcoin price and sentiment analysis.
#
# Prerequisites:
# - TimescaleDB running in Docker
# - Price and sentiment data loaded
# - Python dependencies installed
#
# Usage:
#   ./run_dashboard.sh [port]
#
# Examples:
#   ./run_dashboard.sh          # Launch on default port 8501
#   ./run_dashboard.sh 8502     # Launch on custom port 8502
# ============================================================================

set -e

# Navigate to project root (parent of bin/)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_ROOT"

# Default port
PORT=${1:-8501}

echo "=========================================="
echo " Bitcoin Analytics Dashboard"
echo "=========================================="
echo ""

# Check if virtual environment exists and activate
if [ -d "venv" ]; then
    echo "Activating virtual environment (venv)..."
    source venv/bin/activate
elif [ -d ".venv" ]; then
    echo "Activating virtual environment (.venv)..."
    source .venv/bin/activate
elif [ ! -z "$VIRTUAL_ENV" ]; then
    echo "Using existing virtual environment: $VIRTUAL_ENV"
elif [ ! -z "$CONDA_DEFAULT_ENV" ]; then
    echo "Using conda environment: $CONDA_DEFAULT_ENV"
else
    echo "Warning: No virtual environment detected"
    echo "Consider creating one: python -m venv venv"
    read -p "Continue anyway? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

echo ""

# Pre-flight checks
echo "Running pre-flight checks..."

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo "ERROR: Docker is not running"
    echo "Please start Docker Desktop and try again"
    exit 1
fi
echo "[OK] Docker is running"

# Check if TimescaleDB container exists and is running
if ! docker ps | grep -q timescaledb; then
    echo "ERROR: TimescaleDB container is not running"
    echo ""
    echo "To start TimescaleDB:"
    echo "  docker start timescaledb"
    echo ""
    echo "Or create a new container:"
    echo "  docker run -d --name timescaledb \\"
    echo "    -e POSTGRES_USER=postgres \\"
    echo "    -e POSTGRES_PASSWORD=pass \\"
    echo "    -e POSTGRES_DB=postgres \\"
    echo "    -p 5432:5432 \\"
    echo "    timescale/timescaledb:latest-pg17"
    exit 1
fi
echo "[OK] TimescaleDB is running"

# Check if database has data
DATA_CHECK=$(docker exec timescaledb psql -U postgres -d postgres -t -c "SELECT COUNT(*) FROM historical_price LIMIT 1;" 2>&1)
if [[ $DATA_CHECK =~ "does not exist" ]] || [[ $DATA_CHECK =~ "ERROR" ]]; then
    echo "WARNING: No price data found in database"
    echo ""
    echo "To load initial data:"
    echo "  python -m scripts.init_historical_price"
    echo "  python -m scripts.price.pull_update_price"
    echo "  python -m scripts.load_price"
    echo ""
    read -p "Continue anyway? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
else
    echo "[OK] Price data available"
fi

# Check if port is already in use
if lsof -Pi :$PORT -sTCP:LISTEN -t > /dev/null 2>&1; then
    echo "WARNING: Port $PORT is already in use"
    echo ""
    PID=$(lsof -ti:$PORT)
    echo "Process using port: $(ps -p $PID -o comm=) (PID: $PID)"
    echo ""
    read -p "Kill existing process and continue? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        kill -9 $PID
        echo "Process killed"
    else
        echo "Try using a different port: ./run_dashboard.sh 8502"
        exit 1
    fi
fi
echo "[OK] Port $PORT is available"

echo ""
echo "=========================================="
echo " Starting Dashboard"
echo "=========================================="
echo ""
echo "Dashboard will open at: http://localhost:$PORT"
echo ""
echo "Features:"
echo "  - Real-time Bitcoin price"
echo "  - Interactive price charts"
echo "  - News sentiment analysis"
echo "  - Fear & Greed Index"
echo "  - Currency selector (USD/SGD)"
echo ""
echo "Tips:"
echo "  - Press 'c' in dashboard to clear cache"
echo "  - Press 'r' in dashboard to rerun"
echo "  - Press Ctrl+C here to stop the dashboard"
echo ""
echo "For real-time updates, start the continuous updater:"
echo "  ./start_updater.sh"
echo ""
echo "=========================================="
echo ""

# Launch Streamlit
streamlit run dashboard/app.py \
  --server.port=$PORT \
  --server.headless=true \
  --browser.gatherUsageStats=false
