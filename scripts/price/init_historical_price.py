import os
import shutil
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

def download_kaggle_dataset(dataset_slug: str) -> str:
    log.info(f"⬇️ Downloading dataset: {dataset_slug}")
    path = kagglehub.dataset_download(dataset_slug)
    log.info(f"📦 Download complete: {path}")
    return path

def find_parquet_file(download_path: str) -> str:
    """Find the first .parquet file in the downloaded dataset."""
    parquet_files = [f for f in os.listdir(download_path) if f.lower().endswith(".parquet")]
    if not parquet_files:
        raise FileNotFoundError("No .parquet file found in the downloaded dataset.")
    return os.path.join(download_path, parquet_files[0])


# ----------------------------------------------------------------------
# MAIN ENTRY POINT
# ----------------------------------------------------------------------
def init_historical_price(**kwargs):
    """Download Bitcoin dataset (assumed to be in Parquet format)."""
    ensure_directory(DATA_DIR)

    if os.path.exists(PARQUET_PATH):
        log.info("Parquet file already exists. Skipping download.")
        return PARQUET_PATH

    download_path = download_kaggle_dataset(DATASET_SLUG)
    downloaded_parquet = find_parquet_file(download_path)

    # Copy to your standardized path
    shutil.copy(downloaded_parquet, PARQUET_PATH)
    log.info(f"✅ Parquet file saved to: {PARQUET_PATH}")

    return PARQUET_PATH


if __name__ == "__main__":
    result = init_historical_price()
    print(f"Historical data saved to: {result}")
