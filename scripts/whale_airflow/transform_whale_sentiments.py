import psycopg2
from configs.config import DB_CONFIG
from utils.logger import get_logger

logger = get_logger("transform_whale_sentiments")

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

SENTIMENT_WEIGHTS = {"Whale": 5.0, "Shark": 2.0, "Dolphin": 0.5}


# ------------------------------------------------------------
# Database helpers
# ------------------------------------------------------------

def get_last_processed_block(cur):
    """Fetch the last processed block height from whale_sentiment table."""
    cur.execute("SELECT COALESCE(MAX(block_height), 0) FROM whale_sentiment;")
    return cur.fetchone()[0]


def get_next_block(cur, last_processed_height):
    """Retrieve the next unprocessed block and its hash."""
    cur.execute("""
        SELECT DISTINCT block_height, block_hash
        FROM whale_transactions
        WHERE block_height > %s
        ORDER BY block_height ASC
        LIMIT 1;
    """, (last_processed_height,))
    return cur.fetchone()


def get_transactions_for_block(cur, block_height):
    """Fetch whale transactions for the given block."""
    cur.execute("""
        SELECT label, value_btc,
               COALESCE(input_count, 0),
               COALESCE(output_count, 0),
               output_addresses
        FROM whale_transactions
        WHERE block_height = %s AND label IS NOT NULL;
    """, (block_height,))
    return cur.fetchall()


def store_sentiment(cur, block_height, block_hash, data, sentiment):
    """Insert computed sentiment into whale_sentiment table."""
    cur.execute("""
        INSERT INTO whale_sentiment
            (block_height, block_hash, whale_count, shark_count, dolphin_count, sentiment)
        VALUES (%s, %s, %s, %s, %s, %s);
    """, (
        block_height,
        block_hash,
        data["Whale"]["count"],
        data["Shark"]["count"],
        data["Dolphin"]["count"],
        sentiment,
    ))


# ------------------------------------------------------------
# Calculation helpers
# ------------------------------------------------------------

def initialize_label_data():
    """Prepare containers for whale, shark, and dolphin stats."""
    return {
        "Whale": {"volume": 0, "flow_score": 0, "count": 0},
        "Shark": {"volume": 0, "flow_score": 0, "count": 0},
        "Dolphin": {"volume": 0, "flow_score": 0, "count": 0},
    }


def calculate_transaction_flow(label, value_btc, input_count, output_count, output_addresses):
    """Calculate flow contribution and detect exchange interactions."""
    weight = SENTIMENT_WEIGHTS.get(label, 1.0)
    weighted_btc = value_btc * weight
    flow = 0

    # Distribution vs. consolidation heuristic
    if output_count > input_count:
        flow += weighted_btc
    elif input_count > output_count:
        flow -= weighted_btc

    # Exchange-based adjustment (bearish)
    if output_addresses and any(addr in EXCHANGE_ADDR_SET for addr in output_addresses):
        flow -= abs(weighted_btc) * 2.0
        logger.info(f"BEARISH: {label} sent {value_btc:.2f} BTC to exchange.")
        return weighted_btc, flow, True

    return weighted_btc, flow, False


def compute_sentiment_score(data, total_weighted_volume, exchange_tx_ratio):
    """Combine weighted metrics into a single sentiment score."""
    if total_weighted_volume == 0:
        return 0, "neutral"

    net_flow_score = sum(d["flow_score"] for d in data.values()) / total_weighted_volume
    dominance_score = (
        (data["Whale"]["volume"] + data["Shark"]["volume"]) - data["Dolphin"]["volume"]
    ) / total_weighted_volume

    score = net_flow_score - dominance_score - (exchange_tx_ratio * 0.5)

    if score > 0.25:
        sentiment = "bullish"
    elif score < -0.25:
        sentiment = "bearish"
    else:
        sentiment = "neutral"

    return score, sentiment


# ------------------------------------------------------------
# Main Orchestration
# ------------------------------------------------------------

def transform_whale_sentiments(**context):
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()

    data = initialize_label_data()

    try:
        last_processed_height = get_last_processed_block(cur)
        next_block = get_next_block(cur, last_processed_height)

        if not next_block:
            logger.info("No new blocks to process for sentiment.")
            return

        block_height, block_hash = next_block
        logger.info(f"Processing sentiment for block {block_height} ({block_hash[:10]}...)")

        transactions = get_transactions_for_block(cur, block_height)

        if not transactions:
            final_sentiment_score = 0
            sentiment = "neutral"
        else:
            total_weighted_volume = 0
            exchange_tx_count = 0

            for label, value_btc, input_count, output_count, output_addresses in transactions:
                if label not in data:
                    continue

                weighted_btc, flow, hit_exchange = calculate_transaction_flow(
                    label, value_btc, input_count, output_count, output_addresses
                )

                d = data[label]
                d["volume"] += weighted_btc
                d["flow_score"] += flow
                d["count"] += 1
                total_weighted_volume += weighted_btc
                if hit_exchange:
                    exchange_tx_count += 1

            exchange_tx_ratio = exchange_tx_count / len(transactions)
            final_sentiment_score, sentiment = compute_sentiment_score(
                data, total_weighted_volume, exchange_tx_ratio
            )

        store_sentiment(cur, block_height, block_hash, data, sentiment)
        conn.commit()

        logger.info(
            f"[Block {block_height}] Sentiment: {sentiment.upper()} | "
            f"Score: {final_sentiment_score:.2f} | "
            f"ExchangeTXs: {exchange_tx_count}/{len(transactions)}"
        )

    except Exception as e:
        logger.error(f"Error during whale sentiment transformation: {e}")
        conn.rollback()
    finally:
        cur.close()
        conn.close()