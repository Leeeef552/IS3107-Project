import psycopg2
import sqlparse
from configs.config import DB_CONFIG, SCHEMA_DIR
from utils.logger import get_logger

logger = get_logger("init_whaledb")

def connect_to_db():
    conn = psycopg2.connect(**DB_CONFIG)
    logger.info(f"Connected to TimescaleDB: {DB_CONFIG['host']}:{DB_CONFIG['port']}")
    return conn


def execute_schema_script(conn, schema_filename="init_whale_db.sql"):
    """Run the schema creation SQL safely (idempotent)."""
    import os

    script_path = os.path.join(SCHEMA_DIR, schema_filename)
    with open(script_path, "r", encoding="utf-8") as f:
        sql_text = f.read()

    statements = [s.strip() for s in sqlparse.split(sql_text) if s.strip()]
    cur = conn.cursor()
    try:
        for stmt in statements:
            cur.execute(stmt)
        conn.commit()
        logger.info("Executed whale DB schema successfully.")
    except Exception as e:
        conn.rollback()
        logger.error(f"Error running schema: {e}", exc_info=True)
        raise
    finally:
        cur.close()


def init_whaledb(schema_filename="init_whale_db.sql", **_):
    """Initialize Timescale schema for whale tracking."""
    conn = connect_to_db()
    try:
        execute_schema_script(conn, schema_filename)
        logger.info("Whale DB initialized or already up-to-date.")
    finally:
        conn.close()



def load_whale_transactions_to_db(**context):
    ti = context["task_instance"]
    whales = ti.xcom_pull(key="whales") or []
    blocks = ti.xcom_pull(key="block_metrics") or []
    if not whales and not blocks:
        logger.info("Nothing to insert")
        return 0

    conn = connect_to_db()
    inserted_whales = 0
    upsert_blocks = 0
    try:
        with conn, conn.cursor() as cur:
            # upsert blocks
            for b in blocks:
                cur.execute("""
                INSERT INTO block_metrics
                (block_height, block_hash, block_timestamp, tx_count, size, weight, fill_ratio,
                 fee_total_sats, avg_fee_rate_sat_vb, median_fee_rate_sat_vb,
                 whale_weighted_flow, whale_total_external_btc, to_exchange_btc, from_exchange_btc,
                 top5_concentration, consolidation_index, distribution_index,
                 labeled_tx_count, whale_count, shark_count, dolphin_count)
                VALUES (%(block_height)s, %(block_hash)s, %(block_timestamp)s, %(tx_count)s, %(size)s, %(weight)s, %(fill_ratio)s,
                        %(fee_total_sats)s, %(avg_fee_rate_sat_vb)s, %(median_fee_rate_sat_vb)s,
                        %(whale_weighted_flow)s, %(whale_total_external_btc)s, %(to_exchange_btc)s, %(from_exchange_btc)s,
                        %(top5_concentration)s, %(consolidation_index)s, %(distribution_index)s,
                        %(labeled_tx_count)s, %(whale_count)s, %(shark_count)s, %(dolphin_count)s)
                ON CONFLICT (block_height, block_timestamp) DO UPDATE SET
                  block_hash = EXCLUDED.block_hash,
                  block_timestamp = EXCLUDED.block_timestamp,
                  tx_count = EXCLUDED.tx_count,
                  size = EXCLUDED.size,
                  weight = EXCLUDED.weight,
                  fill_ratio = EXCLUDED.fill_ratio,
                  fee_total_sats = EXCLUDED.fee_total_sats,
                  avg_fee_rate_sat_vb = EXCLUDED.avg_fee_rate_sat_vb,
                  median_fee_rate_sat_vb = EXCLUDED.median_fee_rate_sat_vb,
                  whale_weighted_flow = EXCLUDED.whale_weighted_flow,
                  whale_total_external_btc = EXCLUDED.whale_total_external_btc,
                  to_exchange_btc = EXCLUDED.to_exchange_btc,
                  from_exchange_btc = EXCLUDED.from_exchange_btc,
                  top5_concentration = EXCLUDED.top5_concentration,
                  consolidation_index = EXCLUDED.consolidation_index,
                  distribution_index = EXCLUDED.distribution_index,
                  labeled_tx_count = EXCLUDED.labeled_tx_count,
                  whale_count = EXCLUDED.whale_count,
                  shark_count = EXCLUDED.shark_count,
                  dolphin_count = EXCLUDED.dolphin_count;
                """, b)
                upsert_blocks += 1

            # insert smart-money rows
            for w in whales:
                cur.execute("""
                INSERT INTO whale_transactions
                (txid, block_hash, block_height, block_timestamp, value_btc, label,
                input_count, output_count, fee_sats, input_sum_btc, output_sum_btc,
                external_out_btc, to_exchange, from_exchange, vsize, weight, output_addresses)
                VALUES (%s,%s,%s,%s,%s,%s,
                        %s,%s,%s,%s,%s,
                        %s,%s,%s,%s,%s,%s)
                ON CONFLICT ON CONSTRAINT whale_tx_pk DO NOTHING
                """, (
                    w["txid"], w["block_hash"], w["block_height"], w["block_timestamp"], w["value_btc"], w["label"],
                    w["input_count"], w["output_count"], w["fee_sats"], w["input_sum_btc"], w["output_sum_btc"],
                    w["external_out_btc"], w["to_exchange"], w["from_exchange"], w["vsize"], w["weight"], w["output_addresses"]
                ))
                inserted_whales += cur.rowcount

        logger.info("Upserted %d blocks, inserted %d smart-money txs", upsert_blocks, inserted_whales)
        return inserted_whales
    finally:
        conn.close()
