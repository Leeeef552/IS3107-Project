from datetime import datetime
from airflow import DAG
from airflow.operators.python import PythonOperator

from scripts.whale_airflow.fetch_recent_blocks import fetch_recent_blocks
from scripts.whale_airflow.extract_large_transactions import extract_large_transactions
from scripts.whale_airflow.load_whale_transactions import (
    init_whaledb,
    load_whale_transactions_to_db,
)
from scripts.whale_airflow.transform_whale_sentiments import transform_whale_sentiments

# ----------------------------------------------------------------------
# DAG CONFIG
# ----------------------------------------------------------------------
default_args = {
    "owner": "airflow",
    "depends_on_past": False,
    "retries": 1,
}

with DAG(
    dag_id="init_whale_dag",
    description="ETL pipeline for whale transaction detection and sentiment transformation",
    default_args=default_args,
    schedule_interval="@once",
    start_date=datetime(2025, 1, 1),
    catchup=False,
    tags=["whale", "crypto", "blockchain"],
) as dag:

    # Step 1: Fetch recent Bitcoin blocks
    fetch = PythonOperator(
        task_id="fetch_recent_blocks",
        python_callable=fetch_recent_blocks,
        op_kwargs={"count": 5},
    )

    # Step 2: Extract large (whale/shark/dolphin) transactions from those blocks
    extract = PythonOperator(
        task_id="extract_large_transactions",
        python_callable=extract_large_transactions,
        provide_context=True,
    )

    # Step 3: Initialize whale DB schema (runs once safely)
    initdb = PythonOperator(
        task_id="init_whaledb",
        python_callable=init_whaledb,
    )

    # Step 4: Load whale transactions into TimescaleDB
    load = PythonOperator(
        task_id="load_whale_transactions_to_db",
        python_callable=load_whale_transactions_to_db,
        provide_context=True,
    )

    # Step 5: Transform and analyze whale sentiment
    transform = PythonOperator(
        task_id="transform_whale_sentiment",
        python_callable=transform_whale_sentiments,
    )

    # Define the DAG task dependencies (pipeline order)
    fetch >> extract >> initdb >> load >> transform
