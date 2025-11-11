from datetime import datetime
from airflow import DAG
from airflow.operators.python import PythonOperator

from scripts.whale.fetch_recent_blocks import fetch_recent_blocks
from scripts.whale.extract_large_transactions import extract_large_transactions
from scripts.whale.load_whale_transactions import (
    init_whaledb,
    load_whale_transactions_to_db,
)
from scripts.whale.transform_whale_sentiments import transform_whale_sentiments

# ----------------------------------------------------------------------
# DAG CONFIG
# ----------------------------------------------------------------------
default_args = {
    "owner": "airflow",
    "depends_on_past": False,
    "retries": 1,
}

with DAG(
    dag_id="whale_init_dag",
    description="ETL pipeline for whale transaction detection and sentiment transformation (init run)",
    default_args=default_args,
    schedule_interval="@once",
    start_date=datetime(2025, 1, 1),
    catchup=False,
    tags=["whale", "crypto", "blockchain"],
) as dag:

    fetch = PythonOperator(
        task_id="fetch_recent_blocks",
        python_callable=fetch_recent_blocks,
        op_kwargs={"count": 10},
        provide_context=True,
    )

    extract = PythonOperator(
        task_id="extract_large_transactions",
        python_callable=extract_large_transactions,
        provide_context=True,
    )

    initdb = PythonOperator(
        task_id="init_whaledb",
        python_callable=init_whaledb,
    )

    load = PythonOperator(
        task_id="load_whale_transactions_to_db",
        python_callable=load_whale_transactions_to_db,
        provide_context=True,
    )

    transform = PythonOperator(
        task_id="transform_whale_sentiment",
        python_callable=transform_whale_sentiments,
    )

    fetch >> extract >> initdb >> load >> transform
