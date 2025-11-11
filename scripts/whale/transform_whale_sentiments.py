import math
import psycopg2
from configs.config import DB_CONFIG
from utils.logger import get_logger

logger = get_logger("transform_whale_sentiments")

# weights without econ-density component
WEIGHTS = {
    "whale_flow": 0.55,
    "exchange_pressure": 0.30,
    "utilization": 0.10,
    "fee_pressure": 0.05,
}

UTIL_BASELINE = 0.80  # center utilization (fill_ratio) around this baseline


def tanh_clip(x, k=3.0):
    return math.tanh(k * x)


def fee_z_score(cur, ref_ts):
    """
    Z-score of avg_fee_rate_sat_vb vs last 24h (rolling window).
    Returns 0 if insufficient data or zero variance.
    """
    cur.execute("""
        SELECT avg(avg_fee_rate_sat_vb), stddev_pop(avg_fee_rate_sat_vb)
        FROM block_metrics
        WHERE block_timestamp >= %s - INTERVAL '24 hours'
          AND block_timestamp <  %s
    """, (ref_ts, ref_ts))
    row = cur.fetchone()
    if not row or row[1] is None or row[1] == 0:
        return (0.0, 0.0)  # mean, sd=0
    return row  # (avg, sd)


def transform_whale_sentiments(**context):
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()
    try:
        cur.execute("""
        SELECT bm.block_height, bm.block_hash, bm.block_timestamp,
               bm.whale_weighted_flow, bm.whale_total_external_btc,
               bm.to_exchange_btc, bm.from_exchange_btc,
               bm.fill_ratio, bm.avg_fee_rate_sat_vb,
               bm.whale_count, bm.shark_count, bm.dolphin_count
        FROM block_metrics bm
        LEFT JOIN whale_sentiment ws ON ws.block_height = bm.block_height
        WHERE ws.block_height IS NULL
        ORDER BY bm.block_height ASC
        """)
        rows = cur.fetchall()
        if not rows:
            logger.info("No new blocks to score.")
            return

        for row in rows:
            (h, block_hash, ts,
             whale_flow, whale_total_ext,
             to_ex, from_ex,
             fill_ratio, avg_fee_rate,
             whale_count, shark_count, dolphin_count) = row

            den = max(whale_total_ext, 1.0)

            wf = tanh_clip(whale_flow / den)
            ex = tanh_clip((to_ex - from_ex) / den)
            ut = tanh_clip(fill_ratio - UTIL_BASELINE)

            mean_fee, sd_fee = fee_z_score(cur, ts)
            fp = tanh_clip((avg_fee_rate - mean_fee) / sd_fee) if sd_fee and sd_fee > 0 else 0.0

            score = (WEIGHTS["whale_flow"] * wf +
                     WEIGHTS["exchange_pressure"] * ex +
                     WEIGHTS["utilization"] * ut +
                     WEIGHTS["fee_pressure"] * fp)

            sentiment = "bullish" if score > 0.25 else "bearish" if score < -0.25 else "neutral"

            cur.execute("""
            INSERT INTO whale_sentiment
            (block_height, block_hash, block_timestamp,
             whale_count, shark_count, dolphin_count,
             score, sentiment,
             whale_flow_component, exchange_pressure_component,
             fee_pressure_component, utilization_component)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """, (h, block_hash, ts,
                  whale_count, shark_count, dolphin_count,
                  score, sentiment,
                  wf, ex, fp, ut))

            logger.info(f"[Block {h}] Sentiment={sentiment.upper()} Score={score:.3f} "
                        f"(wf={wf:.3f}, ex={ex:.3f}, ut={ut:.3f}, fp={fp:.3f})")

        conn.commit()
        logger.info(f"Inserted {len(rows)} whale_sentiment rows.")

    except Exception as e:
        logger.error(f"Error during transformation: {e}")
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()

