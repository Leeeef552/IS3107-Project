# %% [markdown]
# # ML - Data Extraction Script (Airflow Task)

# %%
import psycopg2
import pandas as pd
from psycopg2 import sql, Error
from datetime import datetime, timedelta
from utils.logger import get_logger
from configs.config import DB_CONFIG

log = get_logger("run_data_extraction.py")

def load_tables_to_dataframes(host, port, database, username, password):
    """Loads data from PostgreSQL into DataFrames with a 180-day cutoff."""
    conn = None
    dataframes = {}

    # Calculate dynamic cutoff date (180 days ago)
    cutoff_date = (datetime.utcnow() - timedelta(days=180)).strftime("%Y-%m-%d")
    log.info(f"Using cutoff date: {cutoff_date}")

    try:
        conn = psycopg2.connect(
            host=host,
            port=port,
            dbname=database,
            user=username,
            password=password
        )
        log.info("Connected to the database successfully.")

        # Load historical_price (last 180 days)
        historical_query = f"""
            SELECT * FROM historical_price 
            WHERE time >= '{cutoff_date}'
        """
        dataframes['historical_price'] = pd.read_sql_query(historical_query, conn)
        log.info(f"Loaded {len(dataframes['historical_price'])} rows from historical_price.")

        # Load full news_sentiment table
        news_query = "SELECT * FROM news_sentiment"
        dataframes['news_sentiment'] = pd.read_sql_query(news_query, conn)
        log.info(f"Loaded {len(dataframes['news_sentiment'])} rows from news_sentiment.")

        # Load fear_greed_index (last 180 days)
        greed_query = f"""
            SELECT * FROM fear_greed_index 
            WHERE time >= '{cutoff_date}'
        """
        dataframes['fear_greed_index'] = pd.read_sql_query(greed_query, conn)
        log.info(f"Loaded {len(dataframes['fear_greed_index'])} rows from fear_greed_index.")

    except Error as e:
        log.error(f"❌ Database error: {e}")
    except Exception as e:
        log.exception(f"Unexpected error: {e}")
    finally:
        if conn:
            conn.close()
            log.info("Database connection closed.")

    return dataframes

def run_data_extraction():
    """
    Entry function to be called by Airflow DAG.
    Handles database config, extraction, and logging summary.
    """
    log.info("Starting data extraction task...")

    HOST = "localhost"
    PORT = DB_CONFIG["port"]
    USER = DB_CONFIG["user"]
    PASS = DB_CONFIG["password"]
    DB_NAME = DB_CONFIG["dbname"]

    dataframes = load_tables_to_dataframes(HOST, PORT, DB_NAME, USER, PASS)

    for name, df in dataframes.items():
        log.info(f"{name} → Rows: {len(df)}, Columns: {len(df.columns)}")

    log.info("✅ Data extraction completed successfully.")
    return dataframes


# For standalone local run or testing
if __name__ == "__main__":
    run_data_extraction()