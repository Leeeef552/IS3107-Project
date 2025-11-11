from airflow import DAG
from airflow.operators.python import PythonOperator
from datetime import datetime, timedelta

# Import your task functions
from scripts.machine_learning_prediction.pull_data import pull_data
from scripts.machine_learning_prediction.preprocess_data import preprocess_data
from scripts.machine_learning_prediction.prepare_prediction_data import prepare_prediction_data
from scripts.machine_learning_prediction.predict import predict_with_trained_model
from scripts.machine_learning_prediction.save_predictions import save_predictions_to_db

default_args = {
    "owner": "airflow",
    "depends_on_past": False,
    "email_on_failure": False,
    "email_on_retry": False,
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
}

with DAG(
    dag_id="crypto_ml_prediction_pipeline",
    default_args=default_args,
    description="Prediction pipeline: pull latest data → preprocess → prepare inference data → predict → save results",
    schedule_interval="0 */12 * * *",
    start_date=datetime(2025, 1, 1),
    catchup=False,
    tags=["crypto", "ml", "prediction", "lstm"],
    max_active_runs=1,
) as dag:

    # 1️⃣ Pull latest data (120-day lookback)
    pull_latest_data = PythonOperator(
        task_id="pull_data",
        python_callable=pull_data,
        op_kwargs={"lookback_window": 5}, # in days, minimally as many days as training pipeline 
        provide_context=True,
    )

    # 2️⃣ Preprocess (aggregations, indicators, etc.)
    preprocess_latest_data = PythonOperator(
        task_id="preprocess_latest_data",
        python_callable=preprocess_data,
        op_kwargs={"time_bin": "2h"},  # matches training resolution
        provide_context=True,
    )

    # 3️⃣ Prepare inference data (scaling, sequencing)
    prepare_inference_data_task = PythonOperator(
        task_id="prepare_inference_data",
        python_callable=prepare_prediction_data,
        provide_context=True,
    )

    # 4️⃣ Run model predictions (no retraining)
    run_predictions_task = PythonOperator(
        task_id="run_predictions",
        python_callable=predict_with_trained_model,
        provide_context=True,
    )

    # 5️⃣ Save predictions (to Postgres table)
    save_predictions_task = PythonOperator(
        task_id="save_predictions",
        python_callable=save_predictions_to_db,
        provide_context=True,
    )

    # ----------------------------------------------------------------------
    # Task Dependencies
    # ----------------------------------------------------------------------
    (
        pull_latest_data
        >> preprocess_latest_data
        >> prepare_inference_data_task
        >> run_predictions_task
        >> save_predictions_task
    )
