import websocket
import json
import asyncio, json



# Define the WebSocket URL for the BTC/USDT order book stream
socket_url = "wss://stream.binance.com:9443/ws/btcusdt@depth"

def on_open(ws):
    """
    This function is called when the WebSocket connection is established.
    """
    print("### Connection Opened ###")
    print("Streaming live order book for BTC/USDT...")
    print("-----------------------------------------")

def on_message(ws, message):
    """
    This function is called for each message received from the WebSocket.
    It processes and prints the order book data.
    """
    # Load the received JSON message into a Python dictionary
    data = json.loads(message)

    # Extract the bid (buy) and ask (sell) orders
    bids = data.get('b', [])
    asks = data.get('a', [])

    print("\n--- New Order Book Update ---")

    # Print the top 10 buy orders
    print("BIDS (Buy Orders):")
    if bids:
        for i in range(min(10, len(bids))):
            price, quantity = bids[i]
            print(f"  Price: {float(price):<12.2f} | Quantity: {float(quantity):.6f}")
    else:
        print("  (No bid data in this update)")


    # Print the top 10 sell orders
    print("ASKS (Sell Orders):")
    if asks:
        for i in range(min(10, len(asks))):
            price, quantity = asks[i]
            print(f"  Price: {float(price):<12.2f} | Quantity: {float(quantity):.6f}")
    else:
        print("  (No ask data in this update)")


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