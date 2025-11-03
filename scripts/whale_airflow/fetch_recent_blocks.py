import requests
from datetime import datetime, timezone
from utils.logger import get_logger

logger = get_logger("extract_large_transactions.py")

BASE_URL = "https://mempool.space/api"


def _iso(ts: int) -> str:
    return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()


def _fetch_block_header(hash_or_height: str):
    """Return header dict for a single block."""
    url = f"{BASE_URL}/block/{hash_or_height}"
    r = requests.get(url, timeout=10)
    r.raise_for_status()
    b = r.json()
    return {
        "height": b["height"],
        "hash": b["id"],
        "timestamp": _iso(b["timestamp"]),
        "tx_count": b.get("tx_count"),
        "previous_block_hash": b.get("previousblockhash"),
    }


def fetch_recent_blocks(count: int = 5, **context):
    """
    Fetch *count* recent Bitcoin block headers (count can be >10).
    Works by walking backwards from the current tip.
    """
    logger.info(f"Starting fetch_recent_blocks(count={count})")

    # 1. get current tip
    tip_hash = requests.get(f"{BASE_URL}/blocks", timeout=10).json()[0]["id"]

    blocks = []
    current_hash = tip_hash

    for _ in range(count):
        try:
            hdr = _fetch_block_header(current_hash)
        except Exception as e:
            logger.error(f"Failed to fetch header {current_hash}: {e}")
            break
        blocks.append(hdr)
        current_hash = hdr.get("previous_block_hash")
        if not current_hash:          # genesis
            break

    logger.info(f"Fetched {len(blocks)} blocks successfully")

    # Push to XCom for next task
    context["task_instance"].xcom_push(key="blocks", value=blocks)
    return blocks