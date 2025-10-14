"""
Update All Sentiment Intervals at Once
Updates 1h, 1d, 1w, and 1mo intervals
"""

import sys
from scripts.news_sentiment.update_sentiment import update_sentiment_pipeline
from utils.logger import get_logger

log = get_logger("update_all_intervals.py")

INTERVALS = {
    '1h': 6,      # 6 hours
    '1d': 168,    # 7 days  
    '1w': 672,    # 28 days (4 weeks)
    '1mo': 4320   # 180 days (6 months)
}

def update_all_intervals():
    """Update sentiment data for all time intervals"""
    
    print("\n" + "="*80)
    print("UPDATING ALL SENTIMENT INTERVALS")
    print("="*80 + "\n")
    
    # Find the maximum hours needed
    max_hours = max(INTERVALS.values())
    
    print(f"Fetching news from last {max_hours} hours ({max_hours//24} days)...")
    print("This covers all intervals: 1h, 1d, 1w, 1mo")
    print("\nThis may take a few minutes...\n")
    
    try:
        # Single update with maximum lookback period
        # This will populate all continuous aggregates
        update_sentiment_pipeline(
            hours_back=max_hours,
            skip_refresh=False
        )
        
        print("\n" + "="*80)
        print("ALL INTERVALS UPDATED SUCCESSFULLY!")
        print("="*80)
        print("\nYou can now view each interval:")
        print("  Hourly (6h):    python -m scripts.update_interval_sentiment --interval 1h --view")
        print("  Daily (7d):     python -m scripts.update_interval_sentiment --interval 1d --view")
        print("  Weekly (4w):    python -m scripts.update_interval_sentiment --interval 1w --view")
        print("  Monthly (6mo):  python -m scripts.update_interval_sentiment --interval 1mo --view")
        print("\nOr view summary: python -m scripts.view_sentiment_summary")
        print("="*80 + "\n")
        
    except Exception as e:
        log.error(f"Failed to update intervals: {e}")
        sys.exit(1)

if __name__ == "__main__":
    update_all_intervals()

