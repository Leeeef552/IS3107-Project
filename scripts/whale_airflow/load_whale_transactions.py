import psycopg2
import sqlparse
from utils.logger import get_logger
from configs.config import DB_CONFIG, SCHEMA_DIR

logger = get_logger("load_whale_transactions")

# ----------------------------------------------------------------------
# HELPER FUNCTIONS
# ----------------------------------------------------------------------
def connect_to_db():
    conn = psycopg2.connect(**DB_CONFIG)
    logger.info(f"Connected to TimescaleDB: {DB_CONFIG['host']}:{DB_CONFIG['port']}")
    return conn

def execute_schema_script(conn, schema_filename="init_whale_db_airflow.sql"):
    import re

    script_path = f"{SCHEMA_DIR}/{schema_filename}"
    with open(script_path, "r", encoding="utf-8") as file:
        sql_text = file.read()

    statements = [s.strip() for s in sqlparse.split(sql_text) if s.strip()]

    cur = conn.cursor()
    try:
        for stmt in statements:
            # Normalize to uppercase for detection
            upper = stmt.lstrip().upper()

            # Some statements must be run outside transactions
            needs_autocommit = (
                upper.startswith("CALL REFRESH_CONTINUOUS_AGGREGATE")
                or upper.startswith("CREATE EXTENSION")
            )

            if needs_autocommit:
                logger.debug("Running in autocommit mode: %s", stmt.split('\n')[0][:80])
                # Commit open work first
                if not conn.autocommit:
                    conn.commit()
                old_mode = conn.autocommit
                conn.autocommit = True
                try:
                    with conn.cursor() as c2:
                        c2.execute(stmt)
                finally:
                    conn.autocommit = old_mode
            else:
                cur.execute(stmt)

        if not conn.autocommit:
            conn.commit()

        logger.info("Executed init_whale DB schema successfully")
        return True
    finally:
        cur.close()



def init_whaledb(schema_filename: str = "init_whale_db_airflow.sql", **_):
    """
    Run the DB initialization SQL from file. Safe to re-run.
    """
    conn = connect_to_db()
    try:
        execute_schema_script(conn, schema_filename=schema_filename)
        logger.info("Whale DB initialized/verified.")
    finally:
        conn.close()


def load_whale_transactions_to_db(**context):
    ti = context["task_instance"]
    whales = ti.xcom_pull(key="whales") or []
    if not whales:
        logger.info("No whale/shark/dolphin transactions to insert")
        return 0

    detected_at = context.get("ts")  # Airflow logical run timestamp

    conn = connect_to_db()
    inserted = 0
    try:
        with conn, conn.cursor() as cur:
            for w in whales:
                cur.execute(
                    """
                    INSERT INTO whale_transactions
                    (txid, block_hash, block_height, detected_at, value_btc, label)
                    VALUES (%s, %s, %s, %s::timestamptz, %s, %s)
                    ON CONFLICT ON CONSTRAINT whale_transactions_pkey DO NOTHING
                    """,
                    (
                        w["txid"],
                        w["block_hash"],
                        w["block_height"],
                        detected_at,
                        w["value_btc"],
                        w["label"],
                    ),
                )
                inserted += cur.rowcount
        logger.info("Inserted %d new whale/shark/dolphin transactions", inserted)
        return inserted
    finally:
        conn.close()