import pandas as pd
import psycopg2
import sqlparse
from io import StringIO
from utils.logger import get_logger
from configs.config import DB_CONFIG, SCHEMA_DIR, PARQUET_PATH

# ----------------------------------------------------------------------
# LOGGING CONFIGURATION (Singapore Time)
# ----------------------------------------------------------------------
from utils.logger import get_logger

log = get_logger("load_price.py")

# ----------------------------------------------------------------------
# HELPER FUNCTIONS
# ----------------------------------------------------------------------
def connect_to_db():
    conn = psycopg2.connect(**DB_CONFIG)
    log.info(f"Connected to TimescaleDB: {DB_CONFIG['host']}:{DB_CONFIG['port']}")
    return conn

def execute_schema_script(conn, schema_filename="init_price_db.sql"):
    script_path = f"{SCHEMA_DIR}/{schema_filename}"
    with open(script_path, "r") as file:
        sql_commands = file.read()

    cur = conn.cursor()
    for stmt in sqlparse.split(sql_commands):
        stmt = stmt.strip()
        if stmt:
            cur.execute(stmt)
    conn.commit()
    cur.close()
    log.info("Executed schema successfully")

def load_parquet_data(parquet_path: str):
    df = pd.read_parquet(parquet_path)
    df["Timestamp"] = pd.to_datetime(df["Timestamp"], unit="s")
    df.rename(columns={
        "Timestamp": "time",
        "Open": "open",
        "High": "high",
        "Low": "low",
        "Close": "close",
        "Volume": "volume"
    }, inplace=True)
    return df.sort_values("time")

def bulk_insert_data(conn, df: pd.DataFrame, table_name: str):
    output = StringIO()
    df.to_csv(output, sep="\t", header=False, index=False)
    output.seek(0)

    cur = conn.cursor()
    cur.copy_from(output, table_name, sep="\t", null="\\N")
    conn.commit()
    cur.close()
    log.info(f"Loaded {len(df):,} rows into {table_name}")


# ----------------------------------------------------------------------
# MAIN ENTRY POINT
# ----------------------------------------------------------------------
def load_price_to_timescaledb(**kwargs):
    """Load processed dataset into TimescaleDB."""
    parquet_path = kwargs.get("parquet_path", PARQUET_PATH)
    conn = connect_to_db()
    execute_schema_script(conn)
    df = load_parquet_data(parquet_path)
    log.info("Inserting historical price data...")
    bulk_insert_data(conn, df, "historical_price")
    conn.close()
    return f"Loaded {len(df):,} records"