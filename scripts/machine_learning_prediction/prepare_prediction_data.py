# scripts/machine_learning/prepare_inference_data.py

import os
import pandas as pd
import numpy as np
import joblib
from datetime import datetime
from utils.logger import get_logger
from configs.config import PREDICTION_DIR, TRAINING_DIR
from scripts.machine_learning_training.prepare_training_data import FEATURES, merging_data_sources

logger = get_logger("prepare_prediction_data")

# ============================================================
# INFERENCE DATA PREPARATION
# ============================================================

def prepare_prediction_data(
    lookback_window: int = 120,
    training_artifact_path: str = None,
    **context
):
    """
    Prepare scaled feature sequences for inference using a trained scaler.

    Parameters:
        lookback_window (int): Number of timesteps per input sequence.
        training_artifact_path (str): Path to the saved training artifact containing the feature scaler.
    """
    ti = context["ti"]

    # ----------------------------------------------------------------------
    # Step 1. Load preprocessed data paths from XCom
    # ----------------------------------------------------------------------
    processed_paths = ti.xcom_pull(task_ids="preprocess_latest_data", key="processed_data_paths")
    if not processed_paths:
        raise ValueError("❌ No processed data paths found in XCom. Check upstream preprocessing task.")

    logger.info("📂 Loading preprocessed Parquet files for inference...")
    price_1h = pd.read_parquet(processed_paths["price_1h"])
    sentiment_1h = pd.read_parquet(processed_paths["sentiment_1h"])
    fear_greed = pd.read_parquet(processed_paths["fear_greed"])

    # ----------------------------------------------------------------------
    # Step 2. Merge data sources (same as training merge)
    # ----------------------------------------------------------------------
    logger.info("🔗 Merging sentiment, price, and fear/greed data...")
    merged = merging_data_sources(price_1h, sentiment_1h, fear_greed)
    merged = merged.dropna(subset=FEATURES, how="any").reset_index(drop=True)
    logger.info(f"✅ Merged dataframe shape: {merged.shape}")

    # ----------------------------------------------------------------------
    # Step 3. Load trained scaler
    # ----------------------------------------------------------------------
    if training_artifact_path is None:
        training_artifact_path = os.path.join(TRAINING_DIR, "model", "training_artifacts_latest.joblib")

    if not os.path.exists(training_artifact_path):
        raise FileNotFoundError(f"❌ Training artifact not found: {training_artifact_path}")

    logger.info(f"📦 Loading trained scaler from {training_artifact_path}")
    training_artifact = joblib.load(training_artifact_path)
    scaler = training_artifact["metadata"]["feature_scaler"]

    # ----------------------------------------------------------------------
    # Step 4. Scale features
    # ----------------------------------------------------------------------
    logger.info("⚖️ Scaling feature columns using the training scaler...")
    scaled_features = scaler.transform(merged[FEATURES])
    merged_scaled = merged.copy()
    merged_scaled[FEATURES] = scaled_features

    # ----------------------------------------------------------------------
    # Step 5. Create sequences (same logic as training)
    # ----------------------------------------------------------------------
    logger.info(f"🧩 Creating inference sequences with lookback={lookback_window}")
    X_inference, base_prices, timestamps = [], [], []

    close_prices = merged_scaled["close"].values
    time_indices = merged_scaled["time"].values

    for i in range(lookback_window, len(merged_scaled)):
        X_inference.append(merged_scaled[FEATURES].iloc[i - lookback_window:i].values)
        base_prices.append(close_prices[i])
        timestamps.append(time_indices[i])

    X_inference = np.array(X_inference, dtype=np.float32)
    base_prices = np.array(base_prices)
    timestamps = np.array(timestamps)

    logger.info(f"✅ Final inference tensor shape: {X_inference.shape}")

    metadata = {
        "base_prices": base_prices,
        "timestamps": timestamps,
        "lookback_window": lookback_window,
        "feature_list": FEATURES,
    }

    # ----------------------------------------------------------------------
    # Step 6. Save output
    # ----------------------------------------------------------------------
    output_dir = os.path.join(PREDICTION_DIR, "prepared")
    os.makedirs(output_dir, exist_ok=True)

    timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = os.path.join(output_dir, f"inference_data_lb{lookback_window}_{timestamp_str}.joblib")

    joblib.dump({
        "X_inference": X_inference,
        "metadata": metadata,
        "feature_scaler": scaler,
    }, output_path)


    logger.info(f"💾 Saved prepared inference data to {output_path}")

    # ----------------------------------------------------------------------
    # Step 7. Push to XCom for downstream prediction task
    # ----------------------------------------------------------------------
    ti.xcom_push(key="inference_data_path", value=output_path)
    logger.info("📤 XCom pushed with inference data path.")

    return output_path
