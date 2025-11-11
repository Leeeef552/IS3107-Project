from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator
from scripts.fng.init_fng import load_fng

default_args = {
    'owner': 'airflow',
    'depends_on_past': False,
    'email_on_failure': False,
    'retries': 1,
    'retry_delay': timedelta(minutes=5),
}

with DAG(
    'fng_init_dag',
    default_args=default_args,
    description='One-time load of 1-year Fear & Greed Index',
    schedule_interval='@once',
    start_date=datetime(2025, 1, 1),
    catchup=False,
    tags=['fng', 'init', "crypto"],
) as dag:

    PythonOperator(
        task_id='load_fng_historical',
        python_callable=load_fng,
        op_kwargs={'days': 730},
    )