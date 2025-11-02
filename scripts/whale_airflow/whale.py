import asyncio
import aiohttp
from utils.logger import get_logger

logger = get_logger("get_block_transactions.py")

BASE_URL = "https://mempool.space"
PAGE_SIZE = 25

# Define your thresholds for labels (in BTC)
LABEL_THRESHOLDS = [
    ("Whale", 1000),
    ("Shark", 500),
    ("Dolphin", 100),
]

MIN_BTC_VALUE = 100  # for example, only look at transactions ≥ 10 BTC

def sats_to_btc(v):
    return v / 100_000_000

async def fetch_json(session, url):
    async with session.get(url) as r:
        r.raise_for_status()
        return await r.json()

async def get_block_info(session, block_hash):
    logger.info("Getting bitcoin block info")
    return await fetch_json(session, f"{BASE_URL}/api/block/{block_hash}")

async def fetch_page(session, block_hash, start):
    url = f"{BASE_URL}/api/block/{block_hash}/txs/{start}"
    return await fetch_json(session, url)

async def get_tx_details(session, txid):
    # new function: fetch full transaction details
    data = await fetch_json(session, f"{BASE_URL}/api/tx/{txid}")
    return data

def label_for_value(btc_value):
    # determines label by descending threshold
    for label, thr in LABEL_THRESHOLDS:
        if btc_value >= thr:
            return label
    return "Small"

async def main():
    async with aiohttp.ClientSession(
        connector=aiohttp.TCPConnector(limit=60, limit_per_host=20, ttl_dns_cache=300),
        headers={"Accept-Encoding": "gzip"},
    ) as session:
        tip = await session.get(f"{BASE_URL}/api/blocks/tip/hash")
        block_hash = (await tip.text()).strip()

        info = await get_block_info(session, block_hash)
        tx_count = info["tx_count"]
        starts = range(0, tx_count, PAGE_SIZE)

        sem = asyncio.Semaphore(16)  # soft cap to avoid 429s

        async def guarded_fetch(start):
            async with sem:
                return await fetch_page(session, block_hash, start)

        logger.info("Getting all bitcoin transactions within block")
        tasks = [asyncio.create_task(guarded_fetch(s)) for s in starts]
        large = []
        for task in asyncio.as_completed(tasks):
            page = await task
            for tx in page:
                total_btc = sats_to_btc(sum(o["value"] for o in tx["vout"]))
                if total_btc >= MIN_BTC_VALUE:
                    large.append((tx["txid"], total_btc))

        logger.info(f"Found {len(large)} txs ≥ {MIN_BTC_VALUE} BTC")

        # Now fetch details & print
        for txid, val in large[:50]:
            details = await get_tx_details(session, txid)
            num_inputs = len(details["vin"])
            num_outputs = len(details["vout"])
            timestamp = details["status"]["block_time"] if details["status"]["confirmed"] else None
            label = label_for_value(val)
            print(f"{txid} → {val:.8f} BTC | Label: {label} | Time: {timestamp} | Inputs: {num_inputs} | Outputs: {num_outputs}")

if __name__ == "__main__":
    asyncio.run(main())
