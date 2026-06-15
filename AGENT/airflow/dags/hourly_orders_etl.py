
from airflow import DAG
from airflow.operators.python import PythonOperator
from datetime import datetime

import sys
sys.path.append("/opt/airflow/agent")

from Pipeline.pipeline_executor import execute_pipeline


def run_pipeline():
    execute_pipeline("Hourly Orders ETL")


with DAG(
    dag_id="hourly_orders_etl",
    start_date=datetime(2026,1,1),
    schedule="0 * * * *",
    catchup=False
) as dag:

    run_pipeline_task = PythonOperator(
        task_id="run_pipeline",
        python_callable=run_pipeline
    )
