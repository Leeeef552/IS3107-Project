import os
import joblib
import torch
import numpy as np
import pandas as pd
from datetime import datetime
from scripts.machine_learning_training.model import LSTM_Model
from utils.logger import get_logger
from configs.config import PREDICTION_DIR, TRAINING_DIR

logger = get_logger("predict.py")

def predict_with_trained_model(**context):
    """
    Airflow task: Run inference using the most recent trained model.

    - Loads inference data (which now includes the feature scaler)
    - Unscales base prices using the embedded feature scaler
    - Runs model inference and saves predictions to timestamped CSV
    """

    ti = context["ti"]

    # ----------------------------------------------------------------------
    # Step 1. Load inference data
    # ----------------------------------------------------------------------
    inference_data_path = ti.xcom_pull(task_ids="prepare_inference_data", key="inference_data_path")
    if not inference_data_path or not os.path.exists(inference_data_path):
        raise FileNotFoundError(f"❌ Inference data not found: {inference_data_path}")

    logger.info(f"📂 Loading inference data from {inference_data_path}")
    inference_data = joblib.load(inference_data_path)
    X_inference = inference_data["X_inference"]
    metadata = inference_data["metadata"]
    feature_scaler = inference_data.get("feature_scaler", None)

    # ----------------------------------------------------------------------
    # Step 2. Load training artifact (latest, for model weights only)
    # ----------------------------------------------------------------------
    training_artifact_path = ti.xcom_pull(task_ids="train_model", key="training_artifacts_path")
    if not training_artifact_path or not os.path.exists(training_artifact_path):
        training_artifact_path = os.path.join(TRAINING_DIR, "model", "training_artifacts_latest.joblib")

    if not os.path.exists(training_artifact_path):
        raise FileNotFoundError(f"❌ Training artifact not found: {training_artifact_path}")

    artifact = joblib.load(training_artifact_path)
    logger.info(f"📦 Using model weights from: {training_artifact_path}")

    # ----------------------------------------------------------------------
    # Step 3. Load model
    # ----------------------------------------------------------------------
    model_path = artifact["model_state_dict_path"]
    input_size = artifact["config"]["input_size"]

    model = LSTM_Model(input_size=input_size)
    model.load_state_dict(torch.load(model_path, map_location="cpu"))
    model.eval()

    # ----------------------------------------------------------------------
    # Step 4. Unscale base prices using embedded feature scaler
    # ----------------------------------------------------------------------
    base_prices_scaled = np.array(metadata["base_prices"]).reshape(-1, 1)
    feature_list = metadata.get("feature_list", [])

    if feature_scaler is not None:
        try:
            if "close" in feature_list:
                close_idx = feature_list.index("close")
            else:
                close_idx = 0  # fallback to first feature

            dummy = np.zeros((len(base_prices_scaled), len(feature_list)))
            dummy[:, close_idx] = base_prices_scaled.flatten()
            unscaled = feature_scaler.inverse_transform(dummy)
            base_prices = unscaled[:, close_idx]
            logger.info("🔁 Successfully unscaled base prices using embedded scaler")
        except Exception as e:
            logger.error(f"❌ Failed to unscale base prices: {e}")
            base_prices = base_prices_scaled.flatten()
    else:
        logger.warning("⚠️ No scaler found in inference data — base prices remain scaled")
        base_prices = base_prices_scaled.flatten()

    logger.info(f"Base prices (post-unscale) range: {base_prices.min():.2f}–{base_prices.max():.2f}")

    # ----------------------------------------------------------------------
    # Step 5. Run model inference
    # ----------------------------------------------------------------------
    logger.info("🧠 Running model inference...")
    with torch.no_grad():
        preds = model(torch.tensor(X_inference, dtype=torch.float32)).numpy().flatten()

    predict_returns = artifact["metadata"].get("predict_returns", True)

    if predict_returns:
        predicted_price = base_prices * (1 + preds)
        logger.info("✅ Interpreting outputs as RETURNS (converted to absolute prices)")
    else:
        predicted_price = preds
        logger.info("✅ Interpreting outputs as ABSOLUTE PRICES")

    timestamps = metadata["timestamps"]

    df_predictions = pd.DataFrame({
        "timestamp": timestamps,
        "base_price": base_prices,
        "predicted_change": preds,
        "predicted_price": predicted_price
    })

    # ----------------------------------------------------------------------
    # Step 6. Save results
    # ----------------------------------------------------------------------
    output_dir = os.path.join(PREDICTION_DIR, "output")
    os.makedirs(output_dir, exist_ok=True)

    timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")

    df_predictions["timestamp"] = pd.to_datetime(df_predictions["timestamp"])
    cutoff_time = df_predictions["timestamp"].max() - pd.Timedelta(hours=12)
    df_recent = df_predictions[df_predictions["timestamp"] >= cutoff_time]

    logger.info(f"🕒 Keeping predictions from last 12 hours only: "
                f"{cutoff_time} – {df_predictions['timestamp'].max()} "
                f"({len(df_recent)} of {len(df_predictions)} rows)")

    output_path = os.path.join(output_dir, f"predictions_{timestamp_str}.csv")

    df_recent.to_csv(output_path, index=False)
    logger.info(f"💾 Saved last 12 hours of predictions to {output_path}")
    logger.info(f"Predicted price range: {df_recent['predicted_price'].min():.2f}–"
                f"{df_recent['predicted_price'].max():.2f}")

    # ----------------------------------------------------------------------
    # Step 7. Push output to XCom
    # ----------------------------------------------------------------------
    ti.xcom_push(key="prediction_output_path", value=output_path)
    logger.info("📤 XCom pushed with prediction output path.")

    return output_path
