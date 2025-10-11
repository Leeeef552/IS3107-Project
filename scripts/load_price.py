import os
import sys
import pandas as pd
import psycopg2
import sqlparse
from io import StringIO
from dotenv import load_dotenv

# ----------------------------------------------------------------------
# ✅ LOGGING CONFIGURATION (Singapore Time)
# ----------------------------------------------------------------------
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
        log.error(f"❌ Failed to connect to database: {e}")
        sys.exit(1)


def execute_schema_script(conn, script_path: str):
    """Execute SQL schema file to set up tables/hypertables."""
    if not os.path.exists(script_path):
        log.error(f"❌ Schema file not found: {os.path.abspath(script_path)}")
        sys.exit(1)

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

def execute_aggregation_script_separate_conn(config, script_path: str):
    """Execute SQL script for continuous aggregates using separate connection."""
    if not os.path.exists(script_path):
        log.warning(f"⚠️ Aggregation script not found: {os.path.abspath(script_path)}")
        log.info("Skipping continuous aggregates setup")
        return

    conn = psycopg2.connect(**config)
    conn.autocommit = True  # ✅ Add this line
    cur = conn.cursor()

    try:
        with open(script_path, "r") as file:
            sql_commands = file.read()

        for statement in sqlparse.split(sql_commands):
            stmt = statement.strip()
            if stmt:
                try:
                    cur.execute(stmt)
                except Exception as e:
                    log.warning(f"⚠️ Skipping failed aggregation statement:\n{stmt[:100]}...\nError: {e}")
        log.info("✅ Continuous aggregates executed successfully")

    finally:
        cur.close()
        conn.close()

def load_parquet_data(parquet_path: str) -> pd.DataFrame:
    """Load and preprocess Parquet data for ingestion."""
    if not os.path.exists(parquet_path):
        log.error(f"❌ Parquet file not found: {os.path.abspath(parquet_path)}")
        sys.exit(1)

    try:
        df = pd.read_parquet(parquet_path)
        log.info(f"✅ Loaded Parquet: {len(df):,} rows × {len(df.columns)} columns")
    except Exception as e:
        log.error(f"❌ Error reading Parquet file: {e}")
        sys.exit(1)

    # Convert and rename columns
    df["Timestamp"] = pd.to_datetime(df["Timestamp"], unit="s")
    df = df.rename(columns={
        "Timestamp": "time",
        "Open": "open",
        "High": "high",
        "Low": "low",
        "Close": "close",
        "Volume": "volume"
    })

    # Ensure time is first and sorted
    df = df[["time", "open", "high", "low", "close", "volume"]]
    df = df.sort_values("time").reset_index(drop=True)
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
        log.error(f"❌ Failed to load data into '{table_name}': {e}")
        sys.exit(1)
    finally:
        cur.close()


# ----------------------------------------------------------------------
# ✅ MAIN ENTRY POINT
# ----------------------------------------------------------------------
def main():
    SCHEMA_PATH = "schema/init_price_db.sql"
    AGGREGATION_PATH = "schema/aggregate_views.sql"
    PARQUET_PATH = "historical_data/btcusd_1-min_data.parquet"
    TABLE_NAME = "historical_price"

    log.info("=== Historical Price Data Loader to TimescaleDB Started ===")

    # 1. Load DB config and connect
    db_config = get_db_config()
    conn = connect_to_db(db_config)

    # 2. Execute base schema
    execute_schema_script(conn, SCHEMA_PATH)

    # 3. Load and preprocess data
    df = load_parquet_data(PARQUET_PATH)

    # 4. Bulk insert historical data
    bulk_insert_data(conn, df, TABLE_NAME)

    # 5. Close main connection before creating aggregates
    conn.close()

    # 6. Create continuous aggregates using separate connection (no transaction)
    execute_aggregation_script_separate_conn(db_config, AGGREGATION_PATH)

    log.info("=== Historical Price Data Loader to TimescaleDB Finished ===")


if __name__ == "__main__":
    sys.exit(main())