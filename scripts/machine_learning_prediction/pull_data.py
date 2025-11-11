import psycopg2
import pandas as pd
from psycopg2 import Error
from datetime import datetime, timedelta
from configs.config import DB_CONFIG, PREDICTION_DIR
from utils.logger import get_logger
import os

logger = get_logger("pull_data")

def load_tables_to_dataframes(host, port, database, username, password, lookback_window):
    conn = None
    dataframes = {}

    today = datetime.today()
    price_cutoff = today - timedelta(days=lookback_window+20)
    sentiment_cutoff = today - timedelta(days=lookback_window+5)
    greed_cutoff = today - timedelta(days=lookback_window+5)

    try:
        logger.info("Connecting to PostgreSQL database...")
        conn = psycopg2.connect(
            host=host,
            port=port,
            dbname=database,
            user=username,
            password=password
        )
        logger.info("✅ Database connection established successfully.")

        queries = {
            "historical_price": f"""
                SELECT * FROM historical_price
                WHERE time >= '{price_cutoff.strftime('%Y-%m-%d')}'
            """,
            "news_sentiment": f"""
                SELECT * FROM news_sentiment
                WHERE time >= '{sentiment_cutoff.strftime('%Y-%m-%d')}'
            """,
            "fear_greed_index": f"""
                SELECT * FROM fear_greed_index
                WHERE time >= '{greed_cutoff.strftime('%Y-%m-%d')}'
            """
        }

        for name, query in queries.items():
            try:
                logger.info(f"Pulling `{name}` data...")
                df = pd.read_sql_query(query, conn)
                dataframes[name] = df
                logger.info(f"✅ Loaded `{name}` ({len(df):,} rows, {len(df.columns)} columns)")
            except Exception as e:
                logger.error(f"❌ Failed to load `{name}`: {e}", exc_info=True)

    except Error as e:
        logger.error(f"❌ Database connection or query error: {e}", exc_info=True)
        raise

    except Exception as e:
        logger.error(f"❌ Unexpected error during data loading: {e}", exc_info=True)
        raise

    finally:
        if conn:
            conn.close()
            logger.info("🔒 Database connection closed.")

    return dataframes


def pull_data(lookback_window=7, **context):
    """
    Top-level function to pull all datasets and save as Parquet,
    then push file paths to Airflow XComs for downstream tasks.
    """
    # Define the base directory for saving the prediction data
    prediction_data_dir = PREDICTION_DIR
    raw_data_dir = os.path.join(prediction_data_dir, "raw")  # New subdirectory for prediction data
    os.makedirs(raw_data_dir, exist_ok=True)  # Ensure the raw data subdirectory exists

    HOST = DB_CONFIG.get("host")
    PORT = DB_CONFIG.get("port")
    USER = DB_CONFIG.get("user")
    PASS = DB_CONFIG.get("password")
    DB_NAME = DB_CONFIG.get("dbname")

    ti = context["ti"]  # Airflow TaskInstance for XCom push

    try:
        logger.info("🚀 Starting data extraction process...")
        dataframes = load_tables_to_dataframes(HOST, PORT, DB_NAME, USER, PASS, lookback_window)

        xcom_paths = {}

        for name, df in dataframes.items():
            # Save the Parquet file in the 'raw' subdirectory
            output_path = os.path.join(raw_data_dir, f"{name}.parquet")
            try:
                df.to_parquet(output_path, index=False)
                logger.info(f"💾 Saved `{name}` to {output_path} ({len(df):,} rows).")
                xcom_paths[name] = output_path
            except Exception as e:
                logger.error(f"❌ Failed to save `{name}` to Parquet: {e}", exc_info=True)

        # Push all paths as one XCom dictionary
        ti.xcom_push(key="pulled_data_paths", value=xcom_paths)
        logger.info(f"📤 XCom pushed with file paths: {xcom_paths}")

        logger.info("✅ All tables pulled and saved successfully as Parquet.")
        return True

    except Exception as e:
        logger.error(f"❌ Data pulling failed: {e}", exc_info=True)
        ti.xcom_push(key="pulled_data_paths", value={})
        return False