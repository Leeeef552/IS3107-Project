import websocket
import json
from datetime import datetime
import asyncio, json


# Define the WebSocket URL for the BTC/USDT trade stream
socket_url = "wss://stream.binance.com:9443/ws/btcusdt@trade"

def on_open(ws):
    """
    This function is called when the WebSocket connection is established.
    """
    print("### Connection Opened ###")
    print("Streaming live trades for BTC/USDT...")
    print("-----------------------------------")

def on_message(ws, message):
    """
    This function is called for each message received from the WebSocket.
    It processes and prints the trade data.
    """
    # Load the received JSON message into a Python dictionary
    trade_data = json.loads(message)

    # Extract relevant information from the trade data
    symbol = trade_data.get('s')
    price = float(trade_data.get('p', 0))
    quantity = float(trade_data.get('q', 0))
    trade_time = datetime.fromtimestamp(trade_data.get('T', 0) / 1000).strftime('%Y-%m-%d %H:%M:%S')
    is_buyer_maker = trade_data.get('m')

    # Determine the trade side
    side = "SELL" if is_buyer_maker else "BUY"

    # Print the formatted trade information
    print(f"[{trade_time}] {side:<4} | {symbol} | Price: {price:<12.2f} | Quantity: {quantity:.6f}")


def on_error(ws, error):
    """
    This function is called when an error occurs.
    """
    print(f"### Error: {error} ###")

def on_close(ws, close_status_code, close_msg):
    """
    This function is called when the WebSocket connection is closed.
    """
    print("### Connection Closed ###")


if __name__ == "__main__":
    # Create a WebSocketApp instance with the defined callback functions
    ws = websocket.WebSocketApp(socket_url,
                              on_open=on_open,
                              on_message=on_message,
                              on_error=on_error,
                              on_close=on_close)

    # Start the WebSocket connection and run indefinitely
    ws.run_forever()