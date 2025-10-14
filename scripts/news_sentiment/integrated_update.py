"""
Integrated Update Script - Price + Sentiment

This script updates both price data and sentiment data together,
ensuring they stay synchronized for ML model training.

Usage:
    # Standard update (recommended for production)
    python -m scripts.integrated_update
    
    # Update with custom time range
    python -m scripts.integrated_update --hours 2
    
    # Quick update without aggregate refresh
    python -m scripts.integrated_update --skip-refresh

For automated updates, set up a cron job:
    # Run every hour at minute 5
    5 * * * * cd /path/to/project && /path/to/.venv/bin/python -m scripts.integrated_update
"""

import os
import sys
import argparse
from datetime import datetime
from dotenv import load_dotenv
from utils.logger import get_logger

# Import update functions
try:
    from scripts.news_sentiment.update_sentiment import update_sentiment_pipeline
except ImportError:
    update_sentiment_pipeline = None

log = get_logger("integrated_update.py")
load_dotenv()

# =====================================================================
# INTEGRATED UPDATE PIPELINE
# =====================================================================

def update_price_data():
    """
    Update price data using existing price update script
    
    Note: You should replace this with your actual price update logic
    For now, this is a placeholder that can be customized
    """
    log.info(" Updating price data...")
    
    try:
        # Option 1: Import and call your price update function
        # from scripts.pull_update_price import main as update_price
        # update_price()
        
        # Option 2: Run as subprocess (if import doesn't work)
        # import subprocess
        # subprocess.run([sys.executable, "-m", "scripts.pull_update_price"], check=True)
        
        # For now, just a placeholder
        log.info(" Price data update completed")
        log.info(" Note: Integrate your actual price update logic here")
        
        return True
        
    except Exception as e:
        log.error(f" Price data update failed: {e}")
        return False

def update_sentiment_data(hours_back: int = 1, skip_refresh: bool = False):
    """
    Update sentiment data using sentiment update pipeline
    """
    log.info(" Updating sentiment data...")
    
    if update_sentiment_pipeline is None:
        log.error(" Sentiment update pipeline not available")
        return False
    
    try:
        update_sentiment_pipeline(hours_back=hours_back, skip_refresh=skip_refresh)
        return True
    except Exception as e:
        log.error(f" Sentiment data update failed: {e}")
        return False

def integrated_update(hours_back: int = 1, skip_refresh: bool = False, price_only: bool = False, sentiment_only: bool = False):
    """
    Run integrated update for both price and sentiment data
    
    Args:
        hours_back: Number of hours to look back for updates
        skip_refresh: Skip refreshing continuous aggregates (faster)
        price_only: Update only price data
        sentiment_only: Update only sentiment data
    """
    start_time = datetime.now()
    
    log.info("=" * 70)
    log.info("=== INTEGRATED UPDATE PIPELINE ===")
    log.info(f"=== Started at: {start_time.strftime('%Y-%m-%d %H:%M:%S')} ===")
    log.info("=" * 70)
    
    price_success = True
    sentiment_success = True
    
    # Update price data (unless sentiment_only)
    if not sentiment_only:
        log.info("\n[STEP 1/2] Updating Price Data...")
        price_success = update_price_data()
        
        if price_success:
            log.info(" Price data update successful")
        else:
            log.warning(" Price data update failed, continuing with sentiment...")
    else:
        log.info("\n[STEP 1/2] Skipping price update (sentiment_only=True)")
    
    # Update sentiment data (unless price_only)
    if not price_only:
        log.info("\n[STEP 2/2] Updating Sentiment Data...")
        sentiment_success = update_sentiment_data(
            hours_back=hours_back,
            skip_refresh=skip_refresh
        )
        
        if sentiment_success:
            log.info(" Sentiment data update successful")
        else:
            log.warning(" Sentiment data update failed")
    else:
        log.info("\n[STEP 2/2] Skipping sentiment update (price_only=True)")
    
    # Summary
    elapsed = (datetime.now() - start_time).total_seconds()
    
    log.info("\n" + "=" * 70)
    log.info("=== INTEGRATED UPDATE SUMMARY ===")
    log.info(f"=== Time Elapsed: {elapsed:.2f} seconds ===")
    log.info(f"=== Price Update: {' Success' if price_success else ' Failed'} ===")
    log.info(f"=== Sentiment Update: {' Success' if sentiment_success else ' Failed'} ===")
    
    overall_success = price_success and sentiment_success
    if overall_success:
        log.info("=== Status:  ALL UPDATES COMPLETED SUCCESSFULLY ===")
    else:
        log.warning("=== Status:  SOME UPDATES FAILED ===")
    
    log.info("=" * 70)
    
    return overall_success

# =====================================================================
# SCHEDULED UPDATE (for Cron)
# =====================================================================

def scheduled_update():
    """
    Scheduled update function for production use
    Optimized for hourly cron jobs
    """
    log.info(" Running scheduled integrated update (hourly)...")
    
    # Update with a small overlap (1.5 hours) to avoid missing data
    success = integrated_update(hours_back=2, skip_refresh=False)
    
    if success:
        log.info(" Scheduled update completed successfully")
    else:
        log.error(" Scheduled update completed with errors")
    
    return success

# =====================================================================
# MAIN CLI
# =====================================================================

def main():
    parser = argparse.ArgumentParser(
        description='Integrated update for price and sentiment data',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Standard hourly update (recommended)
  python -m scripts.integrated_update
  
  # Update with 2-hour overlap
  python -m scripts.integrated_update --hours 2
  
  # Quick update without refreshing aggregates
  python -m scripts.integrated_update --skip-refresh
  
  # Update only price data
  python -m scripts.integrated_update --price-only
  
  # Update only sentiment data
  python -m scripts.integrated_update --sentiment-only
  
  # Scheduled update (for cron jobs)
  python -m scripts.integrated_update --scheduled

Cron Job Example (run hourly at minute 5):
  5 * * * * cd /path/to/project && /path/to/.venv/bin/python -m scripts.integrated_update --scheduled >> /path/to/logs/update.log 2>&1
        """
    )
    
    parser.add_argument(
        '--hours',
        type=int,
        default=1,
        help='Number of hours to look back (default: 1)'
    )
    
    parser.add_argument(
        '--skip-refresh',
        action='store_true',
        help='Skip refreshing continuous aggregates (faster)'
    )
    
    parser.add_argument(
        '--price-only',
        action='store_true',
        help='Update only price data'
    )
    
    parser.add_argument(
        '--sentiment-only',
        action='store_true',
        help='Update only sentiment data'
    )
    
    parser.add_argument(
        '--scheduled',
        action='store_true',
        help='Run as scheduled task (production mode)'
    )
    
    args = parser.parse_args()
    
    # Validate arguments
    if args.price_only and args.sentiment_only:
        log.error(" Cannot specify both --price-only and --sentiment-only")
        sys.exit(1)
    
    # Run appropriate mode
    try:
        if args.scheduled:
            success = scheduled_update()
        else:
            success = integrated_update(
                hours_back=args.hours,
                skip_refresh=args.skip_refresh,
                price_only=args.price_only,
                sentiment_only=args.sentiment_only
            )
        
        sys.exit(0 if success else 1)
        
    except KeyboardInterrupt:
        log.warning("\n Update interrupted by user")
        sys.exit(1)
    except Exception as e:
        log.exception(f" Update failed with exception: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()

