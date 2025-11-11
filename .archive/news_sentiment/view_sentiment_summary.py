"""
View Sentiment Summary Across All Time Intervals
"""

import os
import psycopg2
from dotenv import load_dotenv
from tabulate import tabulate

load_dotenv()

def get_db_config():
    return {
        "host": os.getenv("TIMESCALE_HOST", "localhost"),
        "port": int(os.getenv("TIMESCALE_PORT", 5432)),
        "user": os.getenv("TIMESCALE_USER"),
        "password": os.getenv("TIMESCALE_PASSWORD"),
        "dbname": os.getenv("TIMESCALE_DBNAME", "postgres"),
    }

def view_sentiment_summary():
    """Display sentiment summary across all time intervals"""
    
    config = get_db_config()
    conn = psycopg2.connect(**config)
    cur = conn.cursor()
    
    print("\n" + "="*80)
    print("BITCOIN NEWS SENTIMENT ANALYSIS SUMMARY")
    print("="*80 + "\n")
    
    # 1. Overall Statistics
    print("1. OVERALL STATISTICS")
    print("-" * 80)
    
    cur.execute("""
        SELECT 
            COUNT(*) as total_articles,
            COUNT(DISTINCT source) as num_sources,
            MIN(published_at) as earliest_article,
            MAX(published_at) as latest_article
        FROM news_articles
    """)
    
    total_articles, num_sources, earliest, latest = cur.fetchone()
    print(f"Total Articles: {total_articles}")
    print(f"Number of Sources: {num_sources}")
    print(f"Date Range: {earliest} to {latest}")
    
    # 2. Sentiment Distribution (All Time)
    print("\n2. SENTIMENT DISTRIBUTION (ALL TIME)")
    print("-" * 80)
    
    cur.execute("""
        SELECT 
            sentiment_label,
            COUNT(*) as count,
            ROUND(AVG(sentiment_score)::numeric, 3) as avg_score,
            ROUND(AVG(confidence)::numeric, 3) as avg_confidence
        FROM news_sentiment
        GROUP BY sentiment_label
        ORDER BY count DESC
    """)
    
    sentiment_dist = cur.fetchall()
    headers = ["Label", "Count", "Avg Score", "Avg Confidence"]
    print(tabulate(sentiment_dist, headers=headers, tablefmt="grid"))
    
    # 3. Hourly Sentiment (Last 24 hours)
    print("\n3. HOURLY SENTIMENT (LAST 24 HOURS)")
    print("-" * 80)
    
    cur.execute("""
        SELECT 
            TO_CHAR(bucket, 'Mon DD HH24:MI') as time,
            article_count,
            ROUND(avg_sentiment::numeric, 3) as sentiment,
            ROUND(sentiment_volatility::numeric, 3) as volatility,
            positive_count,
            negative_count,
            neutral_count,
            ROUND(avg_confidence::numeric, 3) as confidence
        FROM sentiment_1h
        WHERE bucket > NOW() - INTERVAL '24 hours'
        ORDER BY bucket DESC
        LIMIT 10
    """)
    
    hourly = cur.fetchall()
    if hourly:
        headers = ["Time", "Articles", "Sentiment", "Volatility", "Positive", "Negative", "Neutral", "Confidence"]
        print(tabulate(hourly, headers=headers, tablefmt="grid"))
    else:
        print("No hourly data yet. Run sentiment updates first.")
    
    # 4. Daily Sentiment (Last 7 days)
    print("\n4. DAILY SENTIMENT (LAST 7 DAYS)")
    print("-" * 80)
    
    cur.execute("""
        SELECT 
            TO_CHAR(bucket, 'Mon DD, YYYY') as date,
            article_count,
            ROUND(avg_sentiment::numeric, 3) as sentiment,
            ROUND(sentiment_volatility::numeric, 3) as volatility,
            positive_count,
            negative_count,
            neutral_count,
            ROUND(avg_confidence::numeric, 3) as confidence
        FROM sentiment_1d
        WHERE bucket > NOW() - INTERVAL '7 days'
        ORDER BY bucket DESC
    """)
    
    daily = cur.fetchall()
    if daily:
        headers = ["Date", "Articles", "Sentiment", "Volatility", "Positive", "Negative", "Neutral", "Confidence"]
        print(tabulate(daily, headers=headers, tablefmt="grid"))
    else:
        print("No daily data yet. Run sentiment updates first.")
    
    # 5. Weekly Sentiment (Last 4 weeks)
    print("\n5. WEEKLY SENTIMENT (LAST 4 WEEKS)")
    print("-" * 80)
    
    cur.execute("""
        SELECT 
            TO_CHAR(bucket, 'Mon DD, YYYY') as week_start,
            article_count,
            ROUND(avg_sentiment::numeric, 3) as sentiment,
            ROUND(sentiment_volatility::numeric, 3) as volatility,
            positive_count,
            negative_count,
            neutral_count,
            ROUND(avg_confidence::numeric, 3) as confidence
        FROM sentiment_1w
        WHERE bucket > NOW() - INTERVAL '4 weeks'
        ORDER BY bucket DESC
    """)
    
    weekly = cur.fetchall()
    if weekly:
        headers = ["Week Start", "Articles", "Sentiment", "Volatility", "Positive", "Negative", "Neutral", "Confidence"]
        print(tabulate(weekly, headers=headers, tablefmt="grid"))
    else:
        print("No weekly data yet.")
    
    # 6. Monthly Sentiment (Last 6 months)
    print("\n6. MONTHLY SENTIMENT (LAST 6 MONTHS)")
    print("-" * 80)
    
    cur.execute("""
        SELECT 
            TO_CHAR(bucket, 'Mon YYYY') as month,
            article_count,
            ROUND(avg_sentiment::numeric, 3) as sentiment,
            ROUND(sentiment_volatility::numeric, 3) as volatility,
            positive_count,
            negative_count,
            neutral_count,
            ROUND(avg_confidence::numeric, 3) as confidence
        FROM sentiment_1mo
        WHERE bucket > NOW() - INTERVAL '6 months'
        ORDER BY bucket DESC
    """)
    
    monthly = cur.fetchall()
    if monthly:
        headers = ["Month", "Articles", "Sentiment", "Volatility", "Positive", "Negative", "Neutral", "Confidence"]
        print(tabulate(monthly, headers=headers, tablefmt="grid"))
    else:
        print("No monthly data yet.")
    
    # 7. Top Sources
    print("\n7. TOP NEWS SOURCES")
    print("-" * 80)
    
    cur.execute("""
        SELECT 
            source,
            COUNT(*) as article_count,
            ROUND(AVG(ns.sentiment_score)::numeric, 3) as avg_sentiment
        FROM news_articles na
        JOIN news_sentiment ns ON na.article_id = ns.article_id
        GROUP BY source
        ORDER BY article_count DESC
        LIMIT 10
    """)
    
    sources = cur.fetchall()
    headers = ["Source", "Articles", "Avg Sentiment"]
    print(tabulate(sources, headers=headers, tablefmt="grid"))
    
    # 8. Current Sentiment Trend
    print("\n8. CURRENT SENTIMENT TREND")
    print("-" * 80)
    
    cur.execute("""
        SELECT 
            ROUND(AVG(sentiment_score)::numeric, 3) as current_sentiment,
            CASE 
                WHEN AVG(sentiment_score) > 0.3 THEN 'BULLISH'
                WHEN AVG(sentiment_score) < -0.3 THEN 'BEARISH'
                ELSE 'NEUTRAL'
            END as market_mood
        FROM news_sentiment
        WHERE time > NOW() - INTERVAL '24 hours'
    """)
    
    result = cur.fetchone()
    if result and result[0]:
        sentiment, mood = result
        print(f"24-Hour Average Sentiment: {sentiment}")
        print(f"Market Mood: {mood}")
        
        if sentiment > 0:
            print(f"Status: Positive sentiment ({abs(sentiment):.1%} above neutral)")
        else:
            print(f"Status: Negative sentiment ({abs(sentiment):.1%} below neutral)")
    else:
        print("Not enough data for trend analysis yet.")
    
    print("\n" + "="*80 + "\n")
    
    cur.close()
    conn.close()

if __name__ == "__main__":
    try:
        view_sentiment_summary()
    except Exception as e:
        print(f"Error: {e}")
        print("\nMake sure:")
        print("1. TimescaleDB is running")
        print("2. Sentiment tables are created (python -m scripts.load_sentiment)")
        print("3. You have sentiment data (python -m scripts.update_sentiment --hours 24)")

