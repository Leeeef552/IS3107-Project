"""
Query and Export Sentiment Features for ML Model Training

This script demonstrates how to extract sentiment features combined with
price data for machine learning model training.

Usage:
    python -m scripts.query_sentiment_features --days 30 --output features.csv
"""

import os
import argparse
import pandas as pd
from datetime import datetime, timedelta
from sqlalchemy import create_engine
from dotenv import load_dotenv
from utils.logger import get_logger

log = get_logger("query_sentiment_features.py")
load_dotenv()

# =====================================================================
# DATABASE CONNECTION
# =====================================================================
def get_db_engine():
    """Create SQLAlchemy engine for database connection"""
    host = os.getenv("TIMESCALE_HOST", "localhost")
    port = os.getenv("TIMESCALE_PORT", 5432)
    user = os.getenv("TIMESCALE_USER")
    password = os.getenv("TIMESCALE_PASSWORD")
    dbname = os.getenv("TIMESCALE_DBNAME", "postgres")
    
    connection_string = f"postgresql://{user}:{password}@{host}:{port}/{dbname}"
    return create_engine(connection_string)

# =====================================================================
# FEATURE EXTRACTION QUERIES
# =====================================================================

def get_hourly_features(engine, days: int = 30) -> pd.DataFrame:
    """
    Extract hourly features (price + sentiment)
    Best for: Short-term prediction models (1-24 hours)
    """
    query = f"""
    SELECT 
        p.bucket as time,
        -- Price features
        p.open,
        p.high,
        p.low,
        p.close,
        p.volume,
        -- Sentiment features
        s.avg_sentiment,
        s.sentiment_volatility,
        s.weighted_sentiment,
        s.positive_count,
        s.negative_count,
        s.neutral_count,
        s.article_count,
        s.avg_confidence
    FROM price_1h p
    LEFT JOIN sentiment_1h s ON p.bucket = s.bucket
    WHERE p.bucket >= NOW() - INTERVAL '{days} days'
    ORDER BY p.bucket ASC
    """
    
    log.info(f" Querying hourly features for last {days} days...")
    df = pd.read_sql(query, engine)
    log.info(f" Retrieved {len(df)} hourly records")
    
    return df

def get_daily_features(engine, days: int = 180) -> pd.DataFrame:
    """
    Extract daily features (price + sentiment)
    Best for: Medium-term prediction models (1-7 days)
    """
    query = f"""
    SELECT 
        p.bucket as time,
        -- Price features
        p.open,
        p.high,
        p.low,
        p.close,
        p.volume,
        -- Sentiment features
        s.avg_sentiment,
        s.sentiment_volatility,
        s.weighted_sentiment,
        s.positive_count,
        s.negative_count,
        s.neutral_count,
        s.article_count,
        s.avg_confidence
    FROM price_1d p
    LEFT JOIN sentiment_1d s ON p.bucket = s.bucket
    WHERE p.bucket >= NOW() - INTERVAL '{days} days'
    ORDER BY p.bucket ASC
    """
    
    log.info(f" Querying daily features for last {days} days...")
    df = pd.read_sql(query, engine)
    log.info(f" Retrieved {len(df)} daily records")
    
    return df

def get_weekly_features(engine, weeks: int = 52) -> pd.DataFrame:
    """
    Extract weekly features (price + sentiment)
    Best for: Long-term prediction models (1-4 weeks)
    """
    query = f"""
    SELECT 
        p.bucket as time,
        -- Price features
        p.open,
        p.high,
        p.low,
        p.close,
        p.volume,
        -- Sentiment features
        s.avg_sentiment,
        s.sentiment_volatility,
        s.weighted_sentiment,
        s.positive_count,
        s.negative_count,
        s.neutral_count,
        s.article_count,
        s.avg_confidence
    FROM price_1w p
    LEFT JOIN sentiment_1w s ON p.bucket = s.bucket
    WHERE p.bucket >= NOW() - INTERVAL '{weeks} weeks'
    ORDER BY p.bucket ASC
    """
    
    log.info(f" Querying weekly features for last {weeks} weeks...")
    df = pd.read_sql(query, engine)
    log.info(f" Retrieved {len(df)} weekly records")
    
    return df

# =====================================================================
# FEATURE ENGINEERING
# =====================================================================

def engineer_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Add derived features to the dataset
    
    Features added:
    - Price changes and returns
    - Moving averages
    - Sentiment momentum
    - Volume changes
    """
    log.info(" Engineering additional features...")
    
    df = df.copy()
    
    # Price features
    df['price_change'] = df['close'].diff()
    df['price_return'] = df['close'].pct_change()
    df['high_low_spread'] = df['high'] - df['low']
    
    # Moving averages (if enough data)
    if len(df) >= 7:
        df['close_ma7'] = df['close'].rolling(window=7).mean()
        df['volume_ma7'] = df['volume'].rolling(window=7).mean()
    
    if len(df) >= 30:
        df['close_ma30'] = df['close'].rolling(window=30).mean()
    
    # Sentiment features
    df['sentiment_change'] = df['avg_sentiment'].diff()
    df['sentiment_momentum'] = df['avg_sentiment'].diff(3)  # 3-period momentum
    
    # Sentiment-to-price ratio (normalized)
    df['sentiment_price_ratio'] = df['avg_sentiment'] / (df['close'] / df['close'].mean())
    
    # Article activity
    df['article_change'] = df['article_count'].diff()
    
    # Positive/negative ratio
    df['pos_neg_ratio'] = df['positive_count'] / (df['negative_count'] + 1)  # +1 to avoid division by zero
    
    log.info(f" Engineered features. Total columns: {len(df.columns)}")
    
    return df

def handle_missing_values(df: pd.DataFrame) -> pd.DataFrame:
    """
    Handle missing values in the dataset
    
    Strategy:
    - Sentiment features: Fill with 0 (neutral) if no articles available
    - Price features: Forward fill (use last known value)
    """
    log.info(" Handling missing values...")
    
    df = df.copy()
    
    # Sentiment columns to fill with neutral values
    sentiment_cols = [
        'avg_sentiment', 'weighted_sentiment', 'sentiment_volatility',
        'sentiment_change', 'sentiment_momentum', 'sentiment_price_ratio'
    ]
    
    count_cols = [
        'positive_count', 'negative_count', 'neutral_count', 
        'article_count', 'article_change'
    ]
    
    # Fill sentiment with 0 (neutral)
    for col in sentiment_cols:
        if col in df.columns:
            df[col] = df[col].fillna(0)
    
    # Fill counts with 0
    for col in count_cols:
        if col in df.columns:
            df[col] = df[col].fillna(0)
    
    # Fill confidence with 0.5 (uncertain)
    if 'avg_confidence' in df.columns:
        df['avg_confidence'] = df['avg_confidence'].fillna(0.5)
    
    # Forward fill price features
    price_cols = ['open', 'high', 'low', 'close', 'volume']
    for col in price_cols:
        if col in df.columns:
            df[col] = df[col].fillna(method='ffill')
    
    # For remaining NaNs (e.g., first rows with diff/pct_change), backfill
    df = df.fillna(method='bfill')
    
    log.info(f" Missing values handled. Remaining NaNs: {df.isna().sum().sum()}")
    
    return df

# =====================================================================
# MAIN FUNCTION
# =====================================================================

def main():
    parser = argparse.ArgumentParser(
        description='Query and export sentiment features for ML training',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Export hourly features for last 30 days
  python -m scripts.query_sentiment_features --interval hourly --days 30 --output hourly_features.csv
  
  # Export daily features for last 6 months
  python -m scripts.query_sentiment_features --interval daily --days 180 --output daily_features.csv
  
  # Export weekly features for last year
  python -m scripts.query_sentiment_features --interval weekly --weeks 52 --output weekly_features.csv
        """
    )
    
    parser.add_argument(
        '--interval',
        choices=['hourly', 'daily', 'weekly'],
        default='daily',
        help='Time interval for features (default: daily)'
    )
    
    parser.add_argument(
        '--days',
        type=int,
        default=30,
        help='Number of days to query (for hourly/daily, default: 30)'
    )
    
    parser.add_argument(
        '--weeks',
        type=int,
        default=52,
        help='Number of weeks to query (for weekly, default: 52)'
    )
    
    parser.add_argument(
        '--output',
        type=str,
        default='sentiment_features.csv',
        help='Output CSV file path (default: sentiment_features.csv)'
    )
    
    parser.add_argument(
        '--no-engineering',
        action='store_true',
        help='Skip feature engineering (export raw features only)'
    )
    
    args = parser.parse_args()
    
    # Connect to database
    engine = get_db_engine()
    
    # Query features based on interval
    if args.interval == 'hourly':
        df = get_hourly_features(engine, days=args.days)
    elif args.interval == 'daily':
        df = get_daily_features(engine, days=args.days)
    else:  # weekly
        df = get_weekly_features(engine, weeks=args.weeks)
    
    # Engineer additional features if requested
    if not args.no_engineering:
        df = engineer_features(df)
        df = handle_missing_values(df)
    
    # Export to CSV
    df.to_csv(args.output, index=False)
    log.info(f" Features exported to: {args.output}")
    log.info(f" Shape: {df.shape[0]} rows × {df.shape[1]} columns")
    
    # Display summary
    print("\n" + "=" * 70)
    print("FEATURE SUMMARY")
    print("=" * 70)
    print(f"Time Range: {df['time'].min()} to {df['time'].max()}")
    print(f"Records: {len(df)}")
    print(f"Features: {len(df.columns)}")
    print("\nColumn List:")
    for i, col in enumerate(df.columns, 1):
        print(f"  {i:2d}. {col}")
    print("\nSample Statistics:")
    print(df.describe())
    print("=" * 70)

if __name__ == "__main__":
    main()

