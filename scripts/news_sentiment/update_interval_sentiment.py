"""
Update and View Sentiment for Specific Time Intervals
Supports: 1h, 1d, 1w, 1mo
"""

import os
import sys
import argparse
import psycopg2
from datetime import datetime
from dotenv import load_dotenv
from tabulate import tabulate

from scripts.news_sentiment.update_sentiment import update_sentiment_pipeline
from scripts.news_sentiment.load_sentiment import get_db_config

load_dotenv()

# Define lookback periods for each interval
INTERVAL_CONFIG = {
    '1h': {
        'name': 'Hourly',
        'table': 'sentiment_1h',
        'lookback': '6 hours',
        'fetch_hours': 6,
        'description': 'Last 6 hours, broken down per hour'
    },
    '1d': {
        'name': 'Daily',
        'table': 'sentiment_1d',
        'lookback': '7 days',
        'fetch_hours': 168,  # 7 days
        'description': 'Last 7 days, broken down per day'
    },
    '1w': {
        'name': 'Weekly',
        'table': 'sentiment_1w',
        'lookback': '4 weeks',
        'fetch_hours': 672,  # 28 days
        'description': 'Last 4 weeks, broken down per week'
    },
    '1mo': {
        'name': 'Monthly',
        'table': 'sentiment_1mo',
        'lookback': '6 months',
        'fetch_hours': 4320,  # 180 days
        'description': 'Last 6 months, broken down per month'
    }
}

def view_interval_sentiment(interval: str):
    """
    View sentiment data for a specific time interval
    
    Args:
        interval: '1h', '1d', '1w', or '1mo'
    """
    if interval not in INTERVAL_CONFIG:
        print(f"Error: Invalid interval '{interval}'. Choose from: 1h, 1d, 1w, 1mo")
        return
    
    config = INTERVAL_CONFIG[interval]
    
    print("\n" + "="*80)
    print(f"{config['name'].upper()} SENTIMENT ANALYSIS")
    print(f"{config['description']}")
    print("="*80 + "\n")
    
    db_config = get_db_config()
    conn = psycopg2.connect(**db_config)
    cur = conn.cursor()
    
    # Query based on interval
    if interval == '1h':
        query = """
            SELECT 
                TO_CHAR(bucket, 'Mon DD HH24:MI') as time_label,
                bucket,
                article_count,
                ROUND(avg_sentiment::numeric, 3) as sentiment,
                ROUND(weighted_sentiment::numeric, 3) as weighted,
                ROUND(sentiment_volatility::numeric, 3) as volatility,
                positive_count,
                negative_count,
                neutral_count,
                ROUND(avg_confidence::numeric, 3) as confidence
            FROM sentiment_1h
            WHERE bucket > NOW() - INTERVAL %s
            ORDER BY bucket DESC
        """
    elif interval == '1d':
        query = """
            SELECT 
                TO_CHAR(bucket, 'Mon DD, YYYY') as time_label,
                bucket,
                article_count,
                ROUND(avg_sentiment::numeric, 3) as sentiment,
                ROUND(weighted_sentiment::numeric, 3) as weighted,
                ROUND(sentiment_volatility::numeric, 3) as volatility,
                positive_count,
                negative_count,
                neutral_count,
                ROUND(avg_confidence::numeric, 3) as confidence
            FROM sentiment_1d
            WHERE bucket > NOW() - INTERVAL %s
            ORDER BY bucket DESC
        """
    elif interval == '1w':
        query = """
            SELECT 
                TO_CHAR(bucket, 'Mon DD, YYYY') as time_label,
                bucket,
                article_count,
                ROUND(avg_sentiment::numeric, 3) as sentiment,
                ROUND(weighted_sentiment::numeric, 3) as weighted,
                ROUND(sentiment_volatility::numeric, 3) as volatility,
                positive_count,
                negative_count,
                neutral_count,
                ROUND(avg_confidence::numeric, 3) as confidence
            FROM sentiment_1w
            WHERE bucket > NOW() - INTERVAL %s
            ORDER BY bucket DESC
        """
    else:  # 1mo
        query = """
            SELECT 
                TO_CHAR(bucket, 'Mon YYYY') as time_label,
                bucket,
                article_count,
                ROUND(avg_sentiment::numeric, 3) as sentiment,
                ROUND(weighted_sentiment::numeric, 3) as weighted,
                ROUND(sentiment_volatility::numeric, 3) as volatility,
                positive_count,
                negative_count,
                neutral_count,
                ROUND(avg_confidence::numeric, 3) as confidence
            FROM sentiment_1mo
            WHERE bucket > NOW() - INTERVAL %s
            ORDER BY bucket DESC
        """
    
    cur.execute(query, (config['lookback'],))
    results = cur.fetchall()
    
    if not results:
        print(f"No data available for {config['name']} interval yet.")
        print(f"Run: python -m scripts.update_interval_sentiment --interval {interval} --update")
        cur.close()
        conn.close()
        return
    
    # Display results with standardized columns
    # Format: Time, Articles, Sentiment, Volatility, Positive, Negative, Neutral, Confidence
    display_data = []
    for row in results:
        display_data.append([
            row[0],  # time_label
            row[2],  # article_count
            row[3],  # sentiment
            row[5],  # volatility
            row[6],  # positive_count
            row[7],  # negative_count
            row[8],  # neutral_count
            row[9]   # confidence
        ])
    
    headers = [
        "Time", "Articles", "Sentiment", "Volatility", 
        "Positive", "Negative", "Neutral", "Confidence"
    ]
    print(tabulate(display_data, headers=headers, tablefmt="grid"))
    
    # Summary statistics
    print(f"\n{config['name'].upper()} SUMMARY")
    print("-" * 80)
    
    cur.execute(f"""
        SELECT 
            COUNT(*) as periods,
            SUM(article_count) as total_articles,
            ROUND(AVG(avg_sentiment)::numeric, 3) as avg_sentiment,
            ROUND(MIN(avg_sentiment)::numeric, 3) as min_sentiment,
            ROUND(MAX(avg_sentiment)::numeric, 3) as max_sentiment,
            ROUND(AVG(sentiment_volatility)::numeric, 3) as avg_volatility,
            SUM(positive_count) as total_positive,
            SUM(negative_count) as total_negative,
            SUM(neutral_count) as total_neutral
        FROM {config['table']}
        WHERE bucket > NOW() - INTERVAL %s
    """, (config['lookback'],))
    
    summary = cur.fetchone()
    if summary:
        periods, total_articles, avg_sent, min_sent, max_sent, avg_vol, pos, neg, neu = summary
        
        print(f"Time Periods: {periods}")
        print(f"Total Articles: {total_articles}")
        print(f"Average Sentiment: {avg_sent} (Range: {min_sent} to {max_sent})")
        print(f"Average Volatility: {avg_vol}")
        print(f"Distribution: {pos} Positive, {neg} Negative, {neu} Neutral")
        
        # Trend analysis
        if avg_sent > 0.3:
            trend = "BULLISH"
        elif avg_sent < -0.3:
            trend = "BEARISH"
        else:
            trend = "NEUTRAL"
        
        print(f"\nMarket Sentiment: {trend}")
    
    print("\n" + "="*80 + "\n")
    
    cur.close()
    conn.close()

def update_and_view(interval: str, update_only: bool = False):
    """
    Update sentiment data and optionally view results
    
    Args:
        interval: '1h', '1d', '1w', or '1mo'
        update_only: If True, only update without viewing
    """
    if interval not in INTERVAL_CONFIG:
        print(f"Error: Invalid interval '{interval}'. Choose from: 1h, 1d, 1w, 1mo")
        return
    
    config = INTERVAL_CONFIG[interval]
    
    print(f"\nUpdating {config['name']} sentiment data...")
    print(f"Fetching news from last {config['fetch_hours']} hours...\n")
    
    # Update sentiment data
    try:
        update_sentiment_pipeline(
            hours_back=config['fetch_hours'],
            skip_refresh=False
        )
        
        if not update_only:
            print("\n" + "="*80)
            print("Update completed! Viewing results...")
            print("="*80)
            view_interval_sentiment(interval)
        else:
            print(f"\n{config['name']} sentiment data updated successfully!")
            print(f"View results with: python -m scripts.update_interval_sentiment --interval {interval} --view")
            
    except Exception as e:
        print(f"Error updating sentiment: {e}")
        sys.exit(1)

def main():
    parser = argparse.ArgumentParser(
        description='Update and view sentiment for specific time intervals',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Time Intervals and Lookback Periods:
  1h   - Hourly:   Last 6 hours, broken down per hour
  1d   - Daily:    Last 7 days, broken down per day
  1w   - Weekly:   Last 4 weeks, broken down per week
  1mo  - Monthly:  Last 6 months, broken down per month

Examples:
  # Update hourly sentiment and view last 6 hours
  python -m scripts.update_interval_sentiment --interval 1h --update

  # Update daily sentiment and view last 7 days
  python -m scripts.update_interval_sentiment --interval 1d --update

  # Just view weekly sentiment (no update)
  python -m scripts.update_interval_sentiment --interval 1w --view

  # Update all intervals
  python -m scripts.update_interval_sentiment --interval 1h --update
  python -m scripts.update_interval_sentiment --interval 1d --update
  python -m scripts.update_interval_sentiment --interval 1w --update
  python -m scripts.update_interval_sentiment --interval 1mo --update
        """
    )
    
    parser.add_argument(
        '--interval',
        choices=['1h', '1d', '1w', '1mo'],
        required=True,
        help='Time interval: 1h (hourly), 1d (daily), 1w (weekly), 1mo (monthly)'
    )
    
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        '--update',
        action='store_true',
        help='Update sentiment data and view results'
    )
    group.add_argument(
        '--view',
        action='store_true',
        help='View existing sentiment data (no update)'
    )
    
    parser.add_argument(
        '--update-only',
        action='store_true',
        help='Update data without viewing results'
    )
    
    args = parser.parse_args()
    
    if args.view:
        view_interval_sentiment(args.interval)
    elif args.update:
        update_and_view(args.interval, update_only=args.update_only)

if __name__ == "__main__":
    main()

