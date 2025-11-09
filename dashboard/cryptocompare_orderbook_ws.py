"""
Binance WebSocket Order Book Streamer for Real-Time Order Book Updates

This module connects to Binance WebSocket API to stream real-time order book data
and stores it in Streamlit session state for dashboard display.

Uses the full depth stream (@depth) for complete order book with 100+ levels.
"""

import json
import threading
import time
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
import requests
# Use direct import from websocket._app to avoid namespace conflicts
from websocket._app import WebSocketApp
import os
from dotenv import load_dotenv

try:
    import streamlit as st
except ImportError:
    # For testing outside Streamlit
    st = None

load_dotenv()

# Binance WebSocket URL for FULL order book depth
# Using @depth for complete order book (100+ levels)
BINANCE_ORDERBOOK_WS_URL = "wss://stream.binance.com:9443/ws/btcusdt@depth@100ms"

# Binance REST API for order book snapshot
BINANCE_SNAPSHOT_API = "https://api.binance.com/api/v3/depth?symbol=BTCUSDT&limit=1000"


class BinanceOrderBookStreamer:
    """WebSocket client for streaming real-time order book from Binance
    
    Uses full depth stream (@depth) which provides incremental updates.
    Maintains local order book by applying updates to initial snapshot.
    """
    
    def __init__(self, depth=100):
        """
        Initialize order book streamer
        
        Args:
            depth: Number of levels to track (we'll maintain top 100 from full stream)
        """
        self.ws: Optional[WebSocketApp] = None
        self.running = False
        self.thread: Optional[threading.Thread] = None
        self.depth = depth
        
        # Order book data
        self.bids: Dict[str, float] = {}  # Price -> Quantity mapping
        self.asks: Dict[str, float] = {}  # Price -> Quantity mapping
        self.last_update_id = 0
        self.last_update_time: Optional[datetime] = None
        self._lock = threading.Lock()  # Thread-safe access
        self._snapshot_loaded = False
        
    def _get_snapshot(self):
        """Get initial order book snapshot from REST API"""
        try:
            response = requests.get(BINANCE_SNAPSHOT_API, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            with self._lock:
                # Clear existing data
                self.bids.clear()
                self.asks.clear()
                
                # Load snapshot
                for bid in data.get('bids', []):
                    price, qty = bid[0], bid[1]
                    if float(qty) > 0:
                        self.bids[price] = float(qty)
                
                for ask in data.get('asks', []):
                    price, qty = ask[0], ask[1]
                    if float(qty) > 0:
                        self.asks[price] = float(qty)
                
                self.last_update_id = data.get('lastUpdateId', 0)
                self._snapshot_loaded = True
                self.last_update_time = datetime.now(timezone.utc)
                
            print(f"Loaded snapshot: {len(self.bids)} bids, {len(self.asks)} asks")
            return True
        except Exception as e:
            print(f"Error getting snapshot: {e}")
            return False
        
    def _on_message(self, ws, message):
        """Handle incoming WebSocket messages"""
        try:
            data = json.loads(message)
            
            # Wait for snapshot to be loaded first
            if not self._snapshot_loaded:
                return
            
            # Binance depth stream format
            if 'e' in data and data['e'] == 'depthUpdate':
                self._process_orderbook_update(data)
                
        except Exception as e:
            print(f"Error processing WebSocket message: {e}")
    
    def _process_orderbook_update(self, data):
        """Process incremental order book update"""
        try:
            # Get update IDs
            first_update_id = data.get('U')
            final_update_id = data.get('u')
            
            # Skip old updates
            if final_update_id <= self.last_update_id:
                return
            
            # Extract updates
            bids_updates = data.get('b', [])
            asks_updates = data.get('a', [])
            
            # Apply updates
            with self._lock:
                # Update bids
                for bid in bids_updates:
                    price, qty = bid[0], float(bid[1])
                    if qty == 0:
                        # Remove price level
                        self.bids.pop(price, None)
                    else:
                        # Update price level
                        self.bids[price] = qty
                
                # Update asks
                for ask in asks_updates:
                    price, qty = ask[0], float(ask[1])
                    if qty == 0:
                        # Remove price level
                        self.asks.pop(price, None)
                    else:
                        # Update price level
                        self.asks[price] = qty
                
                self.last_update_id = final_update_id
                self.last_update_time = datetime.now(timezone.utc)
            
            # Update Streamlit session state
            self._update_session_state()
                    
        except Exception as e:
            print(f"Error processing order book update: {e}")
    
    def _update_session_state(self):
        """Update Streamlit session state with formatted order book"""
        try:
            with self._lock:
                # Convert to sorted lists (top N levels)
                bids_sorted = sorted(
                    [{'price': float(p), 'quantity': q} for p, q in self.bids.items()],
                    key=lambda x: x['price'],
                    reverse=True
                )[:self.depth]
                
                asks_sorted = sorted(
                    [{'price': float(p), 'quantity': q} for p, q in self.asks.items()],
                    key=lambda x: x['price']
                )[:self.depth]
                
                # Update session state if available
                if st is not None:
                    try:
                        # Initialize session state if not exists
                        if 'orderbook_data' not in st.session_state:
                            st.session_state.orderbook_data = {
                                'bids': [],
                                'asks': [],
                                'last_update': None
                            }
                        
                        # Update with new data
                        st.session_state.orderbook_data = {
                            'bids': bids_sorted,
                            'asks': asks_sorted,
                            'last_update': self.last_update_time
                        }
                    except Exception as e:
                        print(f"Error updating session state: {e}")
        except Exception as e:
            print(f"Error in _update_session_state: {e}")
    
    def _on_error(self, ws, error):
        """Handle WebSocket errors"""
        print(f"WebSocket error: {error}")
        with self._lock:
            self.bids = {}
            self.asks = {}
            self._snapshot_loaded = False
    
    def _on_close(self, ws, close_status_code, close_msg):
        """Handle WebSocket connection close"""
        print(f"WebSocket closed ({close_status_code}): {close_msg}")
        self.running = False
        
        # Attempt to reconnect after a short delay
        if close_status_code != 1000:
            time.sleep(5)
            if self.running:
                self._start_websocket()
    
    def _on_open(self, ws):
        """Handle WebSocket connection open"""
        print("Connected to Binance WebSocket - streaming BTC/USDT full depth order book")
        self.running = True
        
        # Get initial snapshot before processing updates
        print("Fetching initial order book snapshot...")
        if self._get_snapshot():
            print("✅ Snapshot loaded, now processing live updates")
        else:
            print("⚠️  Failed to load snapshot, will retry...")
            # Try again after a delay
            time.sleep(2)
            self._get_snapshot()
    
    def _start_websocket(self):
        """Start the WebSocket connection"""
        try:
            self.ws = WebSocketApp(
                BINANCE_ORDERBOOK_WS_URL,
                on_open=self._on_open,
                on_message=self._on_message,
                on_error=self._on_error,
                on_close=self._on_close
            )
            # Run forever with ping/pong to keep connection alive
            self.ws.run_forever(ping_interval=30, ping_timeout=10)
        except Exception as e:
            print(f"Error starting WebSocket: {e}")
            self.running = False
    
    def start(self):
        """Start WebSocket in background thread"""
        if self.running:
            return  # Already running
        
        self.running = True
        self.thread = threading.Thread(target=self._start_websocket, daemon=True)
        self.thread.start()
        print("Binance order book streamer started in background thread")
    
    def stop(self):
        """Stop WebSocket connection"""
        self.running = False
        if self.ws:
            self.ws.close()
        print("Binance order book streamer stopped")
    
    def get_orderbook(self, depth: int = 1000) -> Dict[str, Any]:
        """
        Get current order book snapshot.
        
        Args:
            depth: Number of levels to return (default: 1000)
        
        Returns:
            Dictionary with bids, asks, and metadata
        """
        with self._lock:
            # Convert dictionaries to sorted lists
            bids_sorted = sorted(
                [{'price': float(p), 'quantity': q} for p, q in self.bids.items()],
                key=lambda x: x['price'],
                reverse=True
            )[:depth]
            
            asks_sorted = sorted(
                [{'price': float(p), 'quantity': q} for p, q in self.asks.items()],
                key=lambda x: x['price']
            )[:depth]
            
            return {
                'bids': bids_sorted,
                'asks': asks_sorted,
                'last_update': self.last_update_time
            }


# Global instance
_orderbook_streamer: Optional[BinanceOrderBookStreamer] = None


def get_orderbook_streamer() -> BinanceOrderBookStreamer:
    """Get or create the global order book streamer instance"""
    global _orderbook_streamer
    if _orderbook_streamer is None:
        _orderbook_streamer = BinanceOrderBookStreamer(depth=1000)  # Get top 1000 levels
    return _orderbook_streamer


def start_orderbook_stream():
    """Start the order book WebSocket stream"""
    streamer = get_orderbook_streamer()
    if not streamer.running:
        streamer.start()


def get_orderbook_data() -> Optional[Dict[str, Any]]:
    """Get current order book data"""
    streamer = get_orderbook_streamer()
    return streamer.get_orderbook()


# For testing
if __name__ == "__main__":
    print("Starting Binance order book streamer...")
    start_orderbook_stream()
    
    try:
        while True:
            time.sleep(5)
            data = get_orderbook_data()
            if data:
                print(f"\nOrder Book Update at {data['last_update']}")
                print(f"Bids: {len(data['bids'])} levels")
                print(f"Asks: {len(data['asks'])} levels")
                if data['bids']:
                    print(f"Best Bid: ${data['bids'][0]['price']:,.2f} x {data['bids'][0]['quantity']:.4f} BTC")
                if data['asks']:
                    print(f"Best Ask: ${data['asks'][0]['price']:,.2f} x {data['asks'][0]['quantity']:.4f} BTC")
            else:
                print("No data yet...")
    except KeyboardInterrupt:
        print("\nStopping...")
        get_orderbook_streamer().stop()

