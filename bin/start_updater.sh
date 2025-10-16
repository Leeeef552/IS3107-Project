#!/bin/bash

# ============================================================================
# Bitcoin Price Data Continuous Updater Launcher
# ============================================================================
# This script starts the background price data updater that continuously
# fetches and loads Bitcoin price data into TimescaleDB.
#
# Usage:
#   ./bin/start_updater.sh [interval_seconds]
#
# Example:
#   ./bin/start_updater.sh          # Update every 1 minute (default)
#   ./bin/start_updater.sh 30       # Update every 30 seconds
#   ./bin/start_updater.sh 120      # Update every 2 minutes
# ============================================================================

set -e

# Navigate to project root (parent of bin/)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_ROOT"

# Default interval: 1 minute (60 seconds)
INTERVAL=${1:-60}

echo "========================================"
echo "Bitcoin Price Data Continuous Updater"
echo "========================================"
echo ""
echo "Update interval: ${INTERVAL} seconds"
echo ""

# Check if virtual environment exists
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
else
    echo "Warning: No virtual environment detected"
    read -p "Continue anyway? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# Check if database is running
echo ""
echo "Checking database connection..."
if ! docker exec timescaledb psql -U postgres -d postgres -c "SELECT 1;" > /dev/null 2>&1; then
    echo "ERROR: Cannot connect to TimescaleDB"
    echo "Make sure Docker is running and TimescaleDB container is started"
    exit 1
fi
echo "[OK] Database connection OK"

echo ""
echo "Starting continuous updater..."
echo "Press Ctrl+C to stop"
echo ""

# Run the updater
python -m scripts.continuous_updater --interval "$INTERVAL"

