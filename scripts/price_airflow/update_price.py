import os
import time
import requests
from datetime import datetime, timedelta, timezone
import psycopg2
from psycopg2.extras import execute_values
from utils.logger import get_logger
from configs.config import DB_CONFIG

# ----------------------------------------------------------------------
# LOGGING CONFIGURATION 
# ----------------------------------------------------------------------
log = get_logger("update_price")


# ----------------------------------------------------------------------
# BINANCE API CONFIGS 
# ----------------------------------------------------------------------
BINANCE_KLINES_URL = "https://api.binance.com/api/v3/klines"
INTERVAL = "1m"
LIMIT = 1000
UTC = timezone.utc


# ----------------------------------------------------------------------
# HELPER FUNCTIONS
# ----------------------------------------------------------------------
def get_db_connection():
    """Create a new DB connection — safe for Airflow (no global state)."""
    return psycopg2.connect(
        host=DB_CONFIG["host"],
        port=DB_CONFIG["port"],
        user=DB_CONFIG["user"],
        password=DB_CONFIG["password"],
        dbname=DB_CONFIG["dbname"],
    )


def fetch_binance_klines(symbol: str, start_time_ms: int, end_time_ms: int):
    params = {
        "symbol": symbol.upper(),
        "interval": INTERVAL,
        "startTime": int(start_time_ms),
        "endTime": int(end_time_ms),
        "limit": LIMIT,
    }

    try:
        response = requests.get(BINANCE_KLINES_URL, params=params, timeout=30)
        response.raise_for_status()
        data = response.json()
        return data if isinstance(data, list) else []
    except Exception as e:
        log.error(f"Error fetching Binance klines for {symbol}: {e}")
        return []


def get_db_time_range():
    """Get min and max 'time' from database."""
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT MIN(time), MAX(time) FROM historical_price;")
            min_time, max_time = cur.fetchone()
            return min_time, max_time


def find_missing_ranges_in_db():
    min_time, max_time = get_db_time_range()
    now = datetime.now(UTC) - timedelta(minutes=1)
    now_ts_ms = int(now.timestamp() * 1000)

    if max_time is None:
        log.warning("No data in database. Please run initial backfill first.")
        return [], None, now_ts_ms

    max_ts_ms = int(max_time.timestamp() * 1000)
    tail_start_ms = max_ts_ms + 60_000

    # Tail gap
    tail_start_ms_to_use = tail_start_ms if tail_start_ms < now_ts_ms else None

    # Internal gaps in last 1 days
    recent_start = now - timedelta(days=1)
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT EXTRACT(EPOCH FROM time) * 1000 FROM historical_price WHERE time >= %s ORDER BY time;",
                (recent_start,)
            )
            rows = cur.fetchall()

    internal_gaps = []
    if rows:
        ts_list = [int(row[0]) for row in rows]
        if ts_list:
            expected = set(range(ts_list[0], now_ts_ms + 1, 60_000))
            actual = set(ts_list)
            missing = sorted(expected - actual)

            if missing:
                start = missing[0]
                prev = start
                for ts in missing[1:]:
                    if ts != prev + 60_000:
                        internal_gaps.append((start, prev))
                        start = ts
                    prev = ts
                internal_gaps.append((start, prev))

    return internal_gaps, tail_start_ms_to_use, now_ts_ms


def fetch_and_insert_klines(symbol: str, start_ms: int, end_ms: int) -> int:
    all_rows = []  # Will hold tuples: (time, open, high, low, close, volume)
    current_start = start_ms

    while current_start < end_ms:
        chunk_end = min(current_start + (LIMIT * 60_000), end_ms)
        klines = fetch_binance_klines(symbol, current_start, chunk_end)

        if not klines:
            log.warning(f"No data for {symbol} in [{current_start}, {chunk_end}]")
            current_start = chunk_end
            time.sleep(0.2)
            continue

        for k in klines:
            # k[0] = open_time (ms)
            row = (
                datetime.fromtimestamp(k[0] / 1000, tz=UTC),
                float(k[1]),  # open
                float(k[2]),  # high
                float(k[3]),  # low
                float(k[4]),  # close
                float(k[5]),  # volume
            )
            all_rows.append(row)

        last_open_time = klines[-1][0]
        current_start = last_open_time + 60_000
        time.sleep(0.2)

    if not all_rows:
        return 0

    # Remove duplicates by time (keep first)
    seen = set()
    unique_rows = []
    for row in all_rows:
        if row[0] not in seen:
            seen.add(row[0])
            unique_rows.append(row)

    # Sort by time
    unique_rows.sort(key=lambda x: x[0])

    # Bulk insert with ON CONFLICT DO UPDATE (to ensure correctness)
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            execute_values(
                cur,
                """
                INSERT INTO historical_price (time, open, high, low, close, volume)
                VALUES %s
                ON CONFLICT (time) DO UPDATE
                SET open = EXCLUDED.open,
                    high = EXCLUDED.high,
                    low = EXCLUDED.low,
                    close = EXCLUDED.close,
                    volume = EXCLUDED.volume;
                """,
                unique_rows,
                page_size=1000,
            )
            inserted = cur.rowcount


    log.info(f"Inserted {inserted} new rows for {symbol}.")
    return inserted

# ----------------------------------------------------------------------
# MAIN ENTRY POINT
# ----------------------------------------------------------------------
def update_price(symbol: str = "BTCUSDT", **kwargs) -> int:
    """
    Airflow-compatible function to update Binance 1m price data in TimescaleDB.
    Returns number of rows inserted.
    """
    log.info("=== Binance Historical Price Updater Started ===")
    log.info(f"Symbol: {symbol}")

    try:
        internal_gaps, tail_start_ms, now_ts_ms = find_missing_ranges_in_db()
        total_inserted = 0

        # Fill internal gaps
        for i, (gap_start, gap_end) in enumerate(internal_gaps):
            log.info(f"Filling internal gap {i+1}/{len(internal_gaps)}: {gap_start} → {gap_end}")
            # Note: gap_end is inclusive last missing timestamp
            total_inserted += fetch_and_insert_klines(symbol, gap_start, gap_end + 60_000)

        # Fill tail
        if tail_start_ms is not None:
            log.info(f"Filling tail gap: {tail_start_ms} → {now_ts_ms}")
            total_inserted += fetch_and_insert_klines(symbol, tail_start_ms, now_ts_ms)
        else:
            log.info("No tail update needed.")

        log.info(f"✅ Update completed. Total rows inserted: {total_inserted}")
        return total_inserted

    except Exception as e:
        log.exception(f"Updater failed: {e}")
        raise
    finally:
        log.info("=== Binance Historical Price Updater Finished ===")