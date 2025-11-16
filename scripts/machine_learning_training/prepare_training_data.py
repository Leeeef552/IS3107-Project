import os
import pandas as pd
import torch
import numpy as np
import joblib
from utils.logger import get_logger
from configs.config import TRAINING_DIR
from sklearn.preprocessing import StandardScaler

logger = get_logger("prepare_training_data.py")

FEATURES = [
    'article_count', 'sentiment_mean', 'sentiment_median', 'sentiment_std', 
    'confidence_mean', 'confidence_std', 'weighted_sentiment', 'weighted_std', 
    'confidence_weighted_count', 'positive_ratio', 'negative_ratio', 
    'neutral_ratio', 'polarized_ratio', 'conflict_score', 'max_disagreement', 
    'is_high_conflict', 'sentiment_score', 'confidence', 'volatility', 'is_conflict', 
    'open', 'high', 'low', 'close', 'volume',
    'RSI', 'MACD', 'Signal', 'MACD_Hist', 
    'SMA', 'STD', 'UpperBand', 'LowerBand', 'OBV', 'VWAP', 
    'RSI_Signal', 'MACD_Signal', 'BB_Signal', 'OBV_Signal', 'VWAP_Signal', 'Combined_Score', 'Combined_Signal', 
    'rolling_volatility', 'rolling_return', 'fng_index', 'fng_sentiment'
]

LABEL_COLUMN = 'target'


# ============================================================
# DATA MERGING AND LABEL CREATION
# ============================================================
def merging_data_sources(price_1h, sentiment_1h, fear_greed):
    price_1h = price_1h.sort_values("time").reset_index(drop=True)
    fear_greed = fear_greed.sort_values("time").reset_index(drop=True)
    sentiment_1h = sentiment_1h.sort_values("time").reset_index(drop=True)

    price_with_fear = pd.merge_asof(
        price_1h,
        fear_greed,
        on="time",
        direction="backward"
    )

    merged = price_with_fear.merge(
        sentiment_1h,
        on="time",
        how="left"
    )

    return merged


def generate_labels(df, target_column='close', forecast_horizon=12):
    if forecast_horizon <= 0:
        raise ValueError("forecast_horizon must be a positive integer.")
    df['target'] = df[target_column].shift(-forecast_horizon)
    df = df.dropna(axis=0)
    return df


# ============================================================
# TRAINING DATA PREPARATION
# ============================================================

def prepare_data_for_training(df, features, label_column, lookback_window, test_size=0.2, predict_returns=True):
    df = df.copy()
    original_close = df['close'].values
    original_time = df['time'].values

    if predict_returns:
        df['target_returns'] = (df[label_column] - df['close']) / df['close']
        target_col = 'target_returns'
    else:
        target_col = label_column

    print(f"\n📊 Target Statistics (BEFORE scaling):")
    print(f" Mean: {df[target_col].mean():.6f}")
    print(f" Std: {df[target_col].std():.6f}")
    print(f" Min: {df[target_col].min():.6f}, Max: {df[target_col].max():.6f}")

    df = df.drop(columns=['time'], errors='ignore')

    split_idx = int(len(df) * (1 - test_size))
    df_train = df.iloc[:split_idx]
    df_test = df.iloc[split_idx:]

    feature_scaler = StandardScaler()
    df_train_scaled = df_train.copy()
    df_test_scaled = df_test.copy()

    df_train_scaled[features] = feature_scaler.fit_transform(df_train[features])
    df_test_scaled[features] = feature_scaler.transform(df_test[features])

    print(f"\n📊 Target Statistics (AFTER scaling):")
    print(f" Train Mean: {df_train_scaled[target_col].mean():.6f}")
    print(f" Train Std: {df_train_scaled[target_col].std():.6f}")
    print(f" Test Mean: {df_test_scaled[target_col].mean():.6f}")
    print(f" Test Std: {df_test_scaled[target_col].std():.6f}")

    def create_sequences(data, features, label_col, window, orig_close_segment, orig_time_segment):
        X, Y, base_prices, time_indices = [], [], [], []
        for i in range(window, len(data)):
            X.append(data[features].iloc[i - window:i].values)
            Y.append(data[label_col].iloc[i])
            base_prices.append(orig_close_segment[i])
            time_indices.append(orig_time_segment[i])
        return (
            np.array(X, dtype=np.float32),
            np.array(Y, dtype=np.float32),
            np.array(base_prices),
            np.array(time_indices)
        )

    X_train, Y_train, _, train_time_indices = create_sequences(
        df_train_scaled, features, target_col,
        lookback_window,
        original_close[:split_idx],
        original_time[:split_idx]
    )
    X_test, Y_test, base_prices_test, test_time_indices = create_sequences(
        df_test_scaled, features, target_col,
        lookback_window,
        original_close[split_idx:],
        original_time[split_idx:]
    )

    metadata = {
        'predict_returns': predict_returns,
        'base_prices_test': base_prices_test,
        'original_close': original_close,
        'feature_scaler': feature_scaler,
        'train_time_indices': train_time_indices,
        'test_time_indices': test_time_indices
    }

    return X_train, X_test, Y_train, Y_test, metadata


# ============================================================
# AIRFLOW ENTRY POINT — uses op_kwargs and XCom
# ============================================================

def prepare_training_data(
    lookback_window: int = 120,
    forecast_horizon: int = 12,
    test_size: float = 0.2,
    predict_returns: bool = True,
    **context
):
    """
    Airflow task to prepare final training tensors.
    
    Parameters (passed via op_kwargs):
        lookback_window (int): Timesteps in input sequence.
        forecast_horizon (int): How many steps ahead to predict.
        test_size (float): Fraction for test split.
        predict_returns (bool): Whether to predict % returns instead of price.
    """
    ti = context["ti"]

    # Pull paths from XCom (from 'preprocess_data' task)
    processed_paths = ti.xcom_pull(task_ids='preprocess_data', key='processed_data_paths')
    if not processed_paths:
        raise ValueError("❌ No processed data paths in XCom. Check upstream task.")

    logger.info("📂 Loading intermediate Parquet files...")
    price_1h = pd.read_parquet(processed_paths['price_1h'])
    sentiment_1h = pd.read_parquet(processed_paths['sentiment_1h'])
    fear_greed = pd.read_parquet(processed_paths['fear_greed'])

    logger.info(f"✅ Loaded: price({len(price_1h)}), sentiment({len(sentiment_1h)}), fng({len(fear_greed)})")

    # Merge and label
    merged = merging_data_sources(price_1h, sentiment_1h, fear_greed)
    df = generate_labels(df=merged, target_column="close", forecast_horizon=forecast_horizon)

    # Prepare sequences
    X_train, X_test, Y_train, Y_test, metadata = prepare_data_for_training(
        df=df,
        features=FEATURES,
        label_column=LABEL_COLUMN,
        lookback_window=lookback_window,
        test_size=test_size,
        predict_returns=predict_returns
    )

    logger.info(f"✅ Final shapes – Train: {X_train.shape}, Test: {X_test.shape}")

    # Save as joblib
    output_dir = os.path.join(TRAINING_DIR, "train_test_splits")
    os.makedirs(output_dir, exist_ok=True)

    from datetime import datetime
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    joblib_path = os.path.join(output_dir, f"training_data_lb{lookback_window}_fh{forecast_horizon}_{timestamp}.joblib")

    joblib.dump({
        'X_train': X_train,
        'X_test': X_test,
        'Y_train': Y_train,
        'Y_test': Y_test,
        'metadata': metadata
    }, joblib_path)

    logger.info(f"💾 Saved training data to: {joblib_path}")

    # Push path to XCom for next task
    ti.xcom_push(key="training_data_path", value=joblib_path)

    return joblib_path
