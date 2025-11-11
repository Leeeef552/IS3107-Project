"""
Database query functions for the Bitcoin Analytics Dashboard

This module handles all database connections and data retrieval operations.
"""

import streamlit as st
import pandas as pd
import requests
from datetime import datetime
import sys
import os
from sqlalchemy import create_engine

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from configs.config import DB_CONFIG


@st.cache_resource
def get_db_engine():
    """Create a SQLAlchemy database engine for pandas queries"""
    try:
        connection_string = (
            f"postgresql://{DB_CONFIG['user']}:{DB_CONFIG['password']}"
            f"@localhost:{DB_CONFIG['port']}/{DB_CONFIG['dbname']}"
        )
        engine = create_engine(connection_string)
        return engine
    except Exception as e:
        st.error(f"Database connection failed: {str(e)}")
        return None


@st.cache_data(ttl=10)  # Cache for 10 seconds for near-live updates
def get_latest_price():
    """Fetch the most recent Bitcoin price"""
    engine = get_db_engine()
    if engine is None:
        return None
    
    try:
        query = """
        SELECT time, open, high, low, close, volume
        FROM historical_price
        ORDER BY time DESC
        LIMIT 1
        """
        df = pd.read_sql_query(query, engine)
        if not df.empty:
            # Convert to Singapore time (GMT+8)
            import pytz
            singapore_tz = pytz.timezone('Asia/Singapore')
            # Check if already timezone-aware, if so just convert, otherwise localize first
            if df['time'].dt.tz is None:
                df['time'] = pd.to_datetime(df['time']).dt.tz_localize('UTC').dt.tz_convert(singapore_tz)
            else:
                df['time'] = pd.to_datetime(df['time']).dt.tz_convert(singapore_tz)
            return df.iloc[0]
        return None
    except Exception as e:
        st.error(f"Error fetching latest price: {str(e)}")
        return None


@st.cache_data(ttl=60)
def get_price_history(interval='1 hour', limit=168):
    """
    Fetch historical price data for charts
    
    Args:
        interval: Time interval ('1 hour', '1 day', etc.)
        limit: Number of data points to fetch
        
    Returns:
        DataFrame with columns: time, open, high, low, close, volume
    """
    engine = get_db_engine()
    if engine is None:
        return pd.DataFrame()
    
    try:
        # Map interval to appropriate table/aggregation
        table_map = {
            '5min': 'price_5min',
            '1hour': 'price_1h',
            '1day': 'price_1d',
            '1week': 'price_1w'
        }
        
        table = table_map.get(interval)
        
        if table:
            query = f"""
            SELECT bucket as time, open, high, low, close, volume
            FROM {table}
            ORDER BY bucket DESC
            LIMIT {limit}
            """
        else:
            # Fallback to raw data
            query = f"""
            SELECT time, open, high, low, close, volume
            FROM historical_price
            ORDER BY time DESC
            LIMIT {limit}
            """
        
        df = pd.read_sql_query(query, engine)
        df = df.sort_values('time')  # Sort ascending for chart
        return df
    except Exception as e:
        st.warning(f"Could not fetch price history: {str(e)}")
        return pd.DataFrame()


@st.cache_data(ttl=300)  # Cache for 5 minutes
def get_latest_articles(limit=5):
    """
    Fetch the latest news articles with sentiment scores
    
    Args:
        limit: Maximum number of articles to fetch
        
    Returns:
        DataFrame with article data and sentiment information
    """
    engine = get_db_engine()
    if engine is None:
        return pd.DataFrame()
    
    try:
        query = f"""
        SELECT 
            na.article_id,
            na.published_at,
            na.title,
            na.content,
            na.url,
            na.source,
            na.author,
            ns.sentiment_score,
            ns.sentiment_label,
            ns.confidence
        FROM news_articles na
        LEFT JOIN news_sentiment ns ON na.article_id = ns.article_id
        ORDER BY na.published_at DESC
        LIMIT {limit}
        """
        df = pd.read_sql_query(query, engine)
        
        # Add image URL extraction logic
        if not df.empty:
            df['image_url'] = df.apply(lambda row: extract_image_url(row['url'], row['source']), axis=1)
        
        return df
    except Exception as e:
        st.warning(f"Could not fetch articles: {str(e)}")
        return pd.DataFrame()


def extract_image_url(article_url, source):
    """
    Extract or generate image URL for article
    For now, returns placeholder based on source
    """
    # Placeholder images by source
    source_images = {
        'CryptoCompare': 'https://images.unsplash.com/photo-1518546305927-5a555bb7020d?w=400',
        'Reddit': 'https://images.unsplash.com/photo-1621761191319-c6fb62004040?w=400',
        'NewsAPI': 'https://images.unsplash.com/photo-1605792657660-596af9009e82?w=400'
    }
    return source_images.get(source, 'https://images.unsplash.com/photo-1621761191319-c6fb62004040?w=400')


@st.cache_data(ttl=300)
def get_sentiment_summary(interval='1 day', limit=7):
    """
    Fetch sentiment aggregates at different time intervals
    
    Args:
        interval: Time interval ('1 hour', '1 day', '1 week', '1 month')
        limit: Number of time periods to fetch
        
    Returns:
        DataFrame with aggregated sentiment metrics
    """
    engine = get_db_engine()
    if engine is None:
        return pd.DataFrame()
    
    try:
        table_map = {
            '1 hour': 'sentiment_1h',
            '1 day': 'sentiment_1d',
            '1 week': 'sentiment_1w',
            '1 month': 'sentiment_1mo'
        }
        
        table = table_map.get(interval, 'sentiment_1d')
        
        query = f"""
        SELECT 
            bucket,
            article_count,
            avg_sentiment,
            sentiment_volatility,
            positive_count,
            negative_count,
            neutral_count,
            avg_confidence
        FROM {table}
        ORDER BY bucket DESC
        LIMIT {limit}
        """
        df = pd.read_sql_query(query, engine)
        df = df.sort_values('bucket')  # Sort ascending for chart
        return df
    except Exception as e:
        st.warning(f"Could not fetch sentiment data: {str(e)}")
        return pd.DataFrame()


@st.cache_data(ttl=3600)  # Cache for 1 hour
def get_fear_greed_index():
    """
    Fetch Fear & Greed Index from alternative.me API
    
    Returns:
        Dictionary with 'value', 'classification', and 'timestamp'
        or None if request fails
    """
    try:
        response = requests.get('https://api.alternative.me/fng/?limit=1', timeout=10)
        if response.status_code == 200:
            data = response.json()
            if data['data']:
                fng_data = data['data'][0]
                return {
                    'value': int(fng_data['value']),
                    'classification': fng_data['value_classification'],
                    'timestamp': datetime.fromtimestamp(int(fng_data['timestamp']))
                }
        return None
    except Exception as e:
        st.warning(f"Could not fetch Fear & Greed Index: {str(e)}")
        return None


@st.cache_data(ttl=3600)  # Cache for 1 hour
def get_exchange_rate(base='USD', target='SGD'):
    """
    Fetch live exchange rate from free API
    
    Args:
        base: Base currency code (default: USD)
        target: Target currency code (default: SGD)
        
    Returns:
        Float exchange rate, or fallback rate if API fails
    """
    fallback_rate = 1.35  # Fallback approximate rate
    
    try:
        # Using exchangerate-api.com free tier (no auth required)
        url = f'https://open.er-api.com/v6/latest/{base}'
        response = requests.get(url, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            if data and 'rates' in data and target in data['rates']:
                rate = data['rates'][target]
                return float(rate)
        
        # Fallback if API fails
        return fallback_rate
    except Exception as e:
        # Silently fallback to approximate rate
        return fallback_rate


def test_database_connection():
    """
    Test database connection and verify tables exist

    Returns:
        Dictionary with connection status and available tables
    """
    engine = get_db_engine()
    if engine is None:
        return {'connected': False, 'tables': []}

    try:
        query = """
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema = 'public'
        AND table_type = 'BASE TABLE'
        ORDER BY table_name
        """
        df = pd.read_sql_query(query, engine)
        return {
            'connected': True,
            'tables': df['table_name'].tolist()
        }
    except Exception as e:
        return {
            'connected': False,
            'error': str(e),
            'tables': []
        }


# ==============================================================================
# WHALE TRANSACTION QUERIES
# ==============================================================================

@st.cache_data(ttl=30)  # Cache for 30 seconds for near-real-time updates
def get_recent_whale_transactions(limit=10):
    """
    Fetch recent whale transactions

    Args:
        limit: Maximum number of transactions to fetch

    Returns:
        DataFrame with recent whale transactions
    """
    engine = get_db_engine()
    if engine is None:
        return pd.DataFrame()

    try:
        query = f"""
        SELECT
            txid,
            detected_at,
            value_btc,
            block_timestamp,
            block_height,
            label,
            input_count,
            output_count,
            output_addresses,
            to_exchange,
            from_exchange,
            external_out_btc
        FROM whale_transactions
        ORDER BY detected_at DESC
        LIMIT {limit}
        """
        df = pd.read_sql_query(query, engine)
        
        # Calculate USD value from current BTC price
        if not df.empty and 'value_btc' in df.columns:
            # Get current BTC price
            latest_price = get_latest_price()
            if latest_price is not None and 'close' in latest_price:
                btc_price = latest_price['close']
                df['value_usd'] = df['value_btc'] * btc_price
            else:
                # Fallback to approximate price if can't fetch
                df['value_usd'] = df['value_btc'] * 110000  # Approximate BTC price
            
            # Add status column (derived from block_timestamp)
            # If block_timestamp exists, transaction is confirmed
            df['status'] = df.apply(
                lambda row: 'confirmed' if pd.notna(row.get('block_timestamp')) else 'mempool',
                axis=1
            )
            
            # Extract primary addresses from output_addresses array
            # Take first output address as primary
            if 'output_addresses' in df.columns:
                df['primary_output_address'] = df['output_addresses'].apply(
                    lambda x: x[0] if isinstance(x, list) and len(x) > 0 else None
                )
            else:
                df['primary_output_address'] = None
            
            # Primary input address not available in Airflow schema, set to None
            df['primary_input_address'] = None

        # Convert to Singapore time
        if not df.empty and 'detected_at' in df.columns:
            import pytz
            singapore_tz = pytz.timezone('Asia/Singapore')
            if df['detected_at'].dt.tz is None:
                df['detected_at'] = pd.to_datetime(df['detected_at']).dt.tz_localize('UTC').dt.tz_convert(singapore_tz)
            else:
                df['detected_at'] = pd.to_datetime(df['detected_at']).dt.tz_convert(singapore_tz)

        return df
    except Exception as e:
        st.warning(f"Could not fetch whale transactions: {str(e)}")
        return pd.DataFrame()


@st.cache_data(ttl=60)
def get_whale_stats(period_hours=24):
    """
    Get whale transaction statistics for a given period

    Args:
        period_hours: Number of hours to look back

    Returns:
        Dictionary with whale statistics
    """
    engine = get_db_engine()
    if engine is None:
        return None

    try:
        query = f"""
        SELECT
            COUNT(*) as transaction_count,
            SUM(value_btc) as total_btc,
            AVG(value_btc) as avg_btc,
            MAX(value_btc) as max_btc,
            MIN(value_btc) as min_btc
        FROM whale_transactions
        WHERE detected_at > NOW() - INTERVAL '{period_hours} hours'
        """
        df = pd.read_sql_query(query, engine)

        if not df.empty:
            stats = df.iloc[0].to_dict()
            # Calculate USD values from current BTC price
            latest_price = get_latest_price()
            if latest_price is not None and 'close' in latest_price:
                btc_price = latest_price['close']
            else:
                btc_price = 110000  # Fallback approximate price
            
            stats['total_usd'] = stats['total_btc'] * btc_price if stats['total_btc'] else 0
            return stats
        return None
    except Exception as e:
        st.warning(f"Could not fetch whale stats: {str(e)}")
        return None


@st.cache_data(ttl=300)
def get_whale_trend(interval='1 hour', limit=24):
    """
    Get whale transaction trends over time

    Args:
        interval: Time interval ('1 hour', '1 day')
        limit: Number of intervals to fetch

    Returns:
        DataFrame with whale transaction trends
    """
    engine = get_db_engine()
    if engine is None:
        return pd.DataFrame()

    try:
        # Check if aggregate views exist, otherwise compute from raw data
        # First try to use aggregate views
        table_map = {
            '1 hour': 'whale_stats_1h',
            '1 day': 'whale_stats_1d'
        }

        table = table_map.get(interval, 'whale_stats_1h')
        
        # Try to query aggregate view first
        try:
            query = f"""
            SELECT
                bucket,
                transaction_count,
                total_btc,
                avg_btc,
                max_btc
            FROM {table}
            ORDER BY bucket DESC
            LIMIT {limit}
            """
            df = pd.read_sql_query(query, engine)
            
            # Calculate total_usd from current BTC price
            latest_price = get_latest_price()
            if latest_price is not None and 'close' in latest_price:
                btc_price = latest_price['close']
            else:
                btc_price = 110000  # Fallback
            
            df['total_usd'] = df['total_btc'] * btc_price
            df = df.sort_values('bucket')  # Sort ascending for charts
            return df
        except Exception:
            # Aggregate view doesn't exist, compute from raw data
            time_bucket = '1 hour' if interval == '1 hour' else '1 day'
            query = f"""
            SELECT
                time_bucket('{time_bucket}', detected_at) AS bucket,
                COUNT(*) AS transaction_count,
                SUM(value_btc) AS total_btc,
                AVG(value_btc) AS avg_btc,
                MAX(value_btc) AS max_btc
            FROM whale_transactions
            WHERE detected_at > NOW() - INTERVAL '{limit * (24 if interval == "1 day" else 1)} hours'
            GROUP BY bucket
            ORDER BY bucket DESC
            LIMIT {limit}
            """
            df = pd.read_sql_query(query, engine)
            
            # Calculate total_usd
            latest_price = get_latest_price()
            if latest_price is not None and 'close' in latest_price:
                btc_price = latest_price['close']
            else:
                btc_price = 110000
            
            df['total_usd'] = df['total_btc'] * btc_price
            df = df.sort_values('bucket')
            return df
    except Exception as e:
        st.warning(f"Could not fetch whale trends: {str(e)}")
        return pd.DataFrame()



@st.cache_data(ttl=300)
def get_block_metrics(limit=24):
    """
    Fetch recent block metrics
    
    Args:
        limit: Maximum number of blocks to fetch
        
    Returns:
        DataFrame with block metrics
    """
    engine = get_db_engine()
    if engine is None:
        return pd.DataFrame()
    
    try:
        query = f"""
        SELECT
            block_height,
            block_hash,
            block_timestamp,
            tx_count,
            size,
            weight,
            fill_ratio,
            fee_total_sats,
            avg_fee_rate_sat_vb,
            median_fee_rate_sat_vb,
            whale_weighted_flow,
            whale_total_external_btc,
            to_exchange_btc,
            from_exchange_btc,
            top5_concentration,
            consolidation_index,
            distribution_index,
            labeled_tx_count,
            whale_count,
            shark_count,
            dolphin_count,
            calculated_at
        FROM block_metrics
        ORDER BY block_timestamp DESC
        LIMIT {limit}
        """
        df = pd.read_sql_query(query, engine)
        df = df.sort_values('block_timestamp')  # Sort ascending for charts
        
        # Convert to Singapore time
        if not df.empty and 'block_timestamp' in df.columns:
            import pytz
            singapore_tz = pytz.timezone('Asia/Singapore')
            if df['block_timestamp'].dt.tz is None:
                df['block_timestamp'] = pd.to_datetime(df['block_timestamp']).dt.tz_localize('UTC').dt.tz_convert(singapore_tz)
            else:
                df['block_timestamp'] = pd.to_datetime(df['block_timestamp']).dt.tz_convert(singapore_tz)
        
        return df
    except Exception as e:
        st.warning(f"Could not fetch block metrics: {str(e)}")
        return pd.DataFrame()


@st.cache_data(ttl=300)
def get_whale_sentiment(limit=24):
    """
    Fetch recent whale sentiment data
    
    Args:
        limit: Maximum number of records to fetch
        
    Returns:
        DataFrame with whale sentiment data
    """
    engine = get_db_engine()
    if engine is None:
        return pd.DataFrame()
    
    try:
        query = f"""
        SELECT
            block_height,
            block_hash,
            block_timestamp,
            whale_count,
            shark_count,
            dolphin_count,
            score,
            sentiment,
            whale_flow_component,
            exchange_pressure_component,
            fee_pressure_component,
            utilization_component,
            calculated_at
        FROM whale_sentiment
        ORDER BY block_timestamp DESC
        LIMIT {limit}
        """
        df = pd.read_sql_query(query, engine)
        df = df.sort_values('block_timestamp')  # Sort ascending for charts
        
        # Convert to Singapore time
        if not df.empty and 'block_timestamp' in df.columns:
            import pytz
            singapore_tz = pytz.timezone('Asia/Singapore')
            if df['block_timestamp'].dt.tz is None:
                df['block_timestamp'] = pd.to_datetime(df['block_timestamp']).dt.tz_localize('UTC').dt.tz_convert(singapore_tz)
            else:
                df['block_timestamp'] = pd.to_datetime(df['block_timestamp']).dt.tz_convert(singapore_tz)
        
        return df
    except Exception as e:
        st.warning(f"Could not fetch whale sentiment: {str(e)}")
        return pd.DataFrame()


@st.cache_data(ttl=300)
def get_block_whale_correlation(limit=24):
    """
    Fetch combined block metrics and whale sentiment data for correlation analysis
    
    Args:
        limit: Maximum number of records to fetch
        
    Returns:
        DataFrame with combined block metrics and whale sentiment
    """
    engine = get_db_engine()
    if engine is None:
        return pd.DataFrame()
    
    try:
        query = f"""
        SELECT
            bm.block_height,
            bm.block_timestamp,
            bm.tx_count,
            bm.size,
            bm.weight,
            bm.avg_fee_rate_sat_vb,
            bm.whale_weighted_flow,
            bm.whale_total_external_btc,
            bm.to_exchange_btc,
            bm.from_exchange_btc,
            bm.consolidation_index,
            bm.distribution_index,
            bm.whale_count,
            bm.shark_count,
            bm.dolphin_count,
            ws.score as sentiment_score,
            ws.sentiment,
            ws.whale_flow_component,
            ws.exchange_pressure_component,
            ws.fee_pressure_component,
            ws.utilization_component
        FROM block_metrics bm
        LEFT JOIN whale_sentiment ws ON bm.block_height = ws.block_height
        ORDER BY bm.block_timestamp DESC
        LIMIT {limit}
        """
        df = pd.read_sql_query(query, engine)
        df = df.sort_values('block_timestamp')  # Sort ascending for charts
        
        # Convert to Singapore time
        if not df.empty and 'block_timestamp' in df.columns:
            import pytz
            singapore_tz = pytz.timezone('Asia/Singapore')
            if df['block_timestamp'].dt.tz is None:
                df['block_timestamp'] = pd.to_datetime(df['block_timestamp']).dt.tz_localize('UTC').dt.tz_convert(singapore_tz)
            else:
                df['block_timestamp'] = pd.to_datetime(df['block_timestamp']).dt.tz_convert(singapore_tz)
        
        return df
    except Exception as e:
        st.warning(f"Could not fetch block-whale correlation: {str(e)}")
        return pd.DataFrame()
    

# ==============================================================================
# LSTM PREDICTIONS
# ==============================================================================
@st.cache_data(ttl=300)  # Cache for 5 minutes
def get_lstm_predictions(limit=5):
    """
    Fetch LSTM model predictions for the next 12 hours
    
    Args:
        limit: Maximum number of prediction records to fetch
        
    Returns:
        DataFrame with LSTM prediction data
    """
    engine = get_db_engine()
    if engine is None:
        return pd.DataFrame()
    
    try:
        query = f"""
        SELECT
            prediction_time,
            run_id,
            predicted_low,
            predicted_high,
            predicted_mean,
            predicted_variance,
            base_price,
            created_at,
            SQRT(predicted_variance) as predicted_std
        FROM model_predictions
        ORDER BY prediction_time DESC
        LIMIT {limit}
        """
        df = pd.read_sql_query(query, engine)
        df = df.sort_values('prediction_time')  # Sort ascending for charts
        
        # Convert to Singapore time
        if not df.empty and 'prediction_time' in df.columns:
            import pytz
            singapore_tz = pytz.timezone('Asia/Singapore')
            if df['prediction_time'].dt.tz is None:
                df['prediction_time'] = pd.to_datetime(df['prediction_time']).dt.tz_localize('UTC').dt.tz_convert(singapore_tz)
            else:
                df['prediction_time'] = pd.to_datetime(df['prediction_time']).dt.tz_convert(singapore_tz)
            
            if df['created_at'].dt.tz is None:
                df['created_at'] = pd.to_datetime(df['created_at']).dt.tz_localize('UTC').dt.tz_convert(singapore_tz)
            else:
                df['created_at'] = pd.to_datetime(df['created_at']).dt.tz_convert(singapore_tz)
        
        return df
    except Exception as e:
        st.warning(f"Could not fetch LSTM predictions: {str(e)}")
        return pd.DataFrame()