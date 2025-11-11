"""
Airflow DAG for loading news sentiment data into TimescaleDB
"""

from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator
from scripts.news_sentiment.load_sentiment import load_sentiment
from scripts.news_sentiment.update_sentiment import backfill_sentiment

default_args = {
    'owner': 'airflow',
    'depends_on_past': False,
    'retries': 1,
    'retry_delay': timedelta(minutes=5),
}

with DAG(
    'news_init_dag',
    default_args=default_args,
    description='Load news sentiment data into TimescaleDB',
    schedule_interval='@once',
    start_date=datetime(2025, 1, 1),
    catchup=False,
    tags=['crypto', 'm'],
) as dag:

    load_sentiment_task = PythonOperator(
        task_id='initialize_sentiment_database',
        python_callable=load_sentiment,
        provide_context=True,
    )

    backfill_task = PythonOperator(
        task_id='backfill_historical_sentiment',
        python_callable=backfill_sentiment,
        op_kwargs={'days': 180},  # You can adjust this or make it configurable
        provide_context=True,
    )

    # Set dependency: backfill runs AFTER the main load
    load_sentiment_task >> backfill_task