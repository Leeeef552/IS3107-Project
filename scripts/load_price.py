import os
import sys
import pandas as pd
import psycopg2
import sqlparse
from io import StringIO
from dotenv import load_dotenv
from utils.logger import get_logger

log = get_logger("load_price.py")

# ----------------------------------------------------------------------
# ✅ DATABASE CONFIGURATION
# ----------------------------------------------------------------------
def get_db_config():
    """Load database configuration from environment variables."""
    load_dotenv()
    return {
        "host": os.getenv("TIMESCALE_HOST", "localhost"),
        "port": int(os.getenv("TIMESCALE_PORT", 5432)),
        "user": os.getenv("TIMESCALE_USER"),
        "password": os.getenv("TIMESCALE_PASSWORD"),
        "dbname": os.getenv("TIMESCALE_DBNAME", "postgres"),
    }

# ----------------------------------------------------------------------
# ✅ CORE FUNCTIONS
# ----------------------------------------------------------------------
def connect_to_db(config):
    """Establish connection to TimescaleDB."""
    try:
        conn = psycopg2.connect(**config)
        log.info(f"✅ Connected to TimescaleDB at {config['host']}:{config['port']}/{config['dbname']}")
        return conn
    except Exception as e:
        log.exception(f"❌ Failed to connect to database: {e}")
        raise

def execute_schema_script(conn, script_path: str):
    """Execute SQL schema file to set up tables/hypertables."""
    if not os.path.exists(script_path):
        raise FileNotFoundError(f"Schema file not found: {os.path.abspath(script_path)}")

    with open(script_path, "r") as file:
        sql_commands = file.read()

    cur = conn.cursor()
    for statement in sqlparse.split(sql_commands):
        stmt = statement.strip()
        if stmt:
            try:
                cur.execute(stmt)
            except Exception as e:
                log.warning(f"⚠️ Skipping failed statement:\n{stmt[:100]}...\nError: {e}")
    conn.commit()
    cur.close()
    log.info("✅ Schema executed successfully")

def load_parquet_data(parquet_path: str) -> pd.DataFrame:
    """Load and preprocess Parquet data for ingestion."""
    if not os.path.exists(parquet_path):
        raise FileNotFoundError(f"Parquet file not found: {os.path.abspath(parquet_path)}")

    df = pd.read_parquet(parquet_path)
    log.info(f"✅ Loaded Parquet: {len(df):,} rows × {len(df.columns)} columns")

    df["Timestamp"] = pd.to_datetime(df["Timestamp"], unit="s")
    df = df.rename(columns={
        "Timestamp": "time",
        "Open": "open",
        "High": "high",
        "Low": "low",
        "Close": "close",
        "Volume": "volume"
    })
    df = df[["time", "open", "high", "low", "close", "volume"]].sort_values("time").reset_index(drop=True)
    log.info("✅ Data preprocessing completed")
    return df

def bulk_insert_data(conn, df: pd.DataFrame, table_name: str):
    """Efficiently bulk insert DataFrame into TimescaleDB using COPY."""
    output = StringIO()
    df.to_csv(output, sep='\t', header=False, index=False, na_rep='\\N')
    output.seek(0)

    cur = conn.cursor()
    try:
        cur.copy_from(
            output,
            table=table_name,
            columns=('time', 'open', 'high', 'low', 'close', 'volume'),
            sep='\t',
            null='\\N'
        )
        conn.commit()
        log.info(f"✅ Successfully loaded {len(df):,} rows into '{table_name}'")
    except Exception as e:
        conn.rollback()
        log.exception(f"❌ Failed to load data into '{table_name}': {e}")
        raise
    finally:
        cur.close()

# ----------------------------------------------------------------------
# ✅ MAIN ENTRY POINT
# ----------------------------------------------------------------------
def main():
    SCHEMA_PATH = "schema/init_price_db.sql"
    PARQUET_PATH = "historical_data/btcusd_1-min_data.parquet"
    TABLE_NAME = "historical_price"

    log.info("=== Historical Price Data Loader to TimescaleDB Started ===")

    db_config = get_db_config()
    conn = connect_to_db(db_config)

    execute_schema_script(conn, SCHEMA_PATH)
    df = load_parquet_data(PARQUET_PATH)
    bulk_insert_data(conn, df, TABLE_NAME)

    conn.close()
    log.info("=== Historical Price Data Loader Finished ===")

if __name__ == "__main__":
    main()
