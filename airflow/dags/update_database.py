from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator

# Import your existing scripts
from scripts.price_airflow.update_price import update_price
from scripts.news_sentiment_airflow.update_sentiment import update_sentiment_pipeline

# ---------------------------------------------------------------------
# DEFAULT DAG SETTINGS
# ---------------------------------------------------------------------
default_args = {
    "owner": "airflow",
    "depends_on_past": False,
    "email_on_failure": True,
    "email_on_retry": False,
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
}

# ---------------------------------------------------------------------
# DAG DEFINITION
# ---------------------------------------------------------------------
with DAG(
    dag_id="update_database_dag",
    description="Update Binance price data and news sentiment data",
    default_args=default_args,
    schedule_interval="0 * * * *",
    start_date=datetime(2025, 1, 1),
    catchup=False,
    max_active_runs=1,
    tags=["price", "sentiment", "crypto"],
) as dag:

    # -----------------------------------------------------------------
    # TASK 1: Update historical price data
    # -----------------------------------------------------------------
    update_price_task = PythonOperator(
        task_id="update_price",
        python_callable=update_price, # will check 1-day lookback worth of price, run every hour 
        op_kwargs={"symbol": "BTCUSDT"},
    )

    # -----------------------------------------------------------------
    # TASK 2: Update sentiment data
    # -----------------------------------------------------------------
    update_sentiment_task = PythonOperator(
        task_id="update_sentiment",
        python_callable=update_sentiment_pipeline,
        op_kwargs={"hours_back": 2, "skip_refresh": False}, # add additional hour look back for buffer
    )

    # -----------------------------------------------------------------
    # TASK DEPENDENCIES
    # -----------------------------------------------------------------
    update_price_task >> update_sentiment_task
