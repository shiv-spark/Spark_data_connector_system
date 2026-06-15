# import os


# DAGS_FOLDER = "airflow/dags"


# def generate_airflow_dag(spec):

#     pipeline_name = spec["pipeline_name"]

#     dag_id = (
#         pipeline_name
#         .lower()
#         .replace(" ", "_")
#     )

#     schedule = spec["schedule"]

#     dag_code = f'''
# from airflow import DAG
# from airflow.operators.python import PythonOperator
# from datetime import datetime

# import sys
# sys.path.append("/opt/airflow/agent")

# from Pipeline.pipeline_executor import execute_pipeline


# def run_pipeline():
#     execute_pipeline("{pipeline_name}")


# with DAG(
#     dag_id="{dag_id}",
#     start_date=datetime(2026,1,1),
#     schedule="{schedule}",
#     catchup=False
# ) as dag:

#     run_pipeline_task = PythonOperator(
#         task_id="run_pipeline",
#         python_callable=run_pipeline
#     )
# '''

#     os.makedirs(
#         DAGS_FOLDER,
#         exist_ok=True
#     )

#     filename = f"{dag_id}.py"

#     filepath = os.path.join(
#         DAGS_FOLDER,
#         filename
#     )

#     with open(
#         filepath,
#         "w"
#     ) as f:

#         f.write(dag_code)

#     print(
#         f"✓ DAG Generated: {filepath}"
#     )

#     return filepath

import os

DAGS_FOLDER = "airflow/dags"


def generate_airflow_dag(spec):

    pipeline_name = spec["pipeline_name"]

    dag_id = (
        pipeline_name
        .lower()
        .replace(" ", "_")
    )

    schedule = spec.get(
        "schedule",
        "@daily"
    )

    dag_code = f"""
from airflow import DAG
from airflow.operators.python import PythonOperator
from datetime import datetime

import sys
sys.path.append("/opt/airflow/agent")

from Pipeline.pipeline_executor import execute_pipeline


def run_pipeline():
    execute_pipeline("{pipeline_name}")


with DAG(
    dag_id="{dag_id}",
    start_date=datetime(2026, 1, 1),
    schedule="{schedule}",
    catchup=False,
    tags=["ai-pipeline"]
) as dag:

    run_pipeline_task = PythonOperator(
        task_id="run_pipeline",
        python_callable=run_pipeline
    )
"""

    os.makedirs(
        DAGS_FOLDER,
        exist_ok=True
    )

    filepath = os.path.join(
        DAGS_FOLDER,
        f"{dag_id}.py"
    )

    with open(
        filepath,
        "w",
        encoding="utf-8"
    ) as f:
        f.write(dag_code)

    print(
        f"✓ DAG Generated: {filepath}"
    )

    return filepath