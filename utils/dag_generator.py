import os
import re
from dotenv import load_dotenv

load_dotenv()

DAGS_FOLDER = os.path.normpath(os.getenv(
    "DAGS_FOLDER",
    os.path.join(os.path.dirname(__file__), "..", "airflow", "dags")
))

WINDOWS_DATA_PATH      = os.getenv("WINDOWS_DATA_PATH",      "").replace("\\", "/")
WINDOWS_DATASET_PATH   = os.getenv("WINDOWS_DATASET_PATH",   "").replace("\\", "/")
CONTAINER_DATA_PATH    = os.getenv("CONTAINER_DATA_PATH",    "/opt/airflow/user_data")
CONTAINER_DATASET_PATH = os.getenv("CONTAINER_DATASET_PATH", "/opt/airflow/dataset")

VALID_CONNECTORS = {"csv", "excel", "google_sheets", "api", "postgres", "s3"}  
VALID_OPTIONS    = {"1", "2", "3"}


def _safe_id(name: str) -> str:
    name = name.lower().strip()
    name = re.sub(r"[^a-z0-9_]", "_", name)
    name = re.sub(r"_+", "_", name).strip("_")
    return name or "pipeline"


def _clean(val):
    if not val or str(val).strip().lower() in ("string", "null", "none", ""):
        return None
    return val


def _fix_path(val):
    if val is None:
        return None
    val = val.strip().strip('"').strip("'")
    return val.replace("\\", "\\\\")


def validate_pipeline_config(config: dict) -> list:
    config["folder_path"]     = _clean(config.get("folder_path"))
    config["file_path"]       = _clean(config.get("file_path"))
    config["api_url"]         = _clean(config.get("api_url"))
    config["sheet_url"]       = _clean(config.get("sheet_url"))
    config["after_first_run"] = _clean(config.get("after_first_run"))

    errors = []
    if not config.get("pipeline_name"):
        errors.append("pipeline_name required.")

    ct = config.get("connector_type", "")
    if ct not in VALID_CONNECTORS:
        errors.append(f"connector_type '{ct}' invalid. Valid: {VALID_CONNECTORS}")

    if ct in ("csv", "excel"):
        if not config.get("folder_path") and not config.get("file_path"):
            errors.append("csv/excel: folder_path or file_path required.")

    if ct == "google_sheets" and not config.get("sheet_url"):
        errors.append("google_sheets: sheet_url required.")

    if ct == "api" and not config.get("api_url"):
        errors.append("api: api_url required.")

    # ── Incremental validation ───────────────────────────
    sync_mode = config.get("sync_mode", "full")
    if sync_mode not in ("full", "incremental"):
        errors.append("sync_mode 'full' will be 'incremental' only.")

    if sync_mode == "incremental" and not config.get("incremental_column"):
        errors.append("incremental: incremental_column required — e.g. 'updated_at' or 'id'")
    # ────────────────────────────────────────────────────

    # ── Postgres validation ──────────────────────────────
    if ct == "postgres":
        if not config.get("src_pg_host"):
            errors.append("postgres: src_pg_host required.")
        if not config.get("src_pg_db"):
            errors.append("postgres: src_pg_db required.")
        if not config.get("src_pg_user"):
            errors.append("postgres: src_pg_user required.")
        if not config.get("src_pg_password"):
            errors.append("postgres: src_pg_password required.")
        if not config.get("pg_query"):
            errors.append("postgres: pg_query required.")
    # ────────────────────────────────────────────────────

    # ── S3 validation ────────────────────────────────────
    if ct == "s3":
        if not config.get("s3_bucket"):
            errors.append("s3: s3_bucket required.")
        if not config.get("s3_key"):
            errors.append("s3: s3_key required.")
    # ────────────────────────────────────────────────────

    if config.get("option", "1") not in VALID_OPTIONS:
        errors.append("option '1' (append), '2' (overwrite), or '3' (create new) required.")

    afr = config.get("after_first_run")
    if afr and afr not in ("1", "2"):
        errors.append("after_first_run '1' or '2' required.")

    if config.get("option") == "3" and not afr:
        errors.append("option '3': after_first_run required — '1' or '2'.")

    if not config.get("table_name"):
        errors.append("table_name required.")

    return errors


def _render_template(cfg: dict) -> str:
    pipeline_id     = _safe_id(cfg["pipeline_name"])
    connector_type  = cfg["connector_type"]
    option          = cfg.get("option", "1")
    after_first_run = cfg.get("after_first_run") or None
    table_name      = cfg["table_name"]
    schedule        = cfg.get("schedule", "*/5 * * * *")
    folder_path     = _fix_path(cfg.get("folder_path") or None)
    file_path       = _fix_path(cfg.get("file_path") or None)
    sheet_url       = cfg.get("sheet_url") or None
    api_url         = cfg.get("api_url") or None

    # ── Incremental variables ────────────────────────────
    sync_mode          = cfg.get("sync_mode")          or "full"
    incremental_column = cfg.get("incremental_column") or None
    # ────────────────────────────────────────────────────

    # ── Postgres variables ───────────────────────────────
    src_pg_host     = cfg.get("src_pg_host")     or None
    src_pg_db       = cfg.get("src_pg_db")       or None
    src_pg_user     = cfg.get("src_pg_user")     or None
    src_pg_password = cfg.get("src_pg_password") or None
    src_pg_port     = cfg.get("src_pg_port")     or "5432"
    pg_query        = cfg.get("pg_query")        or None
    # ────────────────────────────────────────────────────

    # ── S3 variables ─────────────────────────────────────
    s3_bucket    = cfg.get("s3_bucket")    or None
    s3_key       = cfg.get("s3_key")       or None
    s3_file_type = cfg.get("s3_file_type") or "csv"
    # ────────────────────────────────────────────────────

    def q(val):
        if val is None:
            return "None"
        # double quotes and backslash escape
        safe = str(val).replace("\\", "\\\\").replace('"', '\\"')
        return f'"{safe}"'

    header_lines = [
        "from airflow import DAG",
        "from airflow.operators.python import PythonOperator",
        "from datetime import datetime",
        "import os, json, requests, shutil",
        "",
        f"# AUTO-GENERATED — pipeline: {pipeline_id}",
        f"# Do not manually edit. Use /create_pipeline endpoint to regenerate.",
        "",
        f'PIPELINE_ID     = "pipeline_{pipeline_id}"',
        f'CONNECTOR_TYPE  = "{connector_type}"',
        f"FOLDER_PATH     = {q(folder_path)}",
        f"FILE_PATH       = {q(file_path)}",
        f"SHEET_URL       = {q(sheet_url)}",
        f"API_URL         = {q(api_url)}",
        # ── Incremental ──────────────────────────────────
        f'SYNC_MODE          = "{sync_mode}"',
        f"INCREMENTAL_COLUMN = {q(incremental_column)}",
        # ────────────────────────────────────────────────
        # ── Postgres ────────────────────────────────────
        f"SRC_PG_HOST     = {q(src_pg_host)}",
        f"SRC_PG_DB       = {q(src_pg_db)}",
        f"SRC_PG_USER     = {q(src_pg_user)}",
        f"SRC_PG_PASSWORD = {q(src_pg_password)}",
        f'SRC_PG_PORT     = "{src_pg_port}"',
        f"PG_QUERY        = {q(pg_query)}",
        # ── S3 ──────────────────────────────────────────
        f"S3_BUCKET       = {q(s3_bucket)}",
        f"S3_KEY          = {q(s3_key)}",
        f'S3_FILE_TYPE    = "{s3_file_type}"',
        # ────────────────────────────────────────────────
        f'OPTION          = "{option}"',
        f"AFTER_FIRST_RUN = {q(after_first_run)}",
        f'TABLE_NAME      = "{table_name}"',
        f'SCHEDULE        = "{schedule}"',
        "",
        'BASE_URL              = "http://app:8000"',
        f'CONTAINER_PATH        = "{CONTAINER_DATA_PATH}"',
        f'WINDOWS_PATH          = "{WINDOWS_DATA_PATH}"',
        f'DATASET_BASE_WIN      = "{WINDOWS_DATASET_PATH}"',
        f'DATASET_BASE_CON      = "{CONTAINER_DATASET_PATH}"',
        f'DATASET_PIPELINE_CON  = "{CONTAINER_DATASET_PATH}/pipeline_{pipeline_id}"',
        f'PIPELINE_CON_ROOT     = "{CONTAINER_DATA_PATH}/pipeline_{pipeline_id}"',
        "",
        "CONNECTOR_ENDPOINT = {",
        '    "csv":           "ingest_csv",',
        '    "excel":         "ingest_excel",',
        '    "google_sheets": "ingest_google_sheet",',
        '    "api":           "ingest_api",',
        '    "postgres":      "ingest_postgres",',
        '    "s3":            "ingest_s3",',          # ← added
        "}",
    ]

    static_body = open(
        os.path.join(os.path.dirname(__file__), "dag_static_body.py"),
        encoding="utf-8"
    ).read()

    dag_block = """

with DAG(
    dag_id            = PIPELINE_ID,
    start_date        = datetime(2024, 1, 1),
    schedule_interval = SCHEDULE,
    catchup           = False,
    tags              = ["connector", CONNECTOR_TYPE],
) as dag:
    PythonOperator(
        task_id         = "run_connector",
        python_callable = run_connector,
    )
"""
    return "\n".join(header_lines) + "\n" + static_body + dag_block


def create_dag_file(config: dict) -> dict:
    errors = validate_pipeline_config(config)
    if errors:
        return {"status": "FAILED", "errors": errors}

    pipeline_id = _safe_id(config["pipeline_name"])
    filename    = f"pipeline_{pipeline_id}.py"
    file_path   = os.path.join(DAGS_FOLDER, filename)

    if os.path.exists(file_path):
        return {
            "status": "FAILED",
            "error":  f"Pipeline '{pipeline_id}' already exists. Delete it first or rename."
        }

    content = _render_template({**config, "pipeline_name": pipeline_id})

    os.makedirs(DAGS_FOLDER, exist_ok=True)
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(content)

    return {
        "status":    "SUCCESS",
        "dag_id":    f"pipeline_{pipeline_id}",
        "file_path": file_path,
        "message":   "DAG file created. Airflow will pick it up in ~30 sec."
    }


def delete_dag_file(pipeline_name: str) -> dict:
    pipeline_id = _safe_id(pipeline_name)
    file_path   = os.path.join(DAGS_FOLDER, f"pipeline_{pipeline_id}.py")

    if not os.path.exists(file_path):
        return {"status": "FAILED", "error": f"Pipeline '{pipeline_id}' not found."}

    os.remove(file_path)
    return {"status": "SUCCESS", "message": f"pipeline_{pipeline_id}.py deleted."}


def list_dag_files() -> list:
    if not os.path.exists(DAGS_FOLDER):
        return []

    result = []
    for fname in sorted(os.listdir(DAGS_FOLDER)):
        if fname.startswith("pipeline_") and fname.endswith(".py"):
            fpath = os.path.join(DAGS_FOLDER, fname)
            result.append({
                "dag_id":    fname.replace(".py", ""),
                "file_name": fname,
                "size_kb":   round(os.path.getsize(fpath) / 1024, 1),
            })
    return result

def edit_dag_file(pipeline_name: str, updates: dict) -> dict:
    """
    Update specific variables in the generated DAG file for a given pipeline.
    For example, you can update schedule, table_name, folder_path, etc. without regenerating the whole DAG.
    """
    import re as _re

    pipeline_id = _safe_id(pipeline_name)
    file_path   = os.path.join(DAGS_FOLDER, f"pipeline_{pipeline_id}.py")

    if not os.path.exists(file_path):
        return {
            "status": "FAILED",
            "error":  f"Pipeline 'pipeline_{pipeline_id}' not found."
        }

    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()

    original_content = content
    changed = []

    # ── Mapping: field → DAG variable name ───────────────────────
    field_map = {
        "schedule":          "SCHEDULE",
        "option":            "OPTION",
        "table_name":        "TABLE_NAME",
        "sync_mode":         "SYNC_MODE",
        "incremental_column":"INCREMENTAL_COLUMN",
        "folder_path":       "FOLDER_PATH",
        "file_path":         "FILE_PATH",
        "sheet_url":         "SHEET_URL",
        "api_url":           "API_URL",
        "after_first_run":   "AFTER_FIRST_RUN",
        # Postgres
        "src_pg_host":       "SRC_PG_HOST",
        "src_pg_db":         "SRC_PG_DB",
        "src_pg_user":       "SRC_PG_USER",
        "src_pg_password":   "SRC_PG_PASSWORD",
        "src_pg_port":       "SRC_PG_PORT",
        "pg_query":          "PG_QUERY",
        # S3
        "s3_bucket":         "S3_BUCKET",
        "s3_key":            "S3_KEY",
        "s3_file_type":      "S3_FILE_TYPE",
    }

    for field, new_val in updates.items():
        var = field_map.get(field)
        if not var:
            continue  # unknown field — skip

        if new_val is None or str(new_val).strip() == "":
            # None value → set to None in DAG
            pattern     = rf'^({var}\s*=\s*).*$'
            replacement = rf'\g<1>None'
        else:
            # String value → quoted
            safe_val    = str(new_val).replace("\\", "\\\\").replace('"', '\\"')
            pattern     = rf'^({var}\s*=\s*).*$'
            replacement = rf'\g<1>"{safe_val}"'

        new_content = _re.sub(pattern, replacement, content, flags=_re.MULTILINE)

        if new_content != content:
            changed.append(f"{var} → {new_val!r}")
            content = new_content

    if not changed:
        return {
            "status":  "NO_CHANGE",
            "message": "No matching variables found or values already same.",
            "pipeline": f"pipeline_{pipeline_id}",
        }

    # ── Write updated content ─────────────────────────────────────
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(content)

    return {
        "status":   "SUCCESS",
        "pipeline": f"pipeline_{pipeline_id}",
        "changed":  changed,
        "message":  f"{len(changed)} variable(s) updated. Airflow will reload in ~30s.",
    }
