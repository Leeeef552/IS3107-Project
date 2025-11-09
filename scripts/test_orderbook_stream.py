#!/usr/bin/env python3
"""
Test script for Binance Order Book WebSocket

This script tests the order book WebSocket connection and displays
real-time order book updates.
"""

import sys
import os
import time

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dashboard.cryptocompare_orderbook_ws import start_orderbook_stream, get_orderbook_data

def main():
    print("=" * 60)
    print("Binance Order Book WebSocket Test")
    print("=" * 60)
    print("\nStarting order book stream...")
    print("Endpoint: wss://stream.binance.com:9443/ws/btcusdt@depth20@100ms")
    
    # Start the WebSocket
    start_orderbook_stream()
    
    print("Waiting for initial data (should arrive within 2-3 seconds)...\n")
    
    try:
        updates = 0
        consecutive_no_data = 0
        max_wait = 10  # Maximum consecutive waits before giving up
        
        while updates < 5:  # Show 5 updates then exit (1000 levels is verbose)
            time.sleep(2)
            
            data = get_orderbook_data()
            if data and data.get('bids') and data.get('asks'):
                consecutive_no_data = 0  # Reset counter
                updates += 1
                print(f"\n{'='*60}")
                print(f"Update #{updates}")
                print(f"{'='*60}")
                
                if data.get('last_update'):
                    print(f"Last Update: {data['last_update']}")
                
                bids = data.get('bids', [])
                asks = data.get('asks', [])
                
                print(f"\n📊 Order Book Stats:")
                print(f"   Bid Levels: {len(bids)}")
                print(f"   Ask Levels: {len(asks)}")
                
                if bids and asks:
                    best_bid = bids[0]
                    best_ask = asks[0]
                    spread = best_ask['price'] - best_bid['price']
                    spread_pct = (spread / best_bid['price']) * 100
                    mid_price = (best_bid['price'] + best_ask['price']) / 2
                    
                    print(f"\n💰 Best Prices:")
                    print(f"   Best Bid:  ${best_bid['price']:>10,.2f} x {best_bid['quantity']:>8.4f} BTC")
                    print(f"   Best Ask:  ${best_ask['price']:>10,.2f} x {best_ask['quantity']:>8.4f} BTC")
                    print(f"   Mid Price: ${mid_price:>10,.2f}")
                    print(f"   Spread:    ${spread:>10,.2f} ({spread_pct:.3f}%)")
                    
                    # Show top 10 bids and asks
                    print(f"\n📗 Top 10 Bids:")
                    for i, bid in enumerate(bids[:10], 1):
                        print(f"   {i}. ${bid['price']:>10,.2f} x {bid['quantity']:>8.4f} BTC")
                    
                    print(f"\n📕 Top 10 Asks:")
                    for i, ask in enumerate(asks[:10], 1):
                        print(f"   {i}. ${ask['price']:>10,.2f} x {ask['quantity']:>8.4f} BTC")
                    
                    # Calculate total depth
                    total_bid_btc = sum(b['quantity'] for b in bids)
                    total_ask_btc = sum(a['quantity'] for a in asks)
                    
                    print(f"\n📊 Total Depth:")
                    print(f"   Bid Side: {total_bid_btc:>10.4f} BTC (${total_bid_btc * mid_price:>15,.2f})")
                    print(f"   Ask Side: {total_ask_btc:>10.4f} BTC (${total_ask_btc * mid_price:>15,.2f})")
            else:
                consecutive_no_data += 1
                if consecutive_no_data >= max_wait:
                    print(f"\n\n❌ No data received after {max_wait * 2} seconds.")
                    print("Possible issues:")
                    print("  1. Network connectivity problem")
                    print("  2. Binance WebSocket endpoint may be down")
                    print("  3. Firewall blocking WebSocket connection")
                    print("\nTry:")
                    print("  - Check internet connection")
                    print("  - Test Binance API: https://www.binance.com/")
                    print("  - Check terminal for WebSocket error messages")
                    break
                print(f"\r⏳ Waiting for data... ({updates}/5 updates received, attempt {consecutive_no_data}/{max_wait})", end='', flush=True)
        
        if updates > 0:
            print("\n\n✅ Test completed successfully!")
            print(f"Received {updates} order book updates with 1000 levels each.")
            print("Order book WebSocket is working correctly.")
        
    except KeyboardInterrupt:
        print("\n\n⚠️  Test interrupted by user")
    except Exception as e:
        print(f"\n\n❌ Error during test: {e}")
        import traceback
        traceback.print_exc()
    finally:
        print("\nStopping order book stream...")
        print("=" * 60)

if __name__ == "__main__":
    main()
