import requests
from datetime import datetime, timezone
from utils.logger import get_logger

logger = get_logger("extract_large_transactions.py")


def fetch_recent_blocks(count: int = 5, **context):
    """
    Airflow task: Fetch recent Bitcoin block headers.
    Pushes list of block dicts to XCom.
    """
    API = "https://mempool.space/api/blocks"
    logger.info(f"Starting fetch_recent_blocks(count={count})")

    def iso(ts):
        return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()

    try:
        logger.debug(f"Requesting latest {count} blocks from {API}")
        resp = requests.get(API, timeout=10)
        resp.raise_for_status()

        blocks = resp.json()[:count]
        logger.info(f"Fetched {len(blocks)} blocks successfully")

        block_list = [
            {
                "height": b["height"],
                "hash": b["id"],
                "timestamp": iso(b["timestamp"]),
                "tx_count": b.get("tx_count"),
            }
            for b in blocks
        ]

        # Push to XCom for next task
        context["task_instance"].xcom_push(key="blocks", value=block_list)
        logger.debug(f"Pushed {len(block_list)} blocks to XCom")

        logger.info("fetch_recent_blocks completed successfully")
        return block_list

    except requests.RequestException as e:
        logger.error(f"Network error fetching blocks: {e}", exc_info=True)
        raise
    except Exception as e:
        logger.error(f"Unexpected error in fetch_recent_blocks: {e}", exc_info=True)
        raise
