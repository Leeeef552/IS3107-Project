from datetime import datetime
import os
from airflow import DAG
from airflow.operators.python import PythonOperator

from scripts.price.init_historical_price import init_historical_price
from scripts.price.backfill_price import backfill_price
from scripts.price.load_price import load_price
from scripts.price.create_aggregates import create_aggregate
from configs.config import AGGREGATES_DIR

# ----------------------------------------------------------------------
# DAG CONFIG
# ----------------------------------------------------------------------
default_args = {
    "owner": "airflow",
    "depends_on_past": False,
    "retries": 0,
}

with DAG(
    dag_id="price_pipeline_dag",
    description="Full crypto price ETL and aggregation pipeline",
    default_args=default_args,
    start_date=datetime(2025, 10, 23),
    catchup=False,
    tags=["price", "etl", "crypto"],
) as dag:

    # ------------------------------------------------------------------
    # Step 1: Initialize historical data
    # ------------------------------------------------------------------
    init_task = PythonOperator(
        task_id="init_historical",
        python_callable=init_historical_price,
    )

    # ------------------------------------------------------------------
    # Step 2: Backfill missing data
    # ------------------------------------------------------------------
    backfill_task = PythonOperator(
        task_id="backfill_price",
        python_callable=backfill_price,
    )

    # ------------------------------------------------------------------
    # Step 3: Load into TimescaleDB
    # ------------------------------------------------------------------
    load_task = PythonOperator(
        task_id="load_price",
        python_callable=load_price,
    )

    # ------------------------------------------------------------------
    # Step 4: Create aggregates (parallel per script)
    # ------------------------------------------------------------------
    aggregate_tasks = []
    for script_name in os.listdir(AGGREGATES_DIR):
        if script_name.endswith(".sql"):
            t = PythonOperator(
                task_id=f"create_aggregate_{os.path.splitext(script_name)[0]}",
                python_callable=create_aggregate,
                op_kwargs={"script_name": script_name},
            )
            aggregate_tasks.append(t)

    # ------------------------------------------------------------------
    # Task dependencies
    # ------------------------------------------------------------------
    init_task >> backfill_task >> load_task >> aggregate_tasks
