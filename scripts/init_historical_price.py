import os
import sys
import pandas as pd
import kagglehub
from utils.logger import get_logger
from configs.config import DATA_DIR, DATASET_SLUG, PARQUET_PATH

# ----------------------------------------------------------------------
# LOGGING CONFIGURATION (Singapore Time)
# ----------------------------------------------------------------------
from utils.logger import get_logger

log = get_logger("init_historical_price.py")

# ----------------------------------------------------------------------
#  HELPER FUNCTIONS
# ----------------------------------------------------------------------
def ensure_directory(path: str):
    os.makedirs(path, exist_ok=True)
    # log.info(f"Ensured directory: {os.path.abspath(path)}")

def download_kaggle_dataset(dataset_slug: str) -> str:
    log.info(f"⬇️ Downloading dataset: {dataset_slug}")
    path = kagglehub.dataset_download(dataset_slug)
    log.info(f"📦 Download complete: {path}")
    return path

def find_csv_file(download_path: str) -> str:
    csv_files = [f for f in os.listdir(download_path) if f.lower().endswith(".csv")]
    if not csv_files:
        raise FileNotFoundError("No CSV found in dataset.")
    return os.path.join(download_path, csv_files[0])

def convert_to_parquet(csv_path: str, parquet_path: str):
    df = pd.read_csv(csv_path)
    log.info(f"Loaded CSV ({len(df):,} rows × {len(df.columns)} cols)")
    df.to_parquet(parquet_path, index=False, compression="snappy")
    log.info(f"Saved as Parquet: {parquet_path}")


# ----------------------------------------------------------------------
# MAIN ENTRY POINT
# ----------------------------------------------------------------------
def init_historical_price(**kwargs):
    """Download and convert Bitcoin dataset."""
    ensure_directory(DATA_DIR)
    if os.path.exists(PARQUET_PATH):
        log.info("Parquet file already exists. Skipping download.")
        return PARQUET_PATH

    download_path = download_kaggle_dataset(DATASET_SLUG)
    csv_path = find_csv_file(download_path)
    convert_to_parquet(csv_path, PARQUET_PATH)
    return PARQUET_PATH
