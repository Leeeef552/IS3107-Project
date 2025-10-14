import os
from dotenv import load_dotenv

load_dotenv()

# Base directories
DATA_DIR = os.getenv("DATA_DIR", "historical_data")
SCHEMA_DIR = os.getenv("SCHEMA_DIR", "schema")
AGGREGATES_DIR = os.path.join(SCHEMA_DIR, "aggregates")

# Dataset
DATASET_SLUG = "leeeefun/bitcoin-2012-11-oct-2025-1min"
PARQUET_PATH = os.path.join(DATA_DIR, "btcusd_1-min_data.parquet")

# Database
DB_CONFIG = {
    "host": os.getenv("TIMESCALE_HOST", "localhost"),
    "port": int(os.getenv("TIMESCALE_PORT", 5432)),
    "user": os.getenv("TIMESCALE_USER"),
    "password": os.getenv("TIMESCALE_PASSWORD"),
    "dbname": os.getenv("TIMESCALE_DBNAME", "postgres"),
}
