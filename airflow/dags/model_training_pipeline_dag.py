# dags/crypto_ml_pipeline.py

from airflow import DAG
from airflow.operators.python import PythonOperator
from datetime import datetime, timedelta

# Import your actual functions
from scripts.machine_learning_training.pull_data import pull_data
from scripts.machine_learning_training.preprocess_data import preprocess_data
from scripts.machine_learning_training.prepare_training_data import prepare_training_data
from scripts.machine_learning_training.training import train_model_task
from scripts.machine_learning_training.evaluation import evaluate_model_task

default_args = {
    "owner": "airflow",
    "depends_on_past": False,
    "email_on_failure": False,
    "email_on_retry": False,
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
}

with DAG(
    dag_id="crypto_ml_training_pipeline",
    default_args=default_args,
    description="End-to-end crypto ML pipeline: data extraction → preprocessing → training data preparation → model training",
    schedule_interval="@daily",
    start_date=datetime(2025, 1, 1),
    catchup=False,
    tags=["crypto", "ml", "lstm", "pipeline"],
    max_active_runs=1,
) as dag:

    # Task 1: Extract raw data from PostgreSQL
    extract_raw_data = PythonOperator(
        task_id="extract_raw_data",
        python_callable=pull_data,
        provide_context=True,
    )

    # Task 2: Preprocess and feature engineer datasets
    preprocess_data_task = PythonOperator(
        task_id="preprocess_data",
        python_callable=preprocess_data,
        op_kwargs={
            "time_bin": "2h",  # Resample frequency for time-series aggregation
        },
        provide_context=True,
    )

    # Task 3: Prepare training sequences and save artifacts
    prepare_training_data_task = PythonOperator(
        task_id="prepare_training_data",
        python_callable=prepare_training_data,
        op_kwargs={
            "lookback_window": 60,      # 30 timesteps lookback (~5 days at 4h intervals)
            "forecast_horizon": 6,      # Predict 12 steps ahead (1 day)
            "test_size": 0.2,            # 20% test split
            "predict_returns": True,     # Predict percentage returns instead of absolute prices
        },
        provide_context=True,
    )

    # Task 4: Train LSTM model
    train_model_task_op = PythonOperator(
        task_id="train_model",
        python_callable=train_model_task,
        op_kwargs={
            "num_epochs": 100,           # Max training epochs
            "learning_rate": 0.0005,     # Optimizer learning rate
            "weight_decay": 1e-5,        # L2 regularization
            "batch_size": 64,            # Training batch size
        },
        provide_context=True,
    )

    # Task 5: Evaluate
    evaluate_model_task_op = PythonOperator(
        task_id="evaluate_model",
        python_callable=evaluate_model_task,
        op_kwargs={
            "batch_size": 64,
            "generate_plots": True,  # Always generate plots for evaluation
        },
        provide_context=True,
    )

    # Updated dependencies with evaluation task
    (
        extract_raw_data
        >> preprocess_data_task
        >> prepare_training_data_task
        >> train_model_task_op
        >> evaluate_model_task_op 
    )