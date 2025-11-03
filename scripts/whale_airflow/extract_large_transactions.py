import asyncio
import aiohttp
from utils.logger import get_logger
from datetime import datetime, timezone

logger = get_logger("extract_large_transactions")

BASE_URL = "https://mempool.space"
PAGE_SIZE = 25
LABEL_THRESHOLDS = [("Whale", 1000), ("Shark", 500), ("Dolphin", 100)]

def sats_to_btc(v):
    return v / 100_000_000

async def fetch_json(session, url):
    async with session.get(url) as r:
        r.raise_for_status()
        return await r.json()

async def fetch_block_txs(session, block_hash):
    info = await fetch_json(session, f"{BASE_URL}/api/block/{block_hash}")
    tx_count = info["tx_count"]
    block_height = info["height"]
    block_ts = info["timestamp"]
    starts = range(0, tx_count, PAGE_SIZE)
    tasks = [fetch_json(session, f"{BASE_URL}/api/block/{block_hash}/txs/{s}") for s in starts]
    results = []
    for task in asyncio.as_completed(tasks):
        results.extend(await task)
    return block_height, block_ts, results

def label_for_value(btc_value):
    for label, thr in LABEL_THRESHOLDS:
        if btc_value >= thr:
            return label
    return None

async def extract_whales(block_hash):
    async with aiohttp.ClientSession() as session:
        block_height, block_ts, txs = await fetch_block_txs(session, block_hash)
        block_timestamp_iso = datetime.fromtimestamp(block_ts, tz=timezone.utc).isoformat()

        whales = []
        for tx in txs:
            vouts = tx.get("vout", [])
            total_btc = sats_to_btc(sum(o.get("value", 0) for o in vouts))
            addresses = [o.get("scriptpubkey_address") for o in vouts if o.get("scriptpubkey_address")]

            label = label_for_value(total_btc)
            if label:
                whales.append({
                    "txid": tx["txid"],
                    "block_hash": block_hash,
                    "block_height": block_height,
                    "block_timestamp": block_timestamp_iso,
                    "value_btc": total_btc,
                    "label": label,
                    "output_count": len(vouts),
                    "output_addresses": addresses,
                })
        return whales

def extract_large_transactions(**context):
    ti = context["task_instance"]
    blocks = ti.xcom_pull(key="blocks", task_ids="fetch_recent_blocks")

    if not blocks:
        raise ValueError("No blocks found in XCom from fetch_recent_blocks")

    # proceed as before...
    loop = asyncio.get_event_loop()
    all_whales = []
    for b in blocks:
        whales = loop.run_until_complete(extract_whales(b["hash"]))
        all_whales.extend(whales)

    logger.info(f"Found {len(all_whales)} whales/sharks/dolphins total across {len(blocks)} blocks")
    ti.xcom_push(key="whales", value=all_whales)
    return all_whales