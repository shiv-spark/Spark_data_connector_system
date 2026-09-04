"""
Generates the Airflow DAG file for a scheduled reverse-ETL pipeline.

Deliberately much simpler than utils/dag_generator.py (forward ingestion),
which also handles file hashing/dedup/processed-failed folders — none of
that applies here since the source is always the warehouse Postgres and
there's no file to dedup. Each generated DAG has exactly one PythonOperator
that calls back into this same backend's /reverse_etl/pipelines/{name}/run
endpoint on its cron schedule, the same "DAG calls backend over HTTP"
pattern utils/dag_static_body.py already uses for forward pipelines.
"""

import os
import re

DAGS_FOLDER = os.path.normpath(os.getenv("DAGS_FOLDER", "/app/dags"))
BACKEND_BASE_URL = os.getenv("REVERSE_ETL_BACKEND_URL", "http://backend:8000")


def _safe_id(name: str) -> str:
    name = (name or "").lower().strip()
    name = re.sub(r"[^a-z0-9_]", "_", name)
    name = re.sub(r"_+", "_", name).strip("_")
    return name or "reverse_pipeline"


def _dag_filename(pipeline_id: str) -> str:
    return f"reverse_etl_{pipeline_id}.py"


def _render_template(pipeline_name: str, dag_id: str, schedule: str, timezone: str) -> str:
    # NOTE: PIPELINE_NAME below must be the *raw* name exactly as stored in
    # reverse_etl_pipelines (pipeline_name column) — the DAG calls
    # /reverse_etl/pipelines/{PIPELINE_NAME}/run, and get_pipeline() looks up
    # that exact string. dag_id is separately sanitized (Airflow dag_ids
    # can't contain spaces/special chars), so the two must NOT be conflated —
    # doing so silently breaks every scheduled run for any pipeline_name that
    # needed sanitizing (spaces, uppercase, punctuation, etc.).
    escaped_name = pipeline_name.replace('"', '\\"')
    return f'''
from airflow import DAG
from airflow.operators.python import PythonOperator
import pendulum
import requests

# AUTO-GENERATED — reverse ETL pipeline: {pipeline_name}
# Do not manually edit. Use POST /reverse_etl/pipelines to regenerate.

PIPELINE_NAME = "{escaped_name}"
BACKEND_BASE_URL = "{BACKEND_BASE_URL}"
SCHEDULE = "{schedule}"
TIMEZONE = "{timezone}"


def run_reverse_sync():
    res = requests.post(
        f"{{BACKEND_BASE_URL}}/reverse_etl/pipelines/{{PIPELINE_NAME}}/run",
        timeout=300,
    )
    print(f"Reverse ETL run response [{{res.status_code}}]: {{res.text[:500]}}")
    if res.status_code >= 400:
        raise Exception(f"Reverse ETL sync failed: {{res.status_code}} {{res.text[:300]}}")
    body = res.json()
    if body.get("status") == "FAILED":
        raise Exception(f"Reverse ETL sync failed: {{body.get('error')}}")


with DAG(
    dag_id            = "reverse_etl_{dag_id}",
    start_date        = pendulum.datetime(2024, 1, 1, tz=TIMEZONE),
    schedule_interval = SCHEDULE,
    catchup           = False,
    max_active_runs   = 1,
    tags              = ["reverse_etl"],
) as dag:
    PythonOperator(
        task_id         = "run_reverse_sync",
        python_callable = run_reverse_sync,
    )
'''


def create_reverse_dag_file(pipeline_name: str, schedule: str, timezone: str = "Asia/Kolkata") -> dict:
    dag_id = _safe_id(pipeline_name)
    file_path = os.path.join(DAGS_FOLDER, _dag_filename(dag_id))
    os.makedirs(DAGS_FOLDER, exist_ok=True)
    content = _render_template(pipeline_name, dag_id, schedule, timezone)
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(content)
    return {"status": "SUCCESS", "dag_id": f"reverse_etl_{dag_id}", "file_path": file_path}


def delete_reverse_dag_file(pipeline_name: str) -> dict:
    pipeline_id = _safe_id(pipeline_name)
    file_path = os.path.join(DAGS_FOLDER, _dag_filename(pipeline_id))
    if os.path.exists(file_path):
        os.remove(file_path)
        return {"status": "SUCCESS"}
    return {"status": "NOT_FOUND"}
