import os
import time
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import requests
from datetime import datetime, timedelta, timezone
from utils.logger import get_logger
from configs.config import PARQUET_PATH

# ----------------------------------------------------------------------
# LOGGING CONFIGURATION
# ----------------------------------------------------------------------
from utils.logger import get_logger

SGT = timezone(timedelta(hours=8))
log = get_logger("backfill_price")


# ----------------------------------------------------------------------
# HELPER FUNCTIONS
# ----------------------------------------------------------------------
def fetch_bitstamp_data(currency_pair, start_timestamp, end_timestamp, step=60, limit=1000):
    """Fetch OHLC data from Bitstamp API for a given time range."""
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
    """Compare the last timestamp in the dataset to current time (SGT) and detect tail gaps."""
    if not os.path.exists(parquet_filename):
        log.warning(f"File not found: {parquet_filename}")
        return None, None

    # Memory-efficient: read only Timestamp column
    try:
        parquet_file = pq.ParquetFile(parquet_filename)
        last_timestamp = None
        for batch in parquet_file.iter_batches(columns=["Timestamp"]):
            timestamps = batch["Timestamp"].to_pylist()
            if timestamps:
                batch_max = max(timestamps)
                if last_timestamp is None or batch_max > last_timestamp:
                    last_timestamp = batch_max
    except Exception as e:
        log.warning(f"Error reading parquet file efficiently: {e}. Falling back to pandas.")
        df = pd.read_parquet(parquet_filename, columns=["Timestamp"])
        df["Timestamp"] = pd.to_numeric(df["Timestamp"], errors="coerce")
        last_timestamp = df["Timestamp"].max()

    if last_timestamp is None:
        log.warning("No timestamps found in file")
        return None, None

    current_time = datetime.now(SGT) - timedelta(minutes=1)
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


def find_internal_gaps(parquet_filename, step=60):
    """Identify internal gaps in the OHLC dataset (memory-efficient version)."""
    if not os.path.exists(parquet_filename):
        return []
    
    # Memory-efficient: read only Timestamp column in sorted order
    try:
        timestamps = []
        parquet_file = pq.ParquetFile(parquet_filename)
        for batch in parquet_file.iter_batches(columns=["Timestamp"]):
            timestamps.extend(batch["Timestamp"].to_pylist())
        
        if not timestamps:
            return []
        
        timestamps = sorted(set(timestamps))  # Sort and deduplicate
    except Exception as e:
        log.warning(f"Error reading parquet file efficiently: {e}. Falling back to pandas.")
        df = pd.read_parquet(parquet_filename, columns=["Timestamp"])
        timestamps = sorted(df["Timestamp"].dropna().unique().tolist())
    
    gap_list = []
    for i in range(1, len(timestamps)):
        diff = timestamps[i] - timestamps[i-1]
        if diff > step:
            gap_start = int(timestamps[i-1])
            gap_end = int(timestamps[i])
            gap_list.append((gap_start, gap_end))
    
    return gap_list


def fetch_and_append_missing_data(currency_pair, start_timestamp, end_timestamp, parquet_filename):
    """Fetch new OHLC data and append it to existing dataset using memory-efficient incremental writes."""
    start_sgt = datetime.fromtimestamp(start_timestamp, tz=SGT)
    end_sgt = datetime.fromtimestamp(end_timestamp, tz=SGT)
    log.info(f"Fetching from {start_sgt.strftime('%Y-%m-%d %H:%M:%S')} → {end_sgt.strftime('%Y-%m-%d %H:%M:%S')}")

    # Get existing timestamps to avoid duplicates (memory-efficient: only read Timestamp column)
    existing_timestamps = set()
    if os.path.exists(parquet_filename):
        try:
            # Read only the Timestamp column to check for duplicates
            parquet_file = pq.ParquetFile(parquet_filename)
            for batch in parquet_file.iter_batches(columns=["Timestamp"]):
                existing_timestamps.update(batch["Timestamp"].to_pylist())
            log.info(f"Loaded {len(existing_timestamps):,} existing timestamps for duplicate checking")
        except Exception as e:
            log.warning(f"Could not read existing timestamps: {e}. Will skip duplicate check.")

    chunk_size = 1000 * 60  # 1000 minutes per chunk
    time_chunks = []
    current_start = start_timestamp

    while current_start < end_timestamp:
        current_end = min(current_start + chunk_size, end_timestamp)
        time_chunks.append((current_start, current_end))
        current_start = current_end

    # Collect new data in chunks (limit memory usage)
    new_rows = []
    total_new = 0

    for i, (chunk_start, chunk_end) in enumerate(time_chunks):
        chunk_start_sgt = datetime.fromtimestamp(chunk_start, tz=SGT)
        chunk_end_sgt = datetime.fromtimestamp(chunk_end, tz=SGT)
        log.info(f"Chunk {i+1}/{len(time_chunks)}: {chunk_start_sgt} → {chunk_end_sgt}")

        chunk_data = fetch_bitstamp_data(currency_pair, chunk_start, chunk_end)
        if not chunk_data:
            log.warning("  - No data returned for this chunk.")
            time.sleep(1)
            continue

        # Process chunk data
        for row in chunk_data:
            ts = int(row.get("timestamp", 0))
            if ts > start_timestamp and ts not in existing_timestamps:
                new_rows.append({
                    "Timestamp": ts,
                    "Open": float(row.get("open", 0)),
                    "High": float(row.get("high", 0)),
                    "Low": float(row.get("low", 0)),
                    "Close": float(row.get("close", 0)),
                    "Volume": float(row.get("volume", 0))
                })
                existing_timestamps.add(ts)  # Track to avoid duplicates in same batch

        log.info(f"  - Retrieved {len(chunk_data):,} rows; {len(new_rows) - total_new:,} new after filtering.")
        total_new = len(new_rows)
        time.sleep(1)

    if not new_rows:
        log.info("No new data found; dataset unchanged.")
        return

    log.info(f"Adding {len(new_rows):,} new rows to existing dataset...")

    # Convert to DataFrame
    df_new = pd.DataFrame(new_rows)
    if df_new.empty:
        log.info("All fetched data already exists in dataset.")
        return

    # Ensure numeric types
    numeric_cols = ["Timestamp", "Open", "High", "Low", "Close", "Volume"]
    df_new[numeric_cols] = df_new[numeric_cols].apply(pd.to_numeric, errors="coerce")
    df_new = df_new.dropna(subset=["Timestamp"]).sort_values("Timestamp").reset_index(drop=True)

    if df_new.empty:
        log.info("No valid new data after cleaning.")
        return

    # Memory-efficient merge: use PyArrow for streaming merge
    os.makedirs(os.path.dirname(parquet_filename), exist_ok=True)
    
    if os.path.exists(parquet_filename):
        log.info("Merging with existing parquet file...")
        try:
            existing_parquet_file = pq.ParquetFile(parquet_filename)
            existing_schema = existing_parquet_file.schema_arrow

            # Align dtypes in the new dataframe to match existing schema
            for field in existing_schema:
                column_name = field.name
                if column_name not in df_new.columns:
                    continue

                if pa.types.is_floating(field.type):
                    df_new[column_name] = pd.to_numeric(df_new[column_name], errors="coerce").astype(float)
                elif pa.types.is_integer(field.type):
                    df_new[column_name] = pd.to_numeric(df_new[column_name], errors="coerce").astype("int64")
                else:
                    # Fallback to pandas numeric conversion
                    df_new[column_name] = pd.to_numeric(df_new[column_name], errors="coerce")

            # Convert dataframe to arrow table with matching schema
            try:
                new_table = pa.Table.from_pandas(df_new, schema=existing_schema, preserve_index=False)
            except Exception as cast_error:
                log.warning(f"Schema alignment via from_pandas failed: {cast_error}")
                new_table = pa.Table.from_pandas(df_new, preserve_index=False)
                arrays = []
                for idx, field in enumerate(existing_schema):
                    column_name = field.name
                    column_array = new_table[column_name]
                    if column_array.type != field.type:
                        column_array = column_array.cast(field.type)
                    arrays.append(column_array)
                new_table = pa.Table.from_arrays(arrays, schema=existing_schema)

            temp_new_file = parquet_filename + ".new"
            pq.write_table(new_table, temp_new_file, compression="snappy")

            existing_size = os.path.getsize(parquet_filename) / (1024 * 1024)  # MB
            log.info(f"Existing file size: {existing_size:.2f} MB")

            if existing_size > 500:
                log.info("Large file detected, using chunked merge approach...")
                parquet_file = pq.ParquetFile(parquet_filename)
                new_table = pq.read_table(temp_new_file)

                all_tables = [new_table]
                for i in range(parquet_file.num_row_groups):
                    row_group = parquet_file.read_row_group(i)
                    all_tables.append(row_group)

                combined_table = pa.concat_tables(all_tables)
                df_combined = combined_table.to_pandas()
            else:
                existing_table = pq.read_table(parquet_filename)
                new_table = pq.read_table(temp_new_file)
                combined_table = pa.concat_tables([existing_table, new_table])
                df_combined = combined_table.to_pandas()

            df_combined = df_combined.drop_duplicates(subset="Timestamp").sort_values("Timestamp").reset_index(drop=True)
            df_combined.to_parquet(parquet_filename, index=False, compression="snappy")
            os.remove(temp_new_file)

            log.info(f"✅ Updated dataset saved. Total rows: {len(df_combined):,}")
        except MemoryError as e:
            log.error(f"Memory error during merge: {e}. New data will be written to separate file.")
            # Last resort: append to a separate file (user can merge later)
            append_file = parquet_filename.replace(".parquet", "_append.parquet")
            if os.path.exists(append_file):
                # Append to existing append file
                existing_append = pd.read_parquet(append_file)
                df_combined_append = pd.concat([existing_append, df_new], ignore_index=True)
                df_combined_append = df_combined_append.drop_duplicates(subset="Timestamp").sort_values("Timestamp")
                df_combined_append.to_parquet(append_file, index=False, compression="snappy")
            else:
                df_new.to_parquet(append_file, index=False, compression="snappy")
            log.warning(f"New data written to {append_file}. Manual merge required.")
            raise
    else:
        # New file, just write the new data
        df_new.to_parquet(parquet_filename, index=False, compression="snappy")
        log.info(f"✅ Created new dataset with {len(df_new):,} rows")

    min_time = datetime.fromtimestamp(df_new["Timestamp"].min(), tz=SGT)
    max_time = datetime.fromtimestamp(df_new["Timestamp"].max(), tz=SGT)
    log.info(f"New data range: {min_time.strftime('%Y-%m-%d %H:%M:%S')} → {max_time.strftime('%Y-%m-%d %H:%M:%S')}")
    
    return parquet_filename


# ----------------------------------------------------------------------
# MAIN ENTRY POINT
# ----------------------------------------------------------------------
def backfill_price(currency_pair="btcusd", parquet_filename=PARQUET_PATH, **kwargs):
    """
    Detect missing or new data from Bitstamp API and update the Parquet dataset.

    Returns:
        str: Updated parquet file path.
    """
    try:
        log.info("=== Crypto Data Updater Started ===")

        if not os.path.exists(parquet_filename):
            raise FileNotFoundError(f"Parquet file not found: {parquet_filename}. Run initial downloader first.")

        log.info(f"Reading parquet file metadata: {parquet_filename}")
        # Get row count without loading full file
        parquet_file = pq.ParquetFile(parquet_filename)
        total_rows = parquet_file.metadata.num_rows
        log.info(f"Parquet file contains {total_rows:,} rows")

        # --- Detect internal gaps (memory-efficient) ---
        log.info("Detecting internal gaps...")
        gap_list = find_internal_gaps(parquet_filename)
        if gap_list:
            log.warning(f"Detected {len(gap_list)} internal gaps.")
            for i, (start, end) in enumerate(gap_list[:5]):
                start_dt = datetime.fromtimestamp(start, tz=SGT)
                end_dt = datetime.fromtimestamp(end, tz=SGT)
                log.warning(f"  Gap {i+1}: {start_dt} → {end_dt}")
        else:
            log.info("No internal gaps detected.")

        # --- Handle the most recent missing window ---
        log.info("Checking for tail gaps...")
        last_timestamp, current_timestamp = check_missing_data(parquet_filename)

        # --- Fill internal gaps ---
        if gap_list:
            log.info(f"Starting to fill {len(gap_list)} internal gaps...")
            for i, (start, end) in enumerate(gap_list):
                log.info(f"Filling internal gap {i+1}/{len(gap_list)}")
                try:
                    fetch_and_append_missing_data(currency_pair, start, end, parquet_filename)
                    log.info(f"Successfully filled gap {i+1}/{len(gap_list)}")
                except Exception as e:
                    log.error(f"Error filling gap {i+1}/{len(gap_list)}: {e}")
                    # Continue with next gap instead of failing completely
                    continue

        # --- Fill the tail gap ---
        if last_timestamp and current_timestamp:
            log.info("Filling tail gap...")
            try:
                fetch_and_append_missing_data(currency_pair, last_timestamp, current_timestamp, parquet_filename)
                log.info("Successfully filled tail gap")
            except Exception as e:
                log.error(f"Error filling tail gap: {e}")
                raise  # Re-raise for tail gap as it's critical
        else:
            log.info("No tail updates required.")

        log.info("=== Crypto Data Updater Finished ===")
        return parquet_filename
    except Exception as e:
        log.error(f"Fatal error in backfill_price: {e}", exc_info=True)
        raise  # Re-raise to let Airflow handle the failure


if __name__ == "__main__":
    result = backfill_price()
    print(f"Backfill complete: {result}")
