import os
import re
from dotenv import load_dotenv

load_dotenv()

DAGS_FOLDER = os.path.normpath(os.getenv(
    "DAGS_FOLDER",
    os.path.join(os.path.dirname(__file__), "..", "airflow", "dags")
))


def _safe_id(name: str) -> str:
    name = name.lower().strip()
    name = re.sub(r"[^a-z0-9_]", "_", name)
    name = re.sub(r"_+", "_", name).strip("_")
    return name or "pipeline"


def create_multi_dag_file(config: dict) -> dict:
    pipeline_id = _safe_id(config["pipeline_name"])
    filename    = f"pipeline_{pipeline_id}.py"
    file_path   = os.path.join(DAGS_FOLDER, filename)

    if os.path.exists(file_path):
        return {
            "status": "FAILED",
            "error":  f"Pipeline '{pipeline_id}' already exists."
        }

    sources   = config["sources"]
    table     = config["table_name"]
    schedule  = config.get("schedule", "*/5 * * * *")
    sync_mode = config.get("sync_mode", "full")
    inc_col   = config.get("incremental_column")
    option    = config.get("option", "1")

    # ── Build payload per source ──────────────────────────────────────
    source_calls = []
    for i, src in enumerate(sources):
        ct      = src["connector_type"]
        # for first source, use the provided option. For subsequent sources, always use "1" to append data. This ensures only the first source can overwrite, while others will append.
        src_opt = option if i == 0 else "1"

        if ct == "csv":
            payload = {
                "file_path":          src.get("file_path") or src.get("folder_path"),
                "option":             src_opt,
                "table_name":         table,
                "sync_mode":          sync_mode,
                "incremental_column": inc_col,
            }
            source_calls.append(f"""
    # ── Source {i+1}: CSV ──
    res = requests.post(f"{{BASE_URL}}/ingest_csv", json={payload!r}, timeout=120)
    print(f"Source {i+1} CSV: {{res.status_code}} | {{res.text}}")
    if res.status_code != 200 or res.json().get('status') == 'FAILED':
        raise Exception(f"Source {i+1} CSV failed: {{res.text}}")
""")

        elif ct == "excel":
            payload = {
                "file_path":          src.get("file_path") or src.get("folder_path"),
                "option":             src_opt,
                "table_name":         table,
                "sync_mode":          sync_mode,
                "incremental_column": inc_col,
            }
            source_calls.append(f"""
    # ── Source {i+1}: Excel ──
    res = requests.post(f"{{BASE_URL}}/ingest_excel", json={payload!r}, timeout=120)
    print(f"Source {i+1} Excel: {{res.status_code}} | {{res.text}}")
    if res.status_code != 200 or res.json().get('status') == 'FAILED':
        raise Exception(f"Source {i+1} Excel failed: {{res.text}}")
""")

        elif ct == "google_sheets":
            payload = {
                "sheet_url":          src.get("sheet_url"),
                "option":             src_opt,
                "table_name":         table,
                "sync_mode":          sync_mode,
                "incremental_column": inc_col,
            }
            source_calls.append(f"""
    # ── Source {i+1}: Google Sheets ──
    res = requests.post(f"{{BASE_URL}}/ingest_google_sheet", json={payload!r}, timeout=120)
    print(f"Source {i+1} Sheets: {{res.status_code}} | {{res.text}}")
    if res.status_code != 200 or res.json().get('status') == 'FAILED':
        raise Exception(f"Source {i+1} Google Sheets failed: {{res.text}}")
""")

        elif ct == "api":
            payload = {
                "url":                src.get("api_url"),
                "option":             src_opt,
                "table_name":         table,
                "sync_mode":          sync_mode,
                "incremental_column": inc_col,
            }
            source_calls.append(f"""
    # ── Source {i+1}: API ──
    res = requests.post(f"{{BASE_URL}}/ingest_api", json={payload!r}, timeout=120)
    print(f"Source {i+1} API: {{res.status_code}} | {{res.text}}")
    if res.status_code != 200 or res.json().get('status') == 'FAILED':
        raise Exception(f"Source {i+1} API failed: {{res.text}}")
""")

        elif ct == "s3":
            payload = {
                "bucket":             src.get("s3_bucket"),
                "key":                src.get("s3_key"),
                "file_type":          src.get("s3_file_type", "csv"),
                "option":             src_opt,
                "table_name":         table,
                "sync_mode":          sync_mode,
                "incremental_column": inc_col,
            }
            source_calls.append(f"""
    # ── Source {i+1}: S3 ──
    res = requests.post(f"{{BASE_URL}}/ingest_s3", json={payload!r}, timeout=120)
    print(f"Source {i+1} S3: {{res.status_code}} | {{res.text}}")
    if res.status_code != 200 or res.json().get('status') == 'FAILED':
        raise Exception(f"Source {i+1} S3 failed: {{res.text}}")
""")

        elif ct == "postgres":
            payload = {
                "host":               src.get("src_pg_host"),
                "database":           src.get("src_pg_db"),
                "user":               src.get("src_pg_user"),
                "password":           src.get("src_pg_password"),
                "port":               src.get("src_pg_port", "5432"),
                "query":              src.get("pg_query"),
                "option":             src_opt,
                "table_name":         table,
                "sync_mode":          sync_mode,
                "incremental_column": inc_col,
            }
            source_calls.append(f"""
    # ── Source {i+1}: Postgres ──
    res = requests.post(f"{{BASE_URL}}/ingest_postgres", json={payload!r}, timeout=120)
    print(f"Source {i+1} Postgres: {{res.status_code}} | {{res.text}}")
    if res.status_code != 200 or res.json().get('status') == 'FAILED':
        raise Exception(f"Source {i+1} Postgres failed: {{res.text}}")
""")

    # ── Render full DAG file ──────────────────────────────────────────
    all_calls = "\n".join(source_calls)

    dag_content = f"""
from airflow import DAG
from airflow.operators.python import PythonOperator
from datetime import datetime
import requests

PIPELINE_ID = "pipeline_{pipeline_id}"
BASE_URL    = "http://host.docker.internal:8000"
TABLE_NAME  = "{table}"
SCHEDULE    = "{schedule}"


def run_multi_source(**context):
    print(f"Multi-source pipeline: {{PIPELINE_ID}}")
    print(f"Table: {{TABLE_NAME}}")
    print(f"Total sources: {len(sources)}")

    try:
{all_calls}
        print("All sources ingested successfully!")

    except Exception as e:
        print(f"Pipeline failed: {{e}}")
        raise


with DAG(
    dag_id            = PIPELINE_ID,
    start_date        = datetime(2024, 1, 1),
    schedule_interval = SCHEDULE,
    catchup           = False,
    tags              = ["multi-source", "connector"],
) as dag:
    PythonOperator(
        task_id         = "run_multi_source",
        python_callable = run_multi_source,
    )
"""

    os.makedirs(DAGS_FOLDER, exist_ok=True)
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(dag_content)

    return {
        "status":       "SUCCESS",
        "dag_id":       f"pipeline_{pipeline_id}",
        "file_path":    file_path,
        "sources_count": len(sources),
        "message":      f"{len(sources)} sources → table '{table}'. Airflow will pick up in ~30s."
    }