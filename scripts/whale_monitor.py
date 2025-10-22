"""
Whale Transaction Monitor

Monitors Bitcoin mempool for large transactions and stores them in the database.
Uses mempool.space API for real-time transaction data.
"""

import asyncio
import aiohttp
import psycopg2
from datetime import datetime
import sys
import os

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from configs.config import DB_CONFIG
from utils.logger import get_logger

log = get_logger("whale_monitor")

class WhaleMonitor:
    def __init__(self, min_btc=50):
        """
        Initialize whale transaction monitor

        Args:
            min_btc: Minimum BTC value to consider as a "whale" transaction
        """
        self.min_sats = int(min_btc * 100_000_000)
        self.min_btc = min_btc
        self.session = None
        self.btc_price = None
        self.mempool_api = "https://mempool.space/api/mempool/recent"
        self.price_api = "https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=usd"
        self.checked_txids = set()
        self.conn = None

    async def init_session(self):
        """Initialize aiohttp session"""
        if not self.session:
            self.session = aiohttp.ClientSession()

    async def close_session(self):
        """Close aiohttp session"""
        if self.session:
            await self.session.close()

    def connect_db(self):
        """Connect to database"""
        if not self.conn or self.conn.closed:
            self.conn = psycopg2.connect(**DB_CONFIG)
            log.info(f"Connected to database: {DB_CONFIG['host']}:{DB_CONFIG['port']}")
        return self.conn

    def close_db(self):
        """Close database connection"""
        if self.conn and not self.conn.closed:
            self.conn.close()
            log.info("Database connection closed")

    async def get_btc_price(self):
        """Fetch current BTC price from CoinGecko"""
        try:
            await self.init_session()
            async with self.session.get(self.price_api, timeout=10) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    self.btc_price = data["bitcoin"]["usd"]
                    log.debug(f"Updated BTC price: ${self.btc_price:,.2f}")
                else:
                    log.warning(f"Failed to fetch BTC price: {resp.status}")
        except Exception as e:
            log.error(f"Error fetching BTC price: {e}")
            # Use fallback price if available
            if not self.btc_price:
                self.btc_price = 30_000
        return self.btc_price

    async def price_updater(self):
        """Background task to update BTC price every 5 minutes"""
        while True:
            await self.get_btc_price()
            await asyncio.sleep(300)  # 5 minutes

    def save_whale_transaction(self, txid, value_sats, tx_data=None):
        """
        Save whale transaction to database

        Args:
            txid: Transaction ID
            value_sats: Transaction value in satoshis
            tx_data: Additional transaction data (optional)
        """
        try:
            conn = self.connect_db()
            cur = conn.cursor()

            btc_value = value_sats / 100_000_000
            usd_value = btc_value * (self.btc_price or 30_000)

            # Check if transaction already exists
            cur.execute(
                "SELECT txid FROM whale_transactions WHERE txid = %s LIMIT 1",
                (txid,)
            )

            if cur.fetchone():
                log.debug(f"Transaction {txid[:8]}... already in database")
                cur.close()
                return False

            # Insert new whale transaction
            cur.execute("""
                INSERT INTO whale_transactions
                (txid, detected_at, value_btc, value_usd, btc_price_at_detection, status)
                VALUES (%s, NOW(), %s, %s, %s, 'mempool')
                ON CONFLICT (txid, detected_at) DO NOTHING
            """, (txid, btc_value, usd_value, self.btc_price))

            conn.commit()
            cur.close()

            log.info(f"💎 Whale detected: {btc_value:,.2f} BTC (${usd_value:,.0f}) - TX: {txid[:16]}...")
            return True

        except Exception as e:
            log.error(f"Error saving transaction: {e}")
            if conn:
                conn.rollback()
            return False

    async def fetch_recent_transactions(self):
        """Fetch recent transactions from mempool.space"""
        try:
            await self.init_session()
            async with self.session.get(self.mempool_api, timeout=15) as resp:
                if resp.status == 200:
                    txs = await resp.json()
                    return txs
                else:
                    log.warning(f"Failed to fetch transactions: {resp.status}")
                    return []
        except asyncio.TimeoutError:
            log.warning("Timeout fetching transactions from mempool")
            return []
        except Exception as e:
            log.error(f"Error fetching transactions: {e}")
            return []

    async def monitor(self):
        """
        Main monitoring loop
        Checks mempool.space for new large transactions every 10 seconds
        """
        log.info(f"🐋 Starting whale monitor (threshold: {self.min_btc} BTC)")
        log.info(f"API: {self.mempool_api}")

        # Get initial BTC price
        await self.get_btc_price()

        # Start price updater in background
        asyncio.create_task(self.price_updater())

        poll_interval = 10  # seconds

        while True:
            try:
                txs = await self.fetch_recent_transactions()

                whale_count = 0
                for tx in txs:
                    txid = tx.get("txid")
                    value = tx.get("value", 0)

                    # Skip if already checked
                    if txid in self.checked_txids:
                        continue

                    # Mark as checked
                    self.checked_txids.add(txid)

                    # Check if it's a whale transaction
                    if value >= self.min_sats:
                        if self.save_whale_transaction(txid, value, tx):
                            whale_count += 1

                # Cleanup checked_txids if it gets too large
                if len(self.checked_txids) > 10000:
                    log.info("Clearing checked transaction cache")
                    self.checked_txids.clear()

                if whale_count > 0:
                    log.info(f"Found {whale_count} new whale transaction(s) in this batch")

            except Exception as e:
                log.error(f"Error in monitoring loop: {e}")

            # Wait before next poll
            await asyncio.sleep(poll_interval)

    async def run(self):
        """Run the whale monitor"""
        try:
            await self.monitor()
        except KeyboardInterrupt:
            log.info("\n👋 Stopping whale monitor...")
        finally:
            await self.close_session()
            self.close_db()


async def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(description="Monitor Bitcoin whale transactions")
    parser.add_argument(
        "--min-btc",
        type=float,
        default=50,
        help="Minimum BTC amount to consider as whale transaction (default: 50)"
    )

    args = parser.parse_args()

    monitor = WhaleMonitor(min_btc=args.min_btc)
    await monitor.run()


if __name__ == "__main__":
    asyncio.run(main())
