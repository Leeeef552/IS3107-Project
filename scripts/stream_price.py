import os
import sys
import json
import time
import threading
import websocket
from datetime import datetime, timezone, timedelta

# ----------------------------------------------------------------------
# ✅ LOGGING CONFIGURATION (Singapore Time)
# ----------------------------------------------------------------------
from utils.logger import get_logger
log = get_logger("stream_kline_binance.py")


# ----------------------------------------------------------------------
# ✅ CORE FUNCTIONS
# ----------------------------------------------------------------------
def format_sgt_time(ts: int) -> str:
    """Convert UNIX timestamp (ms) to Singapore Time (HH:MM:SS)."""
    sgt = timezone(timedelta(hours=8))
    return datetime.fromtimestamp(ts / 1000, tz=timezone.utc).astimezone(sgt).strftime("%H:%M:%S")


def on_open(ws):
    """Called when WebSocket connection is opened."""
    log.info("✅ Connected to Binance BTC/USDT WebSocket (1m Kline Stream)")


def on_message(ws, message):
    """Handle incoming kline WebSocket messages."""
    try:
        data = json.loads(message)
        kline = data["k"]
        symbol = kline["s"]
        interval = kline["i"]
        start_time = format_sgt_time(kline["t"])
        end_time = format_sgt_time(kline["T"])
        open_price = float(kline["o"])
        high = float(kline["h"])
        low = float(kline["l"])
        close = float(kline["c"])
        volume = float(kline["v"])
        is_final = kline["x"]  # True if candle is closed

        status = "✅ FINAL" if is_final else "⏳ FORMING"
        log.info(
            f"{status} | {symbol} {interval} | "
            f"{start_time}–{end_time} | "
            f"O: ${open_price:,.2f} H: ${high:,.2f} L: ${low:,.2f} C: ${close:,.2f} | Vol: {volume:,.3f}"
        )
    except Exception as e:
        log.error(f"Error parsing kline message: {e}")


def on_error(ws, error):
    """Handle WebSocket errors."""
    log.error(f"⚠️ WebSocket error: {error}")


def on_close(ws, code, msg):
    """Handle WebSocket closure."""
    log.warning(f"❌ Disconnected from Binance (code={code}, msg={msg})")


def run_ws(symbol: str = "btcusdt"):
    """Run Binance 1m kline WebSocket connection."""
    # 🔥 Changed from @trade to @kline_1m
    socket = f"wss://stream.binance.com:9443/ws/{symbol}@kline_1m"
    ws = websocket.WebSocketApp(
        socket,
        on_open=on_open,
        on_message=on_message,
        on_error=on_error,
        on_close=on_close
    )
    ws.run_forever(ping_interval=20, ping_timeout=10)


# ----------------------------------------------------------------------
# ✅ MAIN ENTRY POINT
# ----------------------------------------------------------------------
def main():
    SYMBOL = "btcusdt"
    log.info(f"=== Binance Live {SYMBOL.upper()} 1m Kline Stream Started ===")
    log.info("Source: wss://stream.binance.com:9443/ws")

    try:
        t = threading.Thread(target=run_ws, args=(SYMBOL,))
        t.daemon = True
        t.start()

        # Keep main thread alive
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        log.info("🛑 Termination requested by user. Stopping...")
        sys.exit(0)
    except Exception as e:
        log.error(f"Unexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    sys.exit(main())