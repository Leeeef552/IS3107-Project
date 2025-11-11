import asyncio
import aiohttp
import statistics
from datetime import datetime, timezone
from utils.logger import get_logger

# Initialize a structured logger
logger = get_logger("extract_large_transactions")

# --- Constants ---
BASE_URL = "https://mempool.space"  # Bitcoin mempool API base URL
PAGE_SIZE = 25                      # Number of txs per API page
MAX_CONCURRENCY = 24                # Limit for async concurrent requests
RETRIES = 3                         # Retry attempts for network calls
BACKOFF = 1.5                       # Exponential backoff multiplier
REQUEST_TIMEOUT = 15                # HTTP timeout in seconds

# Classification thresholds by BTC amount
LABEL_THRESHOLDS_BTC = [("Whale", 1000), ("Shark", 500), ("Dolphin", 100)]
SATS_PER_BTC = 100_000_000  # Conversion factor

# Known exchange addresses for detecting exchange flows
EXCHANGE_ADDR_SET = {
    "bc1qm34lsc65zpw79lxes69zkqmk6ee3ewf0j77s3h",
    "34xp4vRoCGJym3xR7yCVPFHoCNxv4Twseo",
    "3M219KR5vEneNb47ewrPfWyb5jQ2DjxRP6",
    "bc1qx9t2l3pyny2spqpqlye8svce70nppwtaxwdrp4",
    "bc1qgdjqv0av3q56jvd82tkdjpy7gdp9ut8tlqmgrpmv24sq90ecnvqqjwvw97",
    "bc1q9wvygkq7h9xgcp59mc6ghzczrqlgrj9k3ey9tz",
    "3GsJwMHk8UFXCg5KCiqvS5RVS4zjBoHLAF",
    "bc1qa2eu6p5rl9255e3xz7fcgm6snn4wl5kdfh7zpt05qp5fad9dmsys0qjg0e",
    "19CkUw43czT8yQctnHXNiB5ivNtibWbzqS",
    "bc1q4j7fcl8zx5yl56j00nkqez9zf3f6ggqchwzzcs5hjxwqhsgxvavq3qfgpr",
}

# --- Helper Functions ---

def sats_to_btc(v):
    """Convert satoshis to BTC."""
    return v / SATS_PER_BTC


async def fetch_json(session, url, retries=RETRIES, backoff=BACKOFF, semaphore=None):
    """
    Fetch JSON data from a given URL with retries, exponential backoff, and concurrency control.
    """
    attempt = 0
    while attempt < retries:
        try:
            if semaphore:
                # Limit concurrent requests
                async with semaphore:
                    async with session.get(url, timeout=REQUEST_TIMEOUT) as r:
                        r.raise_for_status()
                        return await r.json()
            else:
                async with session.get(url, timeout=REQUEST_TIMEOUT) as r:
                    r.raise_for_status()
                    return await r.json()

        except (aiohttp.ClientError, asyncio.TimeoutError) as e:
            attempt += 1
            wait_time = backoff * attempt
            logger.warning(
                f"[Attempt {attempt}/{retries}] Error fetching {url}: {e} — retrying in {wait_time:.1f}s"
            )
            await asyncio.sleep(wait_time)

    logger.error(f"Failed to fetch {url} after {retries} retries.")
    raise RuntimeError(f"Request failed after {retries} attempts: {url}")


async def fetch_block_txs(session, block_hash):
    """
    Retrieve all transactions from a block using paginated API calls with concurrency limits.
    """
    semaphore = asyncio.Semaphore(MAX_CONCURRENCY)
    info = await fetch_json(session, f"{BASE_URL}/api/block/{block_hash}", semaphore=semaphore)
    tx_count = info["tx_count"]

    # Calculate pagination offsets
    starts = range(0, tx_count, PAGE_SIZE)

    # Schedule async tasks for each page
    tasks = [
        fetch_json(session, f"{BASE_URL}/api/block/{block_hash}/txs/{s}", semaphore=semaphore)
        for s in starts
    ]

    txs = []
    # Asynchronous iteration over completed tasks
    for t in asyncio.as_completed(tasks):
        try:
            txs.extend(await t)
        except Exception as e:
            logger.error(f"Failed to fetch tx page for block {block_hash}: {e}")
    return info, txs


def modal_script_type(input_types):
    """
    Find the most common script type among transaction inputs.
    Used for identifying probable change-output types.
    """
    from collections import Counter
    return Counter([t for t in input_types if t]).most_common(1)[0][0] if input_types else None


def detect_change_outputs(tx, input_addrs, input_type_mode, input_sum_sats):
    """
    Identify likely change outputs using heuristics:
    - Address reuse
    - Script type matching
    - Relative output size
    Returns (set_of_change_indexes, external_out_sats)
    """
    change_idx = set()
    vouts = tx.get("vout", [])

    # Heuristic 1: address reuse — output address matches input address
    for i, o in enumerate(vouts):
        addr = o.get("scriptpubkey_address")
        if addr and addr in input_addrs:
            change_idx.add(i)

    values = [o.get("value", 0) for o in vouts]
    types  = [o.get("scriptpubkey_type") for o in vouts]
    is_opr = [(t == "op_return") for t in types]

    # Heuristic 2: two-output tx — smaller output likely change
    if len(vouts) == 2 and not change_idx:
        smaller_i = 0 if values[0] <= values[1] else 1
        if input_type_mode and types[smaller_i] == input_type_mode:
            change_idx.add(smaller_i)

    # Heuristic 3: multiple outputs — small same-type output may be change
    if len(vouts) > 2:
        tiny_thr = max(int(input_sum_sats * 0.01), 10_000)
        for i, (val, ty) in enumerate(zip(values, types)):
            if i in change_idx or is_opr[i]:
                continue
            if input_type_mode and ty == input_type_mode and val <= tiny_thr:
                change_idx.add(i)

    # Compute total external (non-change) BTC
    external = sum(
        o.get("value", 0)
        for i, o in enumerate(vouts)
        if i not in change_idx and not is_opr[i]
    )
    return change_idx, external


def classify_label(external_out_btc):
    """Label transaction as Whale/Shark/Dolphin based on BTC size thresholds."""
    for label, thr in LABEL_THRESHOLDS_BTC:
        if external_out_btc >= thr:
            return label
    return None


def flow_sign(input_count, output_count):
    """
    Direction heuristic:
    +1 → distribution (outputs > inputs)
    -1 → consolidation (inputs > outputs)
     0 → neutral
    """
    if output_count > input_count:
        return +1
    if input_count > output_count:
        return -1
    return 0


async def extract_block_metrics(block_hash):
    """
    Extract per-block metrics and identify large-value (smart-money) transactions.
    """
    logger.info(f"Processing block {block_hash[:12]}...")
    async with aiohttp.ClientSession() as session:
        block_info, txs = await fetch_block_txs(session, block_hash)

    # Basic block metadata
    block_height = block_info["height"]
    block_ts = block_info["timestamp"]
    block_iso = datetime.fromtimestamp(block_ts, tz=timezone.utc).isoformat()

    sum_vsize = 0
    fee_total = 0
    fee_rates = []

    whales_rows = []   # individual transaction records
    external_values = []  # (external_btc, weighted_flow)
    to_ex_btc = 0.0
    from_ex_btc = 0.0

    for tx in txs:
        vin = tx.get("vin", [])
        vout = tx.get("vout", [])

        in_addrs, in_types, input_sum = [], [], 0
        is_coinbase = False

        # Aggregate input metadata
        for i in vin:
            pv = i.get("prevout")
            if pv is None:
                is_coinbase = True
                continue
            input_sum += pv.get("value", 0) or 0
            in_addrs.append(pv.get("scriptpubkey_address"))
            in_types.append(pv.get("scriptpubkey_type"))

        input_count, output_count = len(vin), len(vout)
        output_sum = sum(o.get("value", 0) or 0 for o in vout)

        # Estimate missing fee if not directly available
        fee_sats = tx.get("fee")
        if fee_sats is None and not is_coinbase and input_sum >= output_sum:
            fee_sats = input_sum - output_sum
        fee_sats = fee_sats or 0

        vsize = tx.get("vsize", 0) or 0
        weight = tx.get("weight", 0) or 0

        # Accumulate block-wide stats
        sum_vsize += vsize
        fee_total += fee_sats
        if vsize > 0:
            fee_rates.append(fee_sats / vsize)

        # Detect external (non-change) outputs
        external_out = 0
        if not is_coinbase:
            input_mode = modal_script_type(in_types)
            _, external_out = detect_change_outputs(tx, set(a for a in in_addrs if a), input_mode, input_sum)

        o_addrs = [o.get("scriptpubkey_address") for o in vout if o.get("scriptpubkey_address")]

        # Detect exchange involvement
        to_exchange = any(a in EXCHANGE_ADDR_SET for a in o_addrs)
        from_exchange = any(a in EXCHANGE_ADDR_SET for a in in_addrs if a)

        external_btc = sats_to_btc(external_out)
        label = classify_label(external_btc)

        # Weighted flow direction (used for aggregation metrics)
        sgn = flow_sign(input_count, output_count)
        label_weight = {"Whale": 5.0, "Shark": 2.0, "Dolphin": 0.5}.get(label, 0.0)
        flow_contrib = sgn * label_weight * external_btc

        # Exchange flow aggregation
        if to_exchange:
            to_ex_btc += external_btc
        if from_exchange:
            from_ex_btc += external_btc

        # Store labeled transaction
        if label:
            whales_rows.append({
                "txid": tx["txid"],
                "block_hash": block_hash,
                "block_height": block_height,
                "block_timestamp": block_iso,
                "value_btc": float(external_btc),
                "label": label,
                "input_count": input_count,
                "output_count": output_count,
                "fee_sats": int(fee_sats),
                "input_sum_btc": sats_to_btc(input_sum),
                "output_sum_btc": sats_to_btc(output_sum),
                "external_out_btc": float(external_btc),
                "to_exchange": to_exchange,
                "from_exchange": from_exchange,
                "vsize": int(vsize),
                "weight": int(weight),
                "output_addresses": o_addrs,
            })
            external_values.append((external_btc, flow_contrib))

    # Aggregate block-level metrics
    avg_fee = (fee_total / sum_vsize) if sum_vsize else 0
    median_fee = statistics.median(fee_rates) if fee_rates else 0
    total_external_btc = sum(v for v, _ in external_values)
    total_weighted_flow = sum(fc for _, fc in external_values)

    # Top 5 concentration metric (large-tx dominance)
    top5 = sorted([v for v, _ in external_values], reverse=True)[:5]
    top5_conc = (sum(top5) / total_external_btc) if total_external_btc else 0

    # Input/output structure metrics
    avg_in = statistics.fmean([r["input_count"] for r in whales_rows]) if whales_rows else 0
    avg_out = statistics.fmean([r["output_count"] for r in whales_rows]) if whales_rows else 0
    consolidation_index = (avg_in / avg_out) if (avg_in and avg_out) else 0
    distribution_index = (avg_out / avg_in) if (avg_in and avg_in) else 0

    # Final block summary dictionary
    block_metrics = {
        "block_height": block_height,
        "block_hash": block_hash,
        "block_timestamp": block_iso,
        "tx_count": block_info["tx_count"],
        "size": block_info.get("size"),
        "weight": block_info.get("weight"),
        "fill_ratio": (block_info.get("weight", 0) or 0) / 4_000_000,
        "fee_total_sats": fee_total,
        "avg_fee_rate_sat_vb": avg_fee,
        "median_fee_rate_sat_vb": median_fee,
        "whale_weighted_flow": float(total_weighted_flow),
        "whale_total_external_btc": float(total_external_btc),
        "to_exchange_btc": float(to_ex_btc),
        "from_exchange_btc": float(from_ex_btc),
        "top5_concentration": float(top5_conc),
        "consolidation_index": float(consolidation_index),
        "distribution_index": float(distribution_index),
        "labeled_tx_count": len(whales_rows),
        "whale_count": sum(1 for r in whales_rows if r["label"] == "Whale"),
        "shark_count": sum(1 for r in whales_rows if r["label"] == "Shark"),
        "dolphin_count": sum(1 for r in whales_rows if r["label"] == "Dolphin"),
    }
    logger.debug(f"Block {block_hash[:12]} info successfully extracted")
    return whales_rows, block_metrics


def extract_large_transactions(**context):
    """
    Airflow-compatible task function:
    - Retrieves recent block data from previous task (via XCom)
    - Extracts large BTC transaction metrics per block
    - Pushes aggregated data back into XCom for downstream tasks
    """
    ti = context["task_instance"]
    blocks = ti.xcom_pull(key="blocks", task_ids="fetch_recent_blocks")
    if not blocks:
        raise ValueError("No blocks found in XCom from fetch_recent_blocks")

    all_whales, all_block_metrics = [], []

    for b in blocks:
        try:
            whales, bm = asyncio.run(extract_block_metrics(b["hash"]))
            all_whales.extend(whales)
            all_block_metrics.append(bm)
        except Exception as e:
            logger.error(f"Error processing block {b['hash']} at height {b['height']}: {e}", exc_info=True)

    logger.info(f"Smart-money txs: {len(all_whales)} across {len(all_block_metrics)} blocks")
    ti.xcom_push(key="whales", value=all_whales)
    ti.xcom_push(key="block_metrics", value=all_block_metrics)
    return {"whales": len(all_whales), "blocks": len(all_block_metrics)}
