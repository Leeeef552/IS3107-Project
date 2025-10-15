"""
Continuous Data Updater

This script runs in the background and continuously updates:
1. Bitcoin price data (every 60 seconds from Bitstamp)
2. News sentiment data:
   - Every 5 minutes: Incremental updates (2 hours lookback)
   - Every 12 hours: Full refresh (30 days lookback)

Usage:
    python -m scripts.continuous_updater [--interval SECONDS]
    
Options:
    --interval    Update interval in seconds (default: 60 = 1 minute)
"""

import time
import sys
import argparse
import pandas as pd
import psycopg2
from datetime import datetime, timedelta
from io import StringIO
from utils.logger import get_logger
from scripts.price.backfill_price import backfill_price
from configs.config import DB_CONFIG, PARQUET_PATH

log = get_logger("continuous_updater")


def load_new_price_data_only(parquet_path=PARQUET_PATH):
    """
    Load only NEW price data that doesn't exist in database yet
    Much faster than reloading everything
    """
    try:
        # Connect to database
        conn = psycopg2.connect(**DB_CONFIG)
        cur = conn.cursor()
        
        # Get the latest timestamp in database
        cur.execute("SELECT MAX(time) FROM historical_price;")
        latest_db_time = cur.fetchone()[0]
        
        if latest_db_time is None:
            log.warning("No data in database, loading full dataset...")
            from scripts.price.load_price import load_price
            return load_price(parquet_path=parquet_path)
        
        # Load parquet and filter for new data only
        df = pd.read_parquet(parquet_path)
        df["Timestamp"] = pd.to_datetime(df["Timestamp"], unit="s")
        df.rename(columns={
            "Timestamp": "time",
            "Open": "open",
            "High": "high",
            "Low": "low",
            "Close": "close",
            "Volume": "volume"
        }, inplace=True)
        
        # Convert both to timezone-naive for comparison
        if latest_db_time.tzinfo is not None:
            # Database time is timezone-aware, convert to naive
            latest_db_time = latest_db_time.replace(tzinfo=None)
        
        # Ensure df['time'] is also timezone-naive
        if df['time'].dt.tz is not None:
            df['time'] = df['time'].dt.tz_localize(None)
        
        # Filter only new data
        df_new = df[df['time'] > latest_db_time].sort_values('time')
        
        if df_new.empty:
            log.info("No new data to insert")
            conn.close()
            return "No new data"
        
        # Insert only new data
        output = StringIO()
        df_new.to_csv(output, sep="\t", header=False, index=False)
        output.seek(0)
        
        cur.copy_from(output, "historical_price", sep="\t", null="\\N")
        conn.commit()
        
        log.info(f"Inserted {len(df_new):,} new rows (latest: {df_new['time'].max()})")
        
        cur.close()
        conn.close()
        
        return f"Inserted {len(df_new):,} new rows"
        
    except Exception as e:
        log.error(f"Error loading new data: {str(e)}")
        raise


def update_news_sentiment_incremental(hours_back=2):
    """
    Fetch and analyze only NEW news articles (not already in database)
    Much faster than reprocessing everything
    
    Args:
        hours_back: Number of hours to look back for articles (default: 2)
    """
    try:
        from scripts.news_sentiment.fetch_news import NewsAggregator
        from scripts.news_sentiment.analyze_sentiment import SentimentAnalyzer, analyze_articles
        from scripts.news_sentiment.load_sentiment import (
            bulk_insert_articles_with_sentiment,
            get_db_config,
            connect_to_db,
            refresh_continuous_aggregates
        )
        
        # Fetch news from specified time period
        aggregator = NewsAggregator()
        articles = aggregator.fetch_all(hours_back=hours_back)
        
        if not articles:
            log.info("No new articles found from news sources")
            return "No new articles"
        
        # Connect to database to check which articles are NEW
        db_config = get_db_config()
        conn = connect_to_db(db_config)
        cur = conn.cursor()
        
        # Get existing URLs
        urls = [a['url'] for a in articles if a.get('url')]
        if not urls:
            cur.close()
            conn.close()
            return "No valid article URLs"
        
        placeholders = ','.join(['%s'] * len(urls))
        cur.execute(f"SELECT url FROM news_articles WHERE url IN ({placeholders})", urls)
        existing_urls = {row[0] for row in cur.fetchall()}
        cur.close()
        
        # Filter for only NEW articles
        new_articles = [a for a in articles if a.get('url') not in existing_urls]
        
        if not new_articles:
            log.info(f"All {len(articles)} articles already in database")
            conn.close()
            return f"No new articles (checked {len(articles)})"
        
        log.info(f"Found {len(new_articles)} new articles (out of {len(articles)} total)")
        
        # Analyze sentiment for new articles only
        analyzer = SentimentAnalyzer()
        analyzed_articles = analyze_articles(new_articles, analyzer)
        
        # Store in database
        success_count = bulk_insert_articles_with_sentiment(conn, analyzed_articles)
        
        # Refresh continuous aggregates
        refresh_continuous_aggregates(conn)
        
        conn.close()
        
        log.info(f"✓ Stored {success_count} new articles with sentiment")
        return f"Added {success_count} new articles"
        
    except Exception as e:
        log.error(f"Error updating news sentiment: {str(e)}")
        return f"Error: {str(e)}"


def continuous_update(interval=60):
    """
    Continuously update price data at specified intervals
    
    Args:
        interval: Time between updates in seconds (default: 60 = 1 minute)
    """
    log.info(f"Starting continuous price data updater (interval: {interval}s)")
    log.info("Press Ctrl+C to stop")
    
    update_count = 0
    
    try:
        while True:
            update_count += 1
            log.info(f"\n{'='*60}")
            log.info(f"Update #{update_count} - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            log.info(f"{'='*60}")
            
            try:
                # Step 1: Pull latest price data from Bitstamp
                log.info("Step 1: Pulling latest price data from Bitstamp...")
                parquet_path = backfill_price()
                
                # Step 2: Load ONLY NEW price data into TimescaleDB (much faster!)
                log.info("Step 2: Loading NEW price data into TimescaleDB...")
                result = load_new_price_data_only(parquet_path=parquet_path)
                log.info(f"✓ {result}")
                
                # Step 3: Update news sentiment
                # - Every 5 minutes: Fetch recent articles (2 hours lookback)
                # - Every 12 hours: Refresh full 30-day dataset
                if update_count % 720 == 1:  # Every 12 hours (first update and then every 720)
                    log.info("Step 3: Full refresh - fetching 30 days of news sentiment...")
                    news_result = update_news_sentiment_incremental(hours_back=720)
                    log.info(f"✓ {news_result}")
                elif update_count % 5 == 0:  # Every 5 updates (5 minutes at 60s interval)
                    log.info("Step 3: Incremental update - checking for new articles...")
                    news_result = update_news_sentiment_incremental(hours_back=2)
                    log.info(f"✓ {news_result}")
                
                log.info(f"Update completed successfully. Next update in {interval}s...")
                
            except Exception as e:
                log.error(f"Error during update: {str(e)}")
                log.info("Continuing despite error...")
            
            # Wait for next update
            time.sleep(interval)
            
    except KeyboardInterrupt:
        log.info("\n\nStopping continuous updater...")
        log.info(f"Total updates performed: {update_count}")
        sys.exit(0)


def main():
    """Main entry point with argument parsing"""
    parser = argparse.ArgumentParser(
        description='Continuous Bitcoin price data updater',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument(
        '--interval',
        type=int,
        default=60,
        help='Update interval in seconds (default: 60 = 1 minute)'
    )
    
    args = parser.parse_args()
    
    # Validate interval
    if args.interval < 30:
        log.warning("Interval less than 30 seconds may cause API rate limiting!")
        log.warning("Recommended minimum: 60 seconds")
    
    continuous_update(interval=args.interval)


if __name__ == "__main__":
    main()

