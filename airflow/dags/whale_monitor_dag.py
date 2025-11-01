from datetime import datetime
from airflow import DAG
from airflow.operators.python import PythonOperator

from scripts.whale_airflow.fetch_recent_blocks import fetch_recent_blocks
from scripts.whale_airflow.extract_large_transactions import extract_large_transactions
from scripts.whale_airflow.load_whale_transactions import load_whale_transactions_to_db
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
    dag_id="whale_monitor_dag",
    description="Real-time monitoring DAG that fetches and processes the latest whale transactions every 10 minutes",
    default_args=default_args,
    schedule_interval="*/10 * * * *",
    start_date=datetime(2025, 1, 1),
    catchup=False,
    tags=["whale", "crypto", "blockchain"],
) as dag:

    fetch = PythonOperator(
        task_id="fetch_latest_block",
        python_callable=fetch_recent_blocks,
        op_kwargs={"count": 1},
    )

    extract = PythonOperator(
        task_id="extract_latest_whales",
        python_callable=extract_large_transactions,
    )

    load = PythonOperator(
        task_id="load_latest_whales_to_db",
        python_callable=load_whale_transactions_to_db,
    )

    transform = PythonOperator(
        task_id="update_sentiment",
        python_callable=transform_whale_sentiments,
    )

    fetch >> extract >> load >> transform