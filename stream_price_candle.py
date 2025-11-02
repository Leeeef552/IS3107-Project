import websocket
import json
from datetime import datetime

# WebSocket URL for BTC/USDT 1-second klines
socket_url = "wss://stream.binance.com:9443/ws/btcusdt@kline_1s"

def on_open(ws):
    print("### Connection Opened ###")
    print("Streaming 1s klines for BTC/USDT...")
    print("-----------------------------------")

def on_message(ws, message):
    data = json.loads(message)
    
    # Extract kline info
    kline = data['k']
    symbol = kline['s']
    start_time = datetime.fromtimestamp(kline['t'] / 1000).strftime('%Y-%m-%d %H:%M:%S')
    end_time = datetime.fromtimestamp(kline['T'] / 1000).strftime('%Y-%m-%d %H:%M:%S')
    open_price = float(kline['o'])
    high_price = float(kline['h'])
    low_price = float(kline['l'])
    close_price = float(kline['c'])
    volume = float(kline['v'])
    is_closed = kline['x']  # True if candle is final

    status = "FINAL" if is_closed else "OPEN "
    print(f"[{start_time} → {end_time}] {status} | {symbol} | "
          f"O: {open_price:<10.2f} H: {high_price:<10.2f} "
          f"L: {low_price:<10.2f} C: {close_price:<10.2f} | Vol: {volume:.6f}")

def on_error(ws, error):
    print(f"### Error: {error} ###")

def on_close(ws, close_status_code, close_msg):
    print("### Connection Closed ###")

if __name__ == "__main__":
    ws = websocket.WebSocketApp(
        socket_url,
        on_open=on_open,
        on_message=on_message,
        on_error=on_error,
        on_close=on_close
    )
    ws.run_forever()