"""
Binance WebSocket Price Streamer for Real-Time Bitcoin Price Updates

This module connects to Binance WebSocket API to stream real-time price data
and stores it in Streamlit session state for dashboard display.
"""

import json
import threading
import time
from datetime import datetime, timezone
from typing import Optional, Dict, Any
from websocket import WebSocketApp
try:
    import streamlit as st
except ImportError:
    # For testing outside Streamlit
    st = None


# Binance WebSocket URL for BTC/USDT ticker stream (updates every second)
BINANCE_WS_URL = "wss://stream.binance.com:9443/ws/btcusdt@ticker"


class BinancePriceStreamer:
    """WebSocket client for streaming real-time Bitcoin price from Binance"""
    
    def __init__(self):
        self.ws: Optional[WebSocketApp] = None
        self.running = False
        self.thread: Optional[threading.Thread] = None
        self.latest_price_data: Optional[Dict[str, Any]] = None
        self.last_update_time: Optional[datetime] = None
        self._lock = threading.Lock()  # Thread-safe access to price data
        
    def _on_message(self, ws, message):
        """Handle incoming WebSocket messages"""
        try:
            data = json.loads(message)
            
            # Extract price data from ticker stream
            # Binance ticker stream provides: current price, 24h high/low, volume, etc.
            price_data = {
                'close': float(data.get('c', 0)),  # Current/last price
                'open': float(data.get('o', 0)),   # 24h open price
                'high': float(data.get('h', 0)),   # 24h high price
                'low': float(data.get('l', 0)),    # 24h low price
                'volume': float(data.get('v', 0)),  # 24h volume
                'price_change': float(data.get('P', 0)),  # 24h price change %
                'time': datetime.fromtimestamp(data.get('E', 0) / 1000, tz=timezone.utc)
            }
            
            # Thread-safe update
            with self._lock:
                self.latest_price_data = price_data
                self.last_update_time = datetime.now(timezone.utc)
            
            # Update Streamlit session state if available
            if st is not None:
                try:
                    if 'binance_price' not in st.session_state:
                        st.session_state.binance_price = {}
                    st.session_state.binance_price = price_data
                except Exception:
                    # Session state might not be available in this context
                    pass
            
        except Exception as e:
            print(f"Error processing WebSocket message: {e}")
    
    def _on_error(self, ws, error):
        """Handle WebSocket errors"""
        print(f"WebSocket error: {error}")
        # Clear price data on error
        with self._lock:
            self.latest_price_data = None
    
    def _on_close(self, ws, close_status_code, close_msg):
        """Handle WebSocket connection close"""
        print(f"WebSocket closed ({close_status_code}): {close_msg}")
        self.running = False
        
        # Attempt to reconnect after a short delay
        if self.running or close_status_code != 1000:
            time.sleep(5)
            if self.running:  # Only reconnect if still supposed to be running
                self._start_websocket()
    
    def _on_open(self, ws):
        """Handle WebSocket connection open"""
        print("Connected to Binance WebSocket - streaming BTC/USDT price updates")
        self.running = True
    
    def _start_websocket(self):
        """Start the WebSocket connection"""
        try:
            self.ws = WebSocketApp(
                BINANCE_WS_URL,
                on_open=self._on_open,
                on_message=self._on_message,
                on_error=self._on_error,
                on_close=self._on_close
            )
            # Run forever with ping/pong to keep connection alive
            self.ws.run_forever(ping_interval=20, ping_timeout=10)
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
        print("Binance WebSocket streamer started in background thread")
    
    def stop(self):
        """Stop WebSocket connection"""
        self.running = False
        if self.ws:
            self.ws.close()
        print("Binance WebSocket streamer stopped")
    
    def get_latest_price(self) -> Optional[Dict[str, Any]]:
        """Get the latest price data (thread-safe)"""
        # First try session state (preferred for Streamlit)
        if st is not None:
            try:
                if 'binance_price' in st.session_state:
                    return st.session_state.get('binance_price')
            except Exception:
                pass
        
        # Fallback to instance variable (thread-safe)
        with self._lock:
            if self.latest_price_data:
                # Return a copy to avoid external modifications
                return dict(self.latest_price_data)
            return None


# Global instance
_streamer: Optional[BinancePriceStreamer] = None


def get_streamer() -> BinancePriceStreamer:
    """Get or create the global WebSocket streamer instance"""
    global _streamer
    if _streamer is None:
        _streamer = BinancePriceStreamer()
    return _streamer


def start_price_stream():
    """Start the WebSocket price stream (call this once in the dashboard)"""
    streamer = get_streamer()
    if not streamer.running:
        streamer.start()


def stop_price_stream():
    """Stop the WebSocket price stream"""
    streamer = get_streamer()
    if streamer.running:
        streamer.stop()


def get_realtime_price() -> Optional[Dict[str, Any]]:
    """Get real-time price from WebSocket stream"""
    streamer = get_streamer()
    return streamer.get_latest_price()

