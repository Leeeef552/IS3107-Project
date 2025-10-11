import os
import sys
import time
import logging
import pandas as pd
import requests
from datetime import datetime, timedelta, timezone
# ----------------------------------------------------------------------
# ✅ LOGGING CONFIGURATION (Singapore Time)
# ----------------------------------------------------------------------
from utils.logger import get_logger

SGT = timezone(timedelta(hours=8))  # UTC+8

log = get_logger("init_historical_price_data.py")


# ----------------------------------------------------------------------
# ✅ CORE FUNCTIONS
# ----------------------------------------------------------------------
def fetch_bitstamp_data(currency_pair, start_timestamp, end_timestamp, step=60, limit=1000):
    # uses the api to get data points based on start and end based on fixed 1 min interval, max step of 1000
    url = f"https://www.bitstamp.net/api/v2/ohlc/{currency_pair}/"
    params = {"step": step, "start": int(start_timestamp), "end": int(end_timestamp), "limit": limit}
    try:
        response = requests.get(url, params=params, timeout=60)
        response.raise_for_status()
        return response.json().get("data", {}).get("ohlc", [])
    except requests.exceptions.RequestException as e:
        log.error(f"Error fetching data: {e}")
        return []


def check_missing_data(parquet_filename):
    # updates based on current time of run and the max timestamp, but no gap finding before max
    if not os.path.exists(parquet_filename):
        log.warning(f"File not found: {parquet_filename}")
        return None, None

    df = pd.read_parquet(parquet_filename)
    df["Timestamp"] = pd.to_numeric(df["Timestamp"], errors="coerce")

    last_timestamp = df["Timestamp"].max()

    # ✅ Only buffer by 2 minutes now
    current_time = datetime.now(SGT) - timedelta(minutes=2)
    current_timestamp = int(current_time.timestamp())

    last_datetime = datetime.fromtimestamp(last_timestamp, tz=SGT)
    log.info(f"Last data point: {last_datetime.strftime('%Y-%m-%d %H:%M:%S')}")
    log.info(f"Current time (buffered): {current_time.strftime('%Y-%m-%d %H:%M:%S')}")

    if current_timestamp > last_timestamp:
        gap = current_timestamp - last_timestamp
        log.info(f"Gap detected: {gap:,} seconds")
        return last_timestamp, current_timestamp
    else:
        log.info("Dataset is up to date.")
        return None, None
    

def find_internal_gaps(df, step=60):
    # Identify internal gaps in the OHLC dataset.
    df = df.sort_values("Timestamp").reset_index(drop=True)
    df["diff"] = df["Timestamp"].diff()
    
    gaps = df[df["diff"] > step]
    gap_list = []
    for _, row in gaps.iterrows():
        gap_start = int(row["Timestamp"] - row["diff"])
        gap_end = int(row["Timestamp"])
        gap_list.append((gap_start, gap_end))
    
    return gap_list


def fetch_and_append_missing_data(currency_pair, last_timestamp, current_timestamp, parquet_filename):
    # entry method to fetch and add new data to curent parquet file 
    df_existing = pd.read_parquet(parquet_filename) if os.path.exists(parquet_filename) else pd.DataFrame()

    if df_existing.empty:
        log.warning("Existing dataset is empty — creating a new one.")

    start_sgt = datetime.fromtimestamp(last_timestamp, tz=SGT)
    end_sgt = datetime.fromtimestamp(current_timestamp, tz=SGT)
    log.info(f"Fetching from {start_sgt.strftime('%Y-%m-%d %H:%M:%S')} "
             f"to {end_sgt.strftime('%Y-%m-%d %H:%M:%S')}")

    chunk_size = 1000 * 60  # 1000 minutes
    time_chunks = []
    current_start = last_timestamp

    while current_start < current_timestamp:
        current_end = min(current_start + chunk_size, current_timestamp)
        time_chunks.append((current_start, current_end))
        current_start = current_end

    all_new_data = []

    for i, (chunk_start, chunk_end) in enumerate(time_chunks):
        chunk_start_sgt = datetime.fromtimestamp(chunk_start, tz=SGT)
        chunk_end_sgt = datetime.fromtimestamp(chunk_end, tz=SGT)
        log.info(f"Chunk {i+1}/{len(time_chunks)}: "
                f"{chunk_start_sgt.strftime('%Y-%m-%d %H:%M:%S')} → "
                f"{chunk_end_sgt.strftime('%Y-%m-%d %H:%M:%S')}")

        chunk_data = fetch_bitstamp_data(currency_pair, chunk_start, chunk_end)
        if not chunk_data:
            log.warning("  - No data returned for this chunk")
            time.sleep(1)
            continue

        df_chunk = pd.DataFrame(chunk_data)
        df_chunk["timestamp"] = pd.to_numeric(df_chunk["timestamp"], errors="coerce")
        df_chunk.columns = ["Timestamp", "Open", "High", "Low", "Close", "Volume"]

        # Filter out anything already in the dataset (avoid duplicates)
        before_filter = len(df_chunk)
        df_chunk = df_chunk[df_chunk["Timestamp"] > last_timestamp]
        after_filter = len(df_chunk)

        log.info(f"  - Retrieved {before_filter:,} rows from API, "
                f"{after_filter:,} new rows after filtering")

        if after_filter > 0:
            all_new_data.append(df_chunk)

        time.sleep(1)


    if not all_new_data:
        log.info("No new data found; file remains unchanged.")
        return

    df_new = pd.concat(all_new_data, ignore_index=True)
    df_new["Timestamp"] = pd.to_numeric(df_new["Timestamp"], errors="coerce")
    unique_new_rows = len(df_new)

    log.info(f"Total new unique data points to append: {unique_new_rows:,}")

    # ✅ Filter out any timestamps <= last_timestamp to avoid duplicates
    df_new["Timestamp"] = pd.to_numeric(df_new["Timestamp"], errors="coerce")
    df_new = df_new[df_new["Timestamp"] > last_timestamp]

    if df_new.empty:
        log.info("All fetched data already exists in dataset; nothing new to append.")
        return

    # Combine and clean
    df_combined = pd.concat([df_existing, df_new], ignore_index=True) if not df_existing.empty else df_new
    numeric_cols = ["Timestamp", "Open", "High", "Low", "Close", "Volume"]
    df_combined[numeric_cols] = df_combined[numeric_cols].apply(pd.to_numeric, errors="coerce")

    df_combined = (
        df_combined.dropna(subset=["Timestamp"])
        .drop_duplicates(subset="Timestamp")
        .sort_values("Timestamp")
        .reset_index(drop=True)
    )

    os.makedirs(os.path.dirname(parquet_filename), exist_ok=True)
    df_combined.to_parquet(parquet_filename, index=False, compression="snappy")

    min_time = datetime.fromtimestamp(df_combined["Timestamp"].min(), tz=SGT)
    max_time = datetime.fromtimestamp(df_combined["Timestamp"].max(), tz=SGT)

    log.info(f"✅ Updated dataset saved to {parquet_filename}")
    log.info(f"Summary: {len(df_new):,} new rows added. Total rows: {len(df_combined):,}")
    log.info(f"Time range: {min_time.strftime('%Y-%m-%d %H:%M:%S')} → "
             f"{max_time.strftime('%Y-%m-%d %H:%M:%S')}")


# ----------------------------------------------------------------------
# ✅ MAIN ENTRY POINT
# ----------------------------------------------------------------------
def main():
    parquet_filename = "historical_data/btcusd_1-min_data.parquet"
    currency_pair = "btcusd"

    log.info("=== Crypto Data Updater Started ===")

    if not os.path.exists(parquet_filename):
        log.error("Parquet file not found; run initial data download first.")
        return

    df = pd.read_parquet(parquet_filename)
    df["Timestamp"] = pd.to_numeric(df["Timestamp"], errors="coerce")

    # --- Detect internal gaps ---
    gap_list = find_internal_gaps(df)
    if gap_list:
        log.warning(f"Detected {len(gap_list)} internal gaps.")
        for i, (start, end) in enumerate(gap_list[:5]):
            start_dt = datetime.fromtimestamp(start, tz=SGT)
            end_dt = datetime.fromtimestamp(end, tz=SGT)
            log.warning(f"  Gap {i+1}: {start_dt} → {end_dt}")
    else:
        log.info("No internal gaps detected.")

    # --- Handle the most recent missing window ---
    last_timestamp, current_timestamp = check_missing_data(parquet_filename)

    # --- Fill gaps by re-fetching missing chunks ---
    for i, (start, end) in enumerate(gap_list):
        log.info(f"Filling internal gap {i+1}/{len(gap_list)}")
        fetch_and_append_missing_data(currency_pair, start, end, parquet_filename)

    # --- Then fetch the tail end if needed ---
    if last_timestamp and current_timestamp:
        fetch_and_append_missing_data(currency_pair, last_timestamp, current_timestamp, parquet_filename)
    else:
        log.info("No updates required at dataset tail.")

    log.info("=== Crypto Data Updater Finished ===")


if __name__ == "__main__":
    sys.exit(main())
