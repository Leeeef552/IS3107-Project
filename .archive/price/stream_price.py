import json
from datetime import datetime, timezone
from websocket import WebSocketApp
# Assuming you have a logger utility, otherwise use the standard logging module
import logging

# ----------------------------------------------------------------------
# LOGGING CONFIGURATION
# ----------------------------------------------------------------------
# Using the standard logging module for simplicity
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
log = logging.getLogger("ws_trade_listener")

# ----------------------------------------------------------------------
# BINANCE CONFIG
# ----------------------------------------------------------------------
SYMBOL = "btcusdt"
STREAM = f"{SYMBOL}@trade"
WS_URL = f"wss://stream.binance.com:9443/ws/{STREAM}"
UTC = timezone.utc

# ----------------------------------------------------------------------
# HANDLERS
# ----------------------------------------------------------------------
def on_message(ws, message):
    """Handle incoming trade data and log the latest transaction."""
    try:
        data = json.loads(message)

        # Extract the core details of the trade
        trade_time = datetime.fromtimestamp(data["T"] / 1000, tz=UTC)
        price = float(data["p"])
        quantity = float(data["q"])
        symbol = data["s"]

        # --- MODIFICATION ---
        # The logic for determining BUY/SELL side has been removed.
        # We now log the transaction details directly.
        log.info(
            f"[{trade_time}] {symbol} "
            f"Price:{price:<10.2f} Quantity:{quantity:.6f}"
        )

    except Exception as e:
        log.exception(f"Error processing message: {e}")


def on_error(ws, error):
    log.error(f"WebSocket error: {error}")


def on_close(ws, close_status_code, close_msg):
    log.warning(f"WebSocket closed ({close_status_code}): {close_msg}")
    import time
    log.info("Reconnecting in 5 seconds...")
    time.sleep(5)
    start_websocket()  # auto-reconnect


# ----------------------------------------------------------------------
# START FUNCTION
# ----------------------------------------------------------------------
def start_websocket():
    log.info(f"Connecting to Binance WebSocket: {WS_URL}")
    ws = WebSocketApp(
        WS_URL,
        on_message=on_message,
        on_error=on_error,
        on_close=on_close,
    )
    ws.run_forever(ping_interval=20, ping_timeout=10)


# ----------------------------------------------------------------------
# ENTRY POINT
# ----------------------------------------------------------------------
if __name__ == "__main__":
    log.info("=== Starting Binance Trade Listener ===")
    start_websocket()