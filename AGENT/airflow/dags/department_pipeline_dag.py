from airflow import DAG
from airflow.operators.python import PythonOperator
from datetime import datetime
import sys
import os

sys.path.append(
    os.path.dirname(
        os.path.dirname(os.path.abspath(__file__))
    )
)
import sys
sys.path.append("/opt/airflow/agent")

from Pipeline.pipeline_executor import execute_pipeline

def run_pipeline():
    execute_pipeline(
        "Department Data ETL"
    )

with DAG(
    dag_id="department_data_etl",
    start_date=datetime(2026,1,1),
    schedule="@daily",
    catchup=False
) as dag:

    run = PythonOperator(
        task_id="run_pipeline",
        python_callable=run_pipeline
    )

