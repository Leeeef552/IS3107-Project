from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator
from scripts.fng_airflow.update_fng import update_fng_daily

default_args = {
    'owner': 'airflow',
    'depends_on_past': False,
    'email_on_failure': False,
    'retries': 1,
    'retry_delay': timedelta(minutes=5),
}

with DAG(
    'batch_update_fng_dag',
    default_args=default_args,
    description='Daily Fear & Greed Index update',
    schedule_interval='@daily',
    start_date=datetime(2025, 1, 1),
    catchup=False,
    tags=['fng', 'daily', "crypto"],
) as dag:

    PythonOperator(
        task_id='update_fng_daily',
        python_callable=update_fng_daily,
        op_kwargs={'days': 7},
    )