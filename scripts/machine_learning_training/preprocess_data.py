import os
import pandas as pd
import numpy as np
from sklearn.linear_model import LinearRegression
from configs.config import TRAINING_DIR
from utils.logger import get_logger

logger = get_logger("preprocess_data.py")


# ============================================================
# NEWS PREPROCESS
# ============================================================

def drop_columns_news_sentiment(news_sentiment):
    news_sentiment = news_sentiment.drop(columns=["model_used", "article_id"])
    return news_sentiment


def basic_sentiment_stats(group: pd.DataFrame) -> pd.Series:
    """Compute basic statistics for sentiment scores in a time bucket"""
    return pd.Series({
        'article_count': len(group),
        'sentiment_mean': group['sentiment_score'].mean(),
        'sentiment_median': group['sentiment_score'].median(),
        'sentiment_std': group['sentiment_score'].std(),
        'confidence_mean': group['confidence'].mean(),
        'confidence_std': group['confidence'].std()
    })


def weighted_sentiment_features(group: pd.DataFrame) -> pd.Series:
    """Compute confidence-weighted sentiment metrics"""
    weights = group['confidence']
    total_weight = weights.sum()
    
    if total_weight == 0 or len(group) == 0:
        return pd.Series({
            'weighted_sentiment': np.nan,
            'weighted_std': np.nan,
            'confidence_weighted_count': 0.0
        })
    
    # Weighted sentiment score
    weighted_sentiment = (group['sentiment_score'] * weights).sum() / total_weight
    
    # Weighted standard deviation
    diff = group['sentiment_score'] - weighted_sentiment
    weighted_variance = (weights * (diff ** 2)).sum() / total_weight
    weighted_std = np.sqrt(weighted_variance) if weighted_variance > 0 else 0.0
    
    return pd.Series({
        'weighted_sentiment': weighted_sentiment,
        'weighted_std': weighted_std,
        'confidence_weighted_count': total_weight  # Sum of confidences
    })


def polarity_ratios(group: pd.DataFrame) -> pd.Series:
    """Compute ratios of positive/negative/neutral articles"""
    if len(group) == 0:
        return pd.Series({
            'positive_ratio': 0.0,
            'negative_ratio': 0.0,
            'neutral_ratio': 1.0,
            'polarized_ratio': 0.0
        })
    
    # Define thresholds
    POS_THRESH = 0.05
    NEG_THRESH = -0.05
    HIGH_CONF_THRESH = 0.7
    
    # Count polarized articles (high confidence + strong sentiment)
    polarized = group[
        (group['confidence'] >= HIGH_CONF_THRESH) &
        (abs(group['sentiment_score']) >= 0.5)
    ]
    
    return pd.Series({
        'positive_ratio': (group['sentiment_score'] > POS_THRESH).mean(),
        'negative_ratio': (group['sentiment_score'] < NEG_THRESH).mean(),
        'neutral_ratio': ((group['sentiment_score'] >= NEG_THRESH) & 
                          (group['sentiment_score'] <= POS_THRESH)).mean(),
        'polarized_ratio': len(polarized) / len(group)
    })


def conflict_features(group: pd.DataFrame) -> pd.Series:
    """Detect sentiment conflict/disagreement in time bucket"""
    if len(group) < 2:
        return pd.Series({
            'conflict_score': 0.0,
            'max_disagreement': 0.0,
            'is_high_conflict': False
        })
    
    # High conflict = high volatility + high confidence articles exist
    volatility = group['sentiment_score'].std()
    high_conf_articles = group[group['confidence'] > 0.6]
    
    conflict_score = volatility * (len(high_conf_articles) / len(group))
    max_disagreement = group['sentiment_score'].max() - group['sentiment_score'].min()
    
    # Binary flag for extreme conflict
    is_high_conflict = (volatility > 0.6) and (len(high_conf_articles) >= 2)
    
    return pd.Series({
        'conflict_score': conflict_score,
        'max_disagreement': max_disagreement,
        'is_high_conflict': is_high_conflict
    })


def volatility_centric_features(group: pd.DataFrame) -> pd.Series:
    if group.empty:
        return pd.Series({
            'sentiment_score': 0.0,
            'confidence': 0.0,
            'article_count': 0,
            'volatility': 0.0,
            'is_conflict': False
        })
    
    weights = group['confidence']
    total_weight = weights.sum()
    
    # Weighted sentiment
    if total_weight == 0:
        weighted_score = group['sentiment_score'].mean()
    else:
        weighted_score = (group['sentiment_score'] * weights).sum() / total_weight
    
    # Volatility = std of raw sentiment scores
    volatility = group['sentiment_score'].std()
    if pd.isna(volatility):
        volatility = 0.0
    
    avg_conf = weights.mean()
    is_conflict = (volatility > 0.5) and (avg_conf > 0.6)
    
    return pd.Series({
        'sentiment_score': weighted_score,
        'confidence': avg_conf,
        'article_count': len(group),
        'volatility': volatility,
        'is_conflict': is_conflict
    })


def aggregate_sentiment_features(
    df: pd.DataFrame,
    freq: str = '1h',
    feature_functions: list = None
) -> pd.DataFrame:
    if feature_functions is None:
        feature_functions = [
            basic_sentiment_stats,
            weighted_sentiment_features,
            polarity_ratios,
            conflict_features,
            volatility_centric_features
        ]
    
    df = df.copy()
    df['time'] = pd.to_datetime(df['time'])
    df = df.set_index('time').sort_index()
    
    buckets = df.resample(freq)
    
    results = []
    for timestamp, group in buckets:
        features = {'time': timestamp}
        for func in feature_functions:
            try:
                func_result = func(group)
                features.update(func_result.to_dict())
            except Exception as e:
                # Fallback for empty or failed groups
                try:
                    empty_df = pd.DataFrame({'sentiment_score': [], 'confidence': []})
                    placeholder = {col: np.nan for col in func(empty_df).index}
                except Exception:
                    placeholder = {}
                features.update(placeholder)
        results.append(features)
    
    result_df = pd.DataFrame(results)
    
    # Fill NaN values for missing data  --> treat as neutral
    result_df = result_df.fillna({
        'article_count': 0,                # Fill NaN article count with 0
        'positive_ratio': 0,               # Fill NaN positive ratio with 0
        'negative_ratio': 0,               # Fill NaN negative ratio with 0
        'neutral_ratio': 1,                # Fill NaN neutral ratio with 1
        'polarized_ratio': 0.0,            # Fill NaN polarized ratio with 0
        'is_high_conflict': False,         # Fill NaN high conflict flag with False
        'is_conflict': False,              # Fill NaN conflict flag with False
        'confidence_weighted_count': 0.0,  # Fill NaN confidence-weighted count with 0
        'volatility': 0.0,                 # Fill NaN volatility with 0
        'sentiment_score': 0.0,            # Fill NaN sentiment score with 0
        'confidence': 0.0,                 # Fill NaN confidence with 0
        'sentiment_mean': 0.0,             # Fill NaN sentiment mean with 0
        'sentiment_median': 0.0,           # Fill NaN sentiment median with 0
        'sentiment_std': 0.0,              # Fill NaN sentiment std with 0
        'confidence_mean': 0.0,            # Fill NaN confidence mean with 0
        'confidence_std': 0.0,             # Fill NaN confidence std with 0
        'weighted_sentiment': 0.0,         # Fill NaN weighted sentiment with 0
        'weighted_std': 0.0                # Fill NaN weighted std with 0
    })

    # Additional handling for specific categorical columns
    result_df['positive_ratio'].fillna(0, inplace=True)
    result_df['negative_ratio'].fillna(0, inplace=True)
    result_df['neutral_ratio'].fillna(1, inplace=True)  # Fill missing neutral ratio with 1 (neutral)

    result_df = result_df.reset_index()  # moves 'time' back to a column
    result_df = result_df.drop(columns=["index"])
    return result_df


# ============================================================
# PRICE RESAMPLING & INDICATORS
# ============================================================

def resample_price(historical_price, interval="1h"):
    historical_price['time'] = pd.to_datetime(historical_price['time'])
    historical_price.set_index('time', inplace=True)

    # Resample to 4-hour candles (OHLCV)
    price_1h = historical_price.resample(interval).agg({
        'open': 'first',
        'high': 'max',
        'low': 'min',
        'close': 'last',
        'volume': 'sum'
    })

    price_1h.reset_index(inplace=True)
    return price_1h


def add_rolling_features(df, price_col='close', window_days=7, candle_interval_hours=1):
    """
    Adds rolling volatility and return features based on past N days.
    """
    window = int((24 / candle_interval_hours) * window_days)
    df = df.copy()
    df['rolling_volatility'] = df[price_col].pct_change().rolling(window).std()
    df['rolling_return'] = df[price_col].pct_change(window)
    return df


def calculate_rsi(df, column='close', period=14):
    """Calculate the Relative Strength Index (RSI)."""
    delta = df[column].diff()
    gain = delta.where(delta > 0, 0)
    loss = -delta.where(delta < 0, 0)

    avg_gain = gain.rolling(window=period, min_periods=1).mean()
    avg_loss = loss.rolling(window=period, min_periods=1).mean()
    rs = avg_gain / avg_loss
    df['RSI'] = 100 - (100 / (1 + rs))
    return df


def calculate_macd(df, column='close', short_span=12, long_span=26, signal_span=9):
    """Calculate MACD and Signal Line."""
    short_ema = df[column].ewm(span=short_span, adjust=False).mean()
    long_ema = df[column].ewm(span=long_span, adjust=False).mean()
    
    df['MACD'] = short_ema - long_ema
    df['Signal'] = df['MACD'].ewm(span=signal_span, adjust=False).mean()
    df['MACD_Hist'] = df['MACD'] - df['Signal']
    return df


def calculate_bollinger_bands(df, column='close', window=20, num_std=2):
    """Calculate Bollinger Bands."""
    df['SMA'] = df[column].rolling(window=window).mean()
    df['STD'] = df[column].rolling(window=window).std()
    df['UpperBand'] = df['SMA'] + (num_std * df['STD'])
    df['LowerBand'] = df['SMA'] - (num_std * df['STD'])
    return df


def calculate_obv(df, close_col='close', vol_col='volume'):
    """Calculate On-Balance Volume (OBV)."""
    df['OBV'] = 0
    df.loc[df[close_col] > df[close_col].shift(1), 'OBV'] = df[vol_col]
    df.loc[df[close_col] < df[close_col].shift(1), 'OBV'] = -df[vol_col]
    df['OBV'] = df['OBV'].cumsum()
    return df


def calculate_vwap(df, price_col='close', vol_col='volume'):
    """Calculate Volume Weighted Average Price (VWAP)."""
    df['Cum_Volume'] = df[vol_col].cumsum()
    df['Cum_Vol_Price'] = (df[price_col] * df[vol_col]).cumsum()
    df['VWAP'] = df['Cum_Vol_Price'] / df['Cum_Volume']
    return df


def generate_signals(df):
    # RSI signal
    df['RSI_Signal'] = 0
    df.loc[df['RSI'] < 30, 'RSI_Signal'] = 1   # bullish (oversold)
    df.loc[df['RSI'] > 70, 'RSI_Signal'] = -1  # bearish (overbought)

    # MACD signal
    df['MACD_Signal'] = 0
    df.loc[df['MACD'] > df['Signal'], 'MACD_Signal'] = 1
    df.loc[df['MACD'] < df['Signal'], 'MACD_Signal'] = -1

    # Bollinger Band signal
    df['BB_Signal'] = 0
    df.loc[df['close'] < df['LowerBand'], 'BB_Signal'] = 1   # bullish
    df.loc[df['close'] > df['UpperBand'], 'BB_Signal'] = -1  # bearish

    # OBV signal
    df['OBV_Signal'] = 0
    df.loc[df['OBV'] > df['OBV'].shift(1), 'OBV_Signal'] = 1
    df.loc[df['OBV'] < df['OBV'].shift(1), 'OBV_Signal'] = -1

    # VWAP signal
    df['VWAP_Signal'] = 0
    df.loc[df['close'] > df['VWAP'], 'VWAP_Signal'] = 1
    df.loc[df['close'] < df['VWAP'], 'VWAP_Signal'] = -1

    # Combined sentiment from all indicators
    signal_cols = ['RSI_Signal', 'MACD_Signal', 'BB_Signal', 'OBV_Signal', 'VWAP_Signal']
    df['Combined_Score'] = df[signal_cols].sum(axis=1)

    # Normalize to -1, 0, 1 (majority vote style)
    df['Combined_Signal'] = df['Combined_Score'].apply(lambda x: 1 if x > 0 else (-1 if x < 0 else 0))
    
    return df



def aggregate_price_features(price_1h):
    price_1h = calculate_rsi(price_1h)
    price_1h = calculate_macd(price_1h)
    price_1h = calculate_bollinger_bands(price_1h)
    price_1h = calculate_obv(price_1h)
    price_1h = calculate_vwap(price_1h)
    price_1h = generate_signals(price_1h)
    price_1h = add_rolling_features(price_1h)
    price_1h = price_1h.drop(columns=["Cum_Volume", "Cum_Vol_Price"])
    # price_1h.reset_index(inplace=True)
    # price_1h.drop(columns=["index"])
    return price_1h


# ============================================================
# FEAR AND GREED PREPROCESSING
# ============================================================

def preprocess_fear_greed(fear_greed):
    fear_greed = fear_greed.rename(columns={
        "value": "fng_index",
        "value_classification": "fng_class"
    })
    
    sentiment_map = {
        "Extreme Fear": -2,
        "Fear": -1,
        "Neutral": 0,
        "Greed": 1,
        "Extreme Greed": 2
    }
    
    fear_greed["fng_sentiment"] = fear_greed["fng_class"].map(sentiment_map)
    fear_greed.drop(columns=["fng_class"], inplace=True)
    return fear_greed

# ============================================================
# HELPERS
# ============================================================

def read_raw_data(xcom_paths):
    """
    Read the raw data from the file paths stored in XComs.
    """
    dataframes = {}
    for name, path in xcom_paths.items():
        try:
            logger.info(f"Reading raw data from {path}...")
            df = pd.read_parquet(path)
            dataframes[name] = df
            logger.info(f"✅ Successfully read `{name}` with {len(df):,} rows.")
        except Exception as e:
            logger.error(f"❌ Failed to read `{name}` from {path}: {e}", exc_info=True)
    return dataframes


def save_intermediate_data(df, name, intermediate_dir):
    """
    Save processed dataframe as a Parquet file in the intermediate directory.
    """
    output_path = os.path.join(intermediate_dir, f"{name}_processed.parquet")
    try:
        df.to_parquet(output_path, index=False)
        logger.info(f"💾 Saved processed `{name}` to {output_path} ({len(df):,} rows).")
        return output_path
    except Exception as e:
        logger.error(f"❌ Failed to save `{name}` to Parquet: {e}", exc_info=True)
        return None


def preprocess_data(time_bin="1hr", **context):
    """
    Preprocess the raw data, save intermediate results, and push file paths to XCom.
    Input file paths are pulled from XCom (e.g., from a previous task named 'extract_raw_data').
    """
    # Get Airflow TaskInstance to pull/push XComs
    ti = context["ti"]

    # Pull the raw data paths from XCom (adjust 'extract_raw_data' to your upstream task ID)
    xcom_paths = ti.xcom_pull(task_ids='extract_raw_data', key='pulled_data_paths')
    
    if not xcom_paths or not isinstance(xcom_paths, dict):
        raise ValueError("❌ Failed to pull 'pulled_data_paths' from XCom. Ensure upstream task pushes it correctly.")

    # Define the base directory for saving intermediate data
    training_data_dir = TRAINING_DIR
    intermediate_data_dir = os.path.join(training_data_dir, "preprocessed")
    os.makedirs(intermediate_data_dir, exist_ok=True)

    # Read raw data from the pulled XCom paths
    dataframes = read_raw_data(xcom_paths)

    xcom_paths_processed = {}

    # Process News Sentiment
    if "news_sentiment" in dataframes:
        news_sentiment = dataframes["news_sentiment"]
        logger.info("Processing News Sentiment data...")
        news_sentiment = drop_columns_news_sentiment(news_sentiment)
        sentiment_1h = aggregate_sentiment_features(news_sentiment, freq=time_bin)
        sentiment_1h_path = save_intermediate_data(sentiment_1h, "sentiment_1h", intermediate_data_dir)
        if sentiment_1h_path:
            xcom_paths_processed["sentiment_1h"] = sentiment_1h_path

    # Process Historical Price
    if "historical_price" in dataframes:
        historical_price = dataframes["historical_price"]
        logger.info("Processing Historical Price data...")
        price_1h = resample_price(historical_price, time_bin)
        price_1h = aggregate_price_features(price_1h)
        price_1h_path = save_intermediate_data(price_1h, "price_1h", intermediate_data_dir)
        if price_1h_path:
            xcom_paths_processed["price_1h"] = price_1h_path

    # Process Fear & Greed Index
    if "fear_greed_index" in dataframes:
        fear_greed = dataframes["fear_greed_index"]
        logger.info("Processing Fear & Greed Index data...")
        fear_greed = preprocess_fear_greed(fear_greed)
        fear_greed_path = save_intermediate_data(fear_greed, "fear_greed", intermediate_data_dir)
        if fear_greed_path:
            xcom_paths_processed["fear_greed"] = fear_greed_path

    # Push processed paths to XCom
    ti.xcom_push(key="processed_data_paths", value=xcom_paths_processed)
    logger.info(f"📤 XCom pushed with processed file paths: {xcom_paths_processed}")
    
    logger.info("✅ All data processed and saved as intermediate Parquet files.")
    return True