import os
import psycopg2
import sqlparse
from dotenv import load_dotenv
from utils.logger import get_logger
from configs.config import DB_CONFIG, AGGREGATES_DIR

# ----------------------------------------------------------------------
# LOGGING CONFIGURATION
# ----------------------------------------------------------------------

log = get_logger("create_aggregates")

# ----------------------------------------------------------------------
# HELPER FUNCTIONS
# ----------------------------------------------------------------------
def execute_sql_script(script_path: str, config: dict):
    """Execute a single SQL file against TimescaleDB."""
    if not os.path.exists(script_path):
        raise FileNotFoundError(f"SQL script not found: {os.path.abspath(script_path)}")

    log.info(f"▶️ Executing SQL: {os.path.basename(script_path)}")

    conn = psycopg2.connect(**config)
    conn.autocommit = True
    cur = conn.cursor()

    with open(script_path, "r") as f:
        sql_commands = f.read()

    for stmt in sqlparse.split(sql_commands):
        stmt = stmt.strip()
        if stmt:
            try:
                cur.execute(stmt)
            except Exception as e:
                log.warning(f"⚠️ Failed statement in {os.path.basename(script_path)}: {e}")

    cur.close()
    conn.close()
    log.info(f"✅ Finished: {os.path.basename(script_path)}")

    return os.path.basename(script_path)


# ----------------------------------------------------------------------
# MAIN ENTRY POINT
# ----------------------------------------------------------------------
def create_aggregate(script_name: str, **kwargs):
    """
    Execute one aggregate SQL script (for Airflow task).

    Args:
        script_name (str): File name inside schema/aggregates/
    
    Returns:
        str: Name of executed script
    """
    config = DB_CONFIG
    script_path = os.path.join(AGGREGATES_DIR, script_name)
    return execute_sql_script(script_path, config)