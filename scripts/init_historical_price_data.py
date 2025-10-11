import os
import sys
import pandas as pd
import kagglehub
from datetime import datetime, timedelta, timezone
# ----------------------------------------------------------------------
# ✅ LOGGING CONFIGURATION (Singapore Time)
# ----------------------------------------------------------------------
from utils.logger import get_logger

log = get_logger("init_historical_price_data.py")


# ----------------------------------------------------------------------
# ✅ CORE FUNCTIONS
# ----------------------------------------------------------------------
def ensure_directory(path: str):
    """Create directory if missing."""
    os.makedirs(path, exist_ok=True)
    log.info(f"Directory ensured: {os.path.abspath(path)}")


def download_kaggle_dataset(dataset_slug: str) -> str:
    """Download dataset using KaggleHub and return its local path."""
    log.info(f"⬇️ Downloading dataset: {dataset_slug}")
    try:
        path = kagglehub.dataset_download(dataset_slug)
        log.info(f"📦 Download complete. Local path: {path}")
        return path
    except Exception as e:
        log.error(f"Failed to download dataset: {e}")
        sys.exit(1)


def find_csv_file(download_path: str) -> str:
    """Locate the first CSV file in the dataset directory."""
    csv_files = [f for f in os.listdir(download_path) if f.lower().endswith(".csv")]
    if not csv_files:
        log.error("❌ No CSV file found in the downloaded dataset.")
        sys.exit(1)
    csv_path = os.path.join(download_path, csv_files[0])
    log.info(f"📄 Found CSV file: {csv_files[0]}")
    return csv_path


def convert_to_parquet(csv_path: str, parquet_path: str):
    """Load CSV and convert to Parquet format."""
    try:
        df = pd.read_csv(csv_path)
        log.info(f"✅ Loaded CSV: {len(df):,} rows × {len(df.columns)} columns")
    except Exception as e:
        log.error(f"Error reading CSV: {e}")
        sys.exit(1)

    try:
        df.to_parquet(parquet_path, index=False, compression="snappy")
        log.info(f"💾 Saved dataset as Parquet: {parquet_path}")
    except Exception as e:
        log.error(f"Error saving Parquet file: {e}")
        sys.exit(1)


# ----------------------------------------------------------------------
# ✅ MAIN ENTRY POINT
# ----------------------------------------------------------------------
def main():
    DATA_DIR = "historical_data"
    DATASET_SLUG = "leeeefun/bitcoin-2012-11-oct-2025-1min"
    PARQUET_PATH = os.path.join(DATA_DIR, "btcusd_1-min_data.parquet")

    log.info("=== Kaggle Bitcoin Dataset Downloader Started ===")
    log.info("Source: https://www.kaggle.com/datasets/leeeefun/bitcoin-2012-11-oct-2025-1min/settings")

    ensure_directory(DATA_DIR)

    # Skip if already exists
    if os.path.exists(PARQUET_PATH):
        log.info(f"Parquet file already exists: {PARQUET_PATH}")
        log.info("No download needed.")
        return

    download_path = download_kaggle_dataset(DATASET_SLUG)
    csv_path = find_csv_file(download_path)
    convert_to_parquet(csv_path, PARQUET_PATH)

    log.info("=== Kaggle Bitcoin Dataset Downloader Finished ===")


if __name__ == "__main__":
    sys.exit(main())
