import psycopg2
import pandas as pd
from psycopg2 import sql
import os
from datetime import timedelta
from configs.config import DB_CONFIG
from utils.logger import get_logger

logger = get_logger("save_predictions")


def save_predictions_to_db(
    table_name: str = "model_predictions",
    **context
):
    """
    Save 12-hour summary (low, high, mean, variance) of model predictions into PostgreSQL.

    Expects:
        - XCom key: 'prediction_output_path' → CSV file from predict_with_trained_model()
          containing columns: ['timestamp', 'predicted_price', 'predicted_change', 'base_price']

    Process:
        - Load predictions
        - Filter last 12 hours
        - Compute low/high/mean/variance
        - Save one record (or per run) to DB
    """

    ti = context["ti"]

    prediction_file = ti.xcom_pull(task_ids="run_predictions", key="prediction_output_path")
    if not prediction_file or not os.path.exists(prediction_file):
        raise FileNotFoundError(f"❌ Prediction file not found: {prediction_file}")

    predictions_df = pd.read_csv(prediction_file)
    if predictions_df.empty:
        logger.warning("⚠️ No predictions to save. Skipping DB write.")
        return False

    # ----------------------------------------------------------------------
    # 🕒 Filter to last 12 hours
    # ----------------------------------------------------------------------
    predictions_df["timestamp"] = pd.to_datetime(predictions_df["timestamp"])
    latest_time = predictions_df["timestamp"].max()
    cutoff_time = latest_time - timedelta(hours=12)
    df_recent = predictions_df[predictions_df["timestamp"] >= cutoff_time]

    if df_recent.empty:
        logger.warning("⚠️ No predictions found in last 12 hours. Skipping DB write.")
        return False

    # ----------------------------------------------------------------------
    # 📊 Compute summary statistics
    # ----------------------------------------------------------------------
    low = df_recent["predicted_price"].min()
    high = df_recent["predicted_price"].max()
    mean = df_recent["predicted_price"].mean()
    variance = df_recent["predicted_price"].var(ddof=0)  # population variance

    base_mean = df_recent["base_price"].mean() if "base_price" in df_recent.columns else None

    logger.info(f"📈 12-hour summary → low={low:.4f}, high={high:.4f}, mean={mean:.4f}, var={variance:.6f}")

    # ----------------------------------------------------------------------
    # 🧱 Prepare row for database
    # ----------------------------------------------------------------------
    run_id = context.get("run_id") or context.get("dag_run").run_id
    created_at = pd.Timestamp.now(tz="UTC")
    prediction_time = latest_time  # anchor summary to most recent prediction time

    row = (prediction_time, run_id, low, high, mean, variance, base_mean, created_at)

    # ----------------------------------------------------------------------
    # 🗄️ Database interaction
    # ----------------------------------------------------------------------
    conn = None
    try:
        conn = psycopg2.connect(
            host=DB_CONFIG["host"],
            port=DB_CONFIG["port"],
            dbname=DB_CONFIG["dbname"],
            user=DB_CONFIG["user"],
            password=DB_CONFIG["password"]
        )
        conn.autocommit = True
        cur = conn.cursor()

        # 1️⃣ Ensure table exists
        create_table_query = sql.SQL("""
            CREATE TABLE IF NOT EXISTS {} (
                prediction_time TIMESTAMPTZ NOT NULL,
                run_id TEXT NOT NULL,
                predicted_low DOUBLE PRECISION,
                predicted_high DOUBLE PRECISION,
                predicted_mean DOUBLE PRECISION,
                predicted_variance DOUBLE PRECISION,
                base_price DOUBLE PRECISION,
                created_at TIMESTAMPTZ DEFAULT NOW(),
                PRIMARY KEY (prediction_time, run_id)
            );
        """).format(sql.Identifier(table_name))
        cur.execute(create_table_query)
        logger.info(f"✅ Table '{table_name}' verified or created.")

        # 2️⃣ Insert or Upsert
        insert_query = sql.SQL("""
            INSERT INTO {} (
                prediction_time, run_id,
                predicted_low, predicted_high,
                predicted_mean, predicted_variance,
                base_price, created_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (prediction_time, run_id)
            DO UPDATE SET
                predicted_low = EXCLUDED.predicted_low,
                predicted_high = EXCLUDED.predicted_high,
                predicted_mean = EXCLUDED.predicted_mean,
                predicted_variance = EXCLUDED.predicted_variance,
                base_price = EXCLUDED.base_price,
                created_at = EXCLUDED.created_at;
        """).format(sql.Identifier(table_name))

        cur.execute(insert_query.as_string(conn), row)
        logger.info(f"✅ Inserted summary row into `{table_name}` for run_id={run_id}")

        cur.close()
        conn.close()
        return True

    except Exception as e:
        logger.error(f"❌ Failed to save predictions: {e}", exc_info=True)
        if conn:
            conn.rollback()
        return False

    finally:
        if conn:
            conn.close()
            logger.info("🔒 Database connection closed.")
