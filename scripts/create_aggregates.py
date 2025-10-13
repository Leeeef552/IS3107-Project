import os
import psycopg2
import sqlparse
from dotenv import load_dotenv
from concurrent.futures import ThreadPoolExecutor, as_completed
from utils.logger import get_logger

# ----------------------------------------------------------------------
# ✅ Logger setup
# ----------------------------------------------------------------------
log = get_logger("create_aggregates")

# ----------------------------------------------------------------------
# ✅ Load DB config
# ----------------------------------------------------------------------
def get_db_config():
    """Load TimescaleDB configuration from environment variables."""
    load_dotenv()
    return {
        "host": os.getenv("TIMESCALE_HOST", "localhost"),
        "port": int(os.getenv("TIMESCALE_PORT", 5432)),
        "user": os.getenv("TIMESCALE_USER"),
        "password": os.getenv("TIMESCALE_PASSWORD"),
        "dbname": os.getenv("TIMESCALE_DBNAME", "postgres"),
    }

# ----------------------------------------------------------------------
# ✅ Execute a single SQL script
# ----------------------------------------------------------------------
def execute_sql_script(script_path: str, config: dict):
    """Execute a single SQL file against the TimescaleDB database."""
    log.info(f"▶️ Executing {os.path.basename(script_path)}")

    if not os.path.exists(script_path):
        log.error(f"❌ File not found: {os.path.abspath(script_path)}")
        return

    try:
        with open(script_path, "r") as f:
            sql_commands = f.read()

        conn = psycopg2.connect(**config)
        conn.autocommit = True
        cur = conn.cursor()

        for stmt in sqlparse.split(sql_commands):
            stmt = stmt.strip()
            if stmt:
                try:
                    cur.execute(stmt)
                except Exception as e:
                    log.warning(f"⚠️ Failed statement in {os.path.basename(script_path)}: {e}")

        cur.close()
        conn.close()
        log.info(f"✅ Finished {os.path.basename(script_path)}")

    except Exception as e:
        log.error(f"❌ Error executing {script_path}: {e}")

# ----------------------------------------------------------------------
# ✅ Main orchestrator
# ----------------------------------------------------------------------
def main():
    log.info("=== Creating Continuous Aggregates Started ===")

    # Load DB credentials
    config = get_db_config()

    # Path to folder with split SQL scripts
    sql_dir = "schema/aggregates"

    # Detect all .sql files
    sql_files = [
        os.path.join(sql_dir, f)
        for f in sorted(os.listdir(sql_dir))
        if f.endswith(".sql")
    ]

    if not sql_files:
        log.error("❌ No SQL files found in schema/aggregates.")
        return

    # Run in parallel for speed (limit concurrency to avoid DB overload)
    max_workers = min(4, len(sql_files))
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(execute_sql_script, f, config): f for f in sql_files}

        for future in as_completed(futures):
            script = futures[future]
            try:
                future.result()
            except Exception as e:
                log.error(f"❌ {os.path.basename(script)} failed: {e}")

    log.info("=== Creating Continuous Aggregates Finished ===")


# ----------------------------------------------------------------------
# ✅ Airflow-friendly entry point
# ----------------------------------------------------------------------
if __name__ == "__main__":
    main()
