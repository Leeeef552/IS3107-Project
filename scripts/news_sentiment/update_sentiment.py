"""
Integrated News Sentiment Update Script
Fetches news, analyzes sentiment, and stores in database

This script should be run periodically (e.g., every hour) to keep
sentiment data synchronized with price updates.

Usage:
    python -m scripts.update_sentiment --hours 1
    python -m scripts.update_sentiment --hours 24  # backfill last 24h
"""

import os
import argparse
from datetime import datetime
from dotenv import load_dotenv

from scripts.news_sentiment.fetch_news import NewsAggregator
from scripts.news_sentiment.analyze_sentiment import SentimentAnalyzer, analyze_articles
from scripts.news_sentiment.load_sentiment import (
    get_db_config, 
    connect_to_db, 
    bulk_insert_articles_with_sentiment,
    refresh_continuous_aggregates
)
from utils.logger import get_logger

log = get_logger("update_sentiment.py")
load_dotenv()

# =====================================================================
# MAIN UPDATE PIPELINE
# =====================================================================
def update_sentiment_pipeline(hours_back: int = 1, skip_refresh: bool = False):
    """
    Complete pipeline: Fetch news → Analyze sentiment → Store in DB
    
    Args:
        hours_back: Number of hours to look back for news
        skip_refresh: Skip refreshing continuous aggregates (faster for testing)
    """
    log.info("=" * 70)
    log.info("=== NEWS SENTIMENT UPDATE PIPELINE ===")
    log.info(f"=== Time Range: Last {hours_back} hour(s) ===")
    log.info("=" * 70)
    
    start_time = datetime.now()
    
    try:
        # -----------------------------------------------------------------
        # STEP 1: Fetch News from Multiple Sources
        # -----------------------------------------------------------------
        log.info("\n[STEP 1/4]  Fetching news from multiple sources...")
        
        aggregator = NewsAggregator()
        articles = aggregator.fetch_all(hours_back=hours_back)
        
        if not articles:
            log.warning(" No articles fetched. Exiting.")
            return
        
        log.info(f" Fetched {len(articles)} unique articles")
        
        # -----------------------------------------------------------------
        # STEP 2: Analyze Sentiment using FinBERT
        # -----------------------------------------------------------------
        log.info("\n[STEP 2/4]  Analyzing sentiment with FinBERT...")
        
        analyzer = SentimentAnalyzer()
        articles_with_sentiment = analyze_articles(articles, analyzer)
        
        log.info(f" Analyzed sentiment for {len(articles_with_sentiment)} articles")
        
        # -----------------------------------------------------------------
        # STEP 3: Store in Database
        # -----------------------------------------------------------------
        log.info("\n[STEP 3/4]  Storing in TimescaleDB...")
        
        db_config = get_db_config()
        conn = connect_to_db(db_config)
        
        success_count = bulk_insert_articles_with_sentiment(conn, articles_with_sentiment)
        
        log.info(f" Stored {success_count} articles with sentiment in database")
        
        # -----------------------------------------------------------------
        # STEP 4: Refresh Continuous Aggregates
        # -----------------------------------------------------------------
        if not skip_refresh:
            log.info("\n[STEP 4/4]  Refreshing continuous aggregates...")
            refresh_continuous_aggregates(conn)
            log.info(" Aggregates refreshed")
        else:
            log.info("\n[STEP 4/4] Skipping aggregate refresh")
        
        conn.close()
        
        # -----------------------------------------------------------------
        # Summary
        # -----------------------------------------------------------------
        elapsed = (datetime.now() - start_time).total_seconds()
        
        log.info("\n" + "=" * 70)
        log.info("=== PIPELINE COMPLETED SUCCESSFULLY ===")
        log.info(f"=== Time Elapsed: {elapsed:.2f} seconds ===")
        log.info(f"=== Articles Processed: {success_count}/{len(articles)} ===")
        log.info("=" * 70)
        
    except Exception as e:
        log.exception(f" Pipeline failed: {e}")
        raise

# =====================================================================
# SCHEDULED UPDATE (For Production)
# =====================================================================
def scheduled_update():
    """
    Scheduled update function for production use
    Updates sentiment data every hour to stay in sync with price updates
    """
    log.info(" Running scheduled sentiment update...")
    
    # Fetch and analyze news from the last 1 hour
    # Add a small overlap (1.5 hours) to avoid missing articles
    update_sentiment_pipeline(hours_back=2, skip_refresh=False)

# =====================================================================
# BACKFILL HISTORICAL SENTIMENT (Optional)
# =====================================================================
def backfill_sentiment(days: int = 7):
    """
    Backfill sentiment data for historical analysis in larger chunks to reduce API calls.
    """
    log.info(f" Backfilling sentiment data for last {days} days...")

    hours = days * 24
    chunk_size = days * 24  # 180 days per chunk = 4320 hours

    total_chunks = (hours + chunk_size - 1) // chunk_size

    for i in range(0, hours, chunk_size):
        chunk_hours = min(chunk_size, hours - i)
        log.info(f"\n Processing chunk {i // chunk_size + 1}/{total_chunks} "
                 f"({chunk_hours} hours)...")

        try:
            update_sentiment_pipeline(hours_back=chunk_hours, skip_refresh=True)
        except Exception as e:
            log.error(f" Chunk {i // chunk_size + 1} failed: {e}")
            continue

    # Refresh aggregates once at the end
    log.info("\n Final aggregate refresh...")
    db_config = get_db_config()
    conn = connect_to_db(db_config)
    refresh_continuous_aggregates(conn)
    conn.close()

    log.info(" Backfill completed")


# =====================================================================
# INTEGRATION WITH PRICE UPDATE
# =====================================================================
def sync_with_price_update():
    """
    This function should be called whenever price data is updated
    to keep sentiment data in sync
    """
    log.info(" Syncing sentiment with price update...")
    
    # Update sentiment for the last 1 hour (matching price update interval)
    update_sentiment_pipeline(hours_back=1, skip_refresh=False)