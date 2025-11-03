import asyncio
import json
import psycopg2
from psycopg2.extras import execute_values
import websockets
from datetime import datetime, timezone
from utils.logger import get_logger
from configs.config import DB_CONFIG

# ----------------------------------------------------------------------
# CONFIGURATION
# ----------------------------------------------------------------------
logger = get_logger("price_stream")
SYMBOL = "btcusdt"
INTERVAL = "1m"
BINANCE_WS_URL = f"wss://stream.binance.com:9443/ws/{SYMBOL}@kline_{INTERVAL}"

# ----------------------------------------------------------------------
# DATABASE CONNECTION
# ----------------------------------------------------------------------
def get_db_conn():
    """Establish and return a new PostgreSQL connection."""
    return psycopg2.connect(
        host="localhost", # adjusted since .env catered for docker 
        port=DB_CONFIG["port"],
        user=DB_CONFIG["user"],
        password=DB_CONFIG["password"],
        dbname=DB_CONFIG["dbname"],
    )

# ----------------------------------------------------------------------
# INSERT FUNCTION
# ----------------------------------------------------------------------
def insert_candle(conn, candle) -> int:
    """Insert a finalized 1m candle into historical_price."""
    record = (
        candle["time"],
        candle["open"],
        candle["high"],
        candle["low"],
        candle["close"],
        candle["volume"],
    )

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
            [record],
        )
        inserted = cur.rowcount
    conn.commit()
    return inserted

# ----------------------------------------------------------------------
# PARSE KLINE MESSAGE
# ----------------------------------------------------------------------
def parse_kline(msg):
    k = msg["k"]
    candle = {
        "symbol": msg["s"],
        "interval": k["i"],
        "time": datetime.fromtimestamp(k["t"] / 1000, tz=timezone.utc),
        "open": float(k["o"]),
        "high": float(k["h"]),
        "low": float(k["l"]),
        "close": float(k["c"]),
        "volume": float(k["v"]),
        "is_closed": k["x"],  # True when candle closes
    }
    return candle

# ----------------------------------------------------------------------
# MAIN WEBSOCKET LOOP
# ----------------------------------------------------------------------
async def listen():
    logger.info(f"Connecting to Binance WebSocket: {BINANCE_WS_URL}")
    conn = get_db_conn()

    async for ws in websockets.connect(BINANCE_WS_URL):
        try:
            async for msg in ws:
                data = json.loads(msg)
                candle = parse_kline(data)

                # Only insert when the 1m candle closes
                if candle["is_closed"]:
                    try:
                        inserted = insert_candle(conn, candle)
                        if inserted > 0:
                            logger.info(
                                f"✅ Inserted candle successfully: [{candle['time']}] "
                                f"{candle['symbol']} O:{candle['open']:.2f} "
                                f"H:{candle['high']:.2f} L:{candle['low']:.2f} "
                                f"C:{candle['close']:.2f} V:{candle['volume']:.2f}"
                            )
                        else:
                            logger.info(
                                f"ℹ️ Candle already existed: [{candle['time']}] {candle['symbol']}"
                            )

                    except Exception as db_err:
                        logger.error(f"DB insert error: {db_err}", exc_info=True)
                        # Try reconnecting DB if connection dropped
                        conn.close()
                        conn = get_db_conn()

        except websockets.ConnectionClosed:
            logger.warning("WebSocket connection closed. Reconnecting in 5s...")
            await asyncio.sleep(5)
            continue
        except Exception as e:
            logger.error(f"Unexpected error: {e}", exc_info=True)
            await asyncio.sleep(5)
            continue

# ----------------------------------------------------------------------
# ENTRY POINT
# ----------------------------------------------------------------------
if __name__ == "__main__":
    asyncio.run(listen())
