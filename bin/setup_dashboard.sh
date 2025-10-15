#!/bin/bash

# Bitcoin Analytics Dashboard - Automated Setup Script
# This script automates the setup process

set -e  # Exit on error

# Navigate to project root (parent of bin/)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_ROOT"

echo "=========================================="
echo "Bitcoin Analytics Dashboard Setup"
echo "=========================================="
echo ""

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print status messages
print_status() {
    echo -e "${GREEN}[OK]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_step() {
    echo ""
    echo "=========================================="
    echo "$1"
    echo "=========================================="
}

# Check if running from project directory
if [ ! -f "requirements.txt" ]; then
    print_error "Please run this script from the project root directory"
    exit 1
fi

# Step 1: Check Docker
print_step "Step 1: Checking Docker"
if ! command -v docker &> /dev/null; then
    print_error "Docker is not installed. Please install Docker first."
    exit 1
fi
print_status "Docker is installed"

# Step 2: Check/Start TimescaleDB
print_step "Step 2: Setting up TimescaleDB"
if docker ps | grep -q timescaledb; then
    print_status "TimescaleDB container is already running"
else
    if docker ps -a | grep -q timescaledb; then
        print_warning "TimescaleDB container exists but is not running. Starting it..."
        docker start timescaledb
        print_status "TimescaleDB started"
    else
        print_warning "Creating new TimescaleDB container..."
        docker run -d --name timescaledb \
            -e POSTGRES_USER=postgres \
            -e POSTGRES_PASSWORD=pass \
            -e POSTGRES_DB=postgres \
            -p 5432:5432 \
            timescale/timescaledb:latest-pg17
        print_status "TimescaleDB container created and started"
        sleep 5  # Wait for database to be ready
    fi
fi

# Wait for database to be ready
print_warning "Waiting for database to be ready..."
sleep 3

# Step 3: Python Environment
print_step "Step 3: Checking Python Environment"
if [[ -n "$VIRTUAL_ENV" ]] || [[ -n "$CONDA_DEFAULT_ENV" ]]; then
    if [[ -n "$CONDA_DEFAULT_ENV" ]]; then
        print_status "Using existing conda environment: $CONDA_DEFAULT_ENV"
    else
        print_status "Using existing virtual environment: $VIRTUAL_ENV"
    fi
else
    print_warning "No virtual environment detected"
    if [ ! -d ".venv" ]; then
        print_warning "Creating virtual environment..."
        python3 -m venv .venv
        print_status "Virtual environment created"
    else
        print_status "Virtual environment already exists"
    fi
    # Activate virtual environment
    source .venv/bin/activate
    print_status "Virtual environment activated"
fi

# Step 4: Install Dependencies
print_step "Step 4: Installing Dependencies"
print_warning "This may take 5-10 minutes..."
pip install --upgrade pip > /dev/null 2>&1
pip install -r requirements.txt
print_status "All dependencies installed"

# Step 5: Check .env file
print_step "Step 5: Checking Configuration"
if [ ! -f ".env" ]; then
    print_warning "Creating .env file from template..."
    cp env.example .env
    print_warning ".env file created. Please edit it with your API keys:"
    echo "  - NEWS_API_KEY (from https://newsapi.org/register)"
    echo "  - CRYPTOCOMPARE_API_KEY (from https://www.cryptocompare.com/cryptopian/api-keys)"
    echo "  - REDDIT_CLIENT_ID and REDDIT_CLIENT_SECRET (from https://www.reddit.com/prefs/apps)"
    echo ""
    read -p "Press Enter after you've updated the .env file with your API keys..."
else
    print_status ".env file exists"
fi

# Step 6: Load Price Data
print_step "Step 6: Loading Historical Price Data"
read -p "Do you want to download and load historical price data? This will take 5-10 minutes. (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    print_warning "Downloading historical data from Kaggle..."
    python -m scripts.price.init_historical_price
    print_status "Historical data downloaded"
    
    print_warning "Updating to latest prices..."
    python -m scripts.price.pull_update_price
    print_status "Price data updated"
    
    print_warning "Loading data into database..."
    python -m scripts.load_price
    print_status "Price data loaded into TimescaleDB"
else
    print_warning "Skipping price data loading"
fi

# Step 7: Load Sentiment Data
print_step "Step 7: Setting up Sentiment Analysis"
read -p "Do you want to set up sentiment analysis? This will take 5-10 minutes. (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    print_warning "Initializing sentiment database..."
    python -m scripts.news_sentiment.load_sentiment
    print_status "Sentiment database initialized"
    
    print_warning "Fetching and analyzing news articles (last 7 days)..."
    print_warning "First run will download ML models (~400MB)..."
    python -m scripts.news_sentiment.update_sentiment --backfill 7
    print_status "Sentiment data loaded"
else
    print_warning "Skipping sentiment analysis setup"
fi

# Step 8: Verify Setup
print_step "Step 8: Verifying Setup"
print_warning "Checking database contents..."

# Check price data
PRICE_COUNT=$(docker exec timescaledb psql -U postgres -d postgres -t -c "SELECT COUNT(*) FROM historical_price;" 2>/dev/null || echo "0")
if [ "$PRICE_COUNT" -gt 0 ]; then
    print_status "Price data: $PRICE_COUNT rows"
else
    print_warning "Price data: No data found"
fi

# Check sentiment data
ARTICLE_COUNT=$(docker exec timescaledb psql -U postgres -d postgres -t -c "SELECT COUNT(*) FROM news_articles;" 2>/dev/null || echo "0")
if [ "$ARTICLE_COUNT" -gt 0 ]; then
    print_status "News articles: $ARTICLE_COUNT rows"
else
    print_warning "News articles: No data found"
fi

# Final Step: Launch Dashboard
print_step "Setup Complete!"
echo ""
echo "Your Bitcoin Analytics Dashboard is ready!"
echo ""
echo "To launch the dashboard, run:"
echo "  ./run_dashboard.sh"
echo ""
echo "Or:"
echo "  streamlit run dashboard/app.py"
echo ""
echo "The dashboard will open at: http://localhost:8501"
echo ""

read -p "Do you want to launch the dashboard now? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    print_status "Launching dashboard..."
    streamlit run dashboard/app.py
else
    print_status "Setup complete! Run './run_dashboard.sh' when ready."
fi

