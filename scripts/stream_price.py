import json
import time
import threading
import websocket
import redis
from datetime import datetime, timezone, timedelta

from utils.logger import get_logger, SGT
from configs.config import REDIS_CONFIG

log = get_logger("stream_price")
BINANCE_SYMBOL = "btcusdt"
BINANCE_INTERVAL = "1m"

# ----------------------------------------------------------------------
# REDIS CONNECTION
# ----------------------------------------------------------------------
r = redis.Redis(
    host=REDIS_CONFIG["host"],
    port=REDIS_CONFIG["port"],
    decode_responses=True,
)
STREAM_KEY = REDIS_CONFIG["stream_key"]
MAXLEN = REDIS_CONFIG["maxlen"]

# ----------------------------------------------------------------------
# Time Conversion (convert binance time stamps)
# ----------------------------------------------------------------------
def format_sgt_time(ts: int) -> str:
    """Convert UNIX timestamp (ms) to Singapore Time (HH:MM:SS)."""
    return datetime.fromtimestamp(ts / 1000, tz=SGT).strftime("%H:%M:%S")

# ----------------------------------------------------------------------
# HELPER FUNCTIONS
# ----------------------------------------------------------------------
def on_open(ws):
    log.info(f"✅ Connected to Binance {BINANCE_SYMBOL.upper()} WebSocket (1m Kline Stream)")

def on_message(ws, message):
    try:
        data = json.loads(message)
        kline = data["k"]

        payload = {
            "symbol": kline["s"],
            "interval": kline["i"],
            "start_time": format_sgt_time(kline["t"]),
            "end_time": format_sgt_time(kline["T"]),
            "open": float(kline["o"]),
            "high": float(kline["h"]),
            "low": float(kline["l"]),
            "close": float(kline["c"]),
            "volume": float(kline["v"]),
            "is_final": int(kline["x"])
        }

        r.xadd(STREAM_KEY, payload, maxlen=MAXLEN)
        status = "✅ FINAL" if payload["is_final"] else "⏳ FORMING"
        log.info(f"{status} | {payload['symbol']} {payload['interval']} | "
                 f"{payload['start_time']}–{payload['end_time']} | "
                 f"O:{payload['open']:.2f} H:{payload['high']:.2f} L:{payload['low']:.2f} "
                 f"C:{payload['close']:.2f} | Vol:{payload['volume']:.3f}")
    except Exception as e:
        log.error(f"Error parsing/pushing message: {e}")

def on_error(ws, error):
    log.error(f"⚠️ WebSocket error: {error}")

def on_close(ws, code, msg):
    log.warning(f"❌ Disconnected from Binance (code={code}, msg={msg})")

# ----------------------------------------------------------------------
# MAIN ENTRY POINT
# ----------------------------------------------------------------------
def run_streamer(run_forever=True):
    """Start Binance WebSocket streamer — Airflow-safe."""
    log.info(f"=== Starting Binance {BINANCE_SYMBOL.upper()} Stream ===")

    socket = f"wss://stream.binance.com:9443/ws/{BINANCE_SYMBOL}@kline_1m"
    ws = websocket.WebSocketApp(
        socket,
        on_open=on_open,
        on_message=on_message,
        on_error=on_error,
        on_close=on_close,
    )

    t = threading.Thread(target=ws.run_forever, kwargs={"ping_interval": 20, "ping_timeout": 10})
    t.daemon = True
    t.start()

    try:
        if run_forever:
            while True:
                time.sleep(1)
        else:
            # For Airflow test mode, run briefly
            time.sleep(10)
            log.info("Streamer test complete.")
        return 0
    except KeyboardInterrupt:
        log.info("🛑 Stopping streamer...")
        return 0
    except Exception as e:
        log.error(f"Unexpected error: {e}")
        return 1

# ----------------------------------------------------------------------
# MAIN
# ----------------------------------------------------------------------
if __name__ == "__main__":
    run_streamer(run_forever=True)
