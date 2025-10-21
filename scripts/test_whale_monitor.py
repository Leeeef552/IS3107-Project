"""
Test script for whale monitor

This script tests the whale monitoring system with a very low threshold
to quickly see transactions being detected and stored.
"""

import asyncio
import sys
import os

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.whale_monitor import WhaleMonitor

async def test_monitor():
    """Run whale monitor with low threshold for testing"""
    print("=" * 80)
    print("  WHALE MONITOR TEST")
    print("=" * 80)
    print()
    print("This test runs the whale monitor with a LOW threshold (0.01 BTC)")
    print("to quickly detect transactions and verify the system works.")
    print()
    print("You should see transactions being detected within 1-2 minutes.")
    print()
    print("Press Ctrl+C to stop the test.")
    print("=" * 80)
    print()

    # Create monitor with very low threshold for testing
    monitor = WhaleMonitor(min_btc=0.01)

    try:
        await monitor.run()
    except KeyboardInterrupt:
        print("\n\nTest completed!")
        print("\nTo check results, run:")
        print("  docker exec timescaledb psql -U postgres -d postgres \\")
        print("    -c \"SELECT * FROM whale_transactions ORDER BY detected_at DESC LIMIT 5;\"")


if __name__ == "__main__":
    asyncio.run(test_monitor())
