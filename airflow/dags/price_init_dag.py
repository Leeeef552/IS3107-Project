from datetime import datetime, timedelta
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
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
}

with DAG(
    dag_id="price_init_dag",
    description="Full crypto price ETL and aggregation pipeline",
    default_args=default_args,
    schedule_interval='@once',
    start_date=datetime(2025, 1, 1),
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
        execution_timeout=timedelta(hours=2),  # Set 2 hour timeout to prevent zombie tasks
    )

    # ------------------------------------------------------------------
    # Step 3: Load into TimescaleDB
    # ------------------------------------------------------------------
    load_task = PythonOperator(
        task_id="load_price",
        python_callable=load_price,
        execution_timeout=timedelta(hours=3),  # Set 3 hour timeout for large data load
    )

    # ------------------------------------------------------------------
    # Step 4: Create aggregates (run sequentially)
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
    init_task >> backfill_task >> load_task

    # Chain aggregate tasks sequentially
    if aggregate_tasks:
        load_task >> aggregate_tasks[0]
        for i in range(len(aggregate_tasks) - 1):
            aggregate_tasks[i] >> aggregate_tasks[i + 1]

