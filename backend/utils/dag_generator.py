# import os
# import re
# from dotenv import load_dotenv

# load_dotenv()

# # ── Paths ─────────────────────────────────────────────────────────────────────
# # Where DAG .py files are written inside the backend container.
# # Must match the dags_volume mount → /app/dags
# DAGS_FOLDER = os.path.normpath(os.getenv("DAGS_FOLDER", "/app/dags"))

# # What the USER types in the frontend (Windows path prefix).
# # e.g.  D:/DATA_ENG/Spark_data_connector_system/data
# WINDOWS_DATA_PATH    = os.getenv("WINDOWS_DATA_PATH",    "").replace("\\", "/")
# WINDOWS_DATASET_PATH = os.getenv("WINDOWS_DATASET_PATH", "").replace("\\", "/")

# # Where Airflow container sees the same folders.
# # Matches docker-compose.yml:  ./data:/opt/airflow/data
# CONTAINER_DATA_PATH    = os.getenv("CONTAINER_DATA_PATH",    "/opt/airflow/data")
# CONTAINER_DATASET_PATH = os.getenv("CONTAINER_DATASET_PATH", "/opt/airflow/dataset")

# VALID_CONNECTORS = {"csv", "excel", "google_sheets", "api", "postgres", "s3"}
# VALID_OPTIONS    = {"1", "2", "3"}


# def _safe_id(name: str) -> str:
#     name = name.lower().strip()
#     name = re.sub(r"[^a-z0-9_]", "_", name)
#     name = re.sub(r"_+", "_", name).strip("_")
#     return name or "pipeline"


# def _clean(val):
#     if not val or str(val).strip().lower() in ("string", "null", "none", ""):
#         return None
#     return val


# def _fix_path(val):
#     """Normalize path — strip quotes, convert backslashes to forward slashes."""
#     if val is None:
#         return None
#     val = val.strip().strip('"').strip("'")
#     return val.replace("\\", "/")


# def validate_pipeline_config(config: dict) -> list:
#     config["folder_path"]     = _clean(config.get("folder_path"))
#     config["file_path"]       = _clean(config.get("file_path"))
#     config["api_url"]         = _clean(config.get("api_url"))
#     config["sheet_url"]       = _clean(config.get("sheet_url"))
#     config["after_first_run"] = _clean(config.get("after_first_run"))

#     errors = []
#     if not config.get("pipeline_name"):
#         errors.append("pipeline_name required.")

#     ct = config.get("connector_type", "")
#     if ct not in VALID_CONNECTORS:
#         errors.append(f"connector_type '{ct}' invalid. Valid: {VALID_CONNECTORS}")

#     if ct in ("csv", "excel"):
#         if not config.get("folder_path") and not config.get("file_path"):
#             errors.append("csv/excel: folder_path or file_path required.")

#     if ct == "google_sheets" and not config.get("sheet_url"):
#         errors.append("google_sheets: sheet_url required.")

#     if ct == "api" and not config.get("api_url"):
#         errors.append("api: api_url required.")

#     sync_mode = config.get("sync_mode", "full")
#     if sync_mode not in ("full", "incremental"):
#         errors.append("sync_mode must be 'full' or 'incremental'.")
#     if sync_mode == "incremental" and not config.get("incremental_column"):
#         errors.append("incremental: incremental_column required — e.g. 'updated_at' or 'id'")

#     if ct == "postgres":
#         for field in ("src_pg_host", "src_pg_db", "src_pg_user", "src_pg_password", "pg_query"):
#             if not config.get(field):
#                 errors.append(f"postgres: {field} required.")

#     if ct == "s3":
#         if not config.get("s3_bucket"):
#             errors.append("s3: s3_bucket required.")
#         if not config.get("s3_key"):
#             errors.append("s3: s3_key required.")

#     if config.get("option", "1") not in VALID_OPTIONS:
#         errors.append("option '1' (append), '2' (overwrite), or '3' (create new) required.")

#     afr = config.get("after_first_run")
#     if afr and afr not in ("1", "2"):
#         errors.append("after_first_run '1' or '2' required.")
#     if config.get("option") == "3" and not afr:
#         errors.append("option '3': after_first_run required — '1' or '2'.")

#     if not config.get("table_name"):
#         errors.append("table_name required.")

#     return errors


# def _render_template(cfg: dict) -> str:
#     pipeline_id     = _safe_id(cfg["pipeline_name"])
#     connector_type  = cfg["connector_type"]
#     option          = cfg.get("option", "1")
#     after_first_run = cfg.get("after_first_run") or None
#     table_name      = cfg["table_name"]
#     schedule        = cfg.get("schedule", "*/5 * * * *")
#     timezone        = cfg.get("timezone") or "Asia/Kolkata"
#     folder_path     = _fix_path(cfg.get("folder_path") or None)
#     file_path       = _fix_path(cfg.get("file_path") or None)
#     sheet_url       = cfg.get("sheet_url") or None
#     api_url         = cfg.get("api_url") or None

#     sync_mode          = cfg.get("sync_mode")          or "full"
#     incremental_column = cfg.get("incremental_column") or None

#     src_pg_host     = cfg.get("src_pg_host")     or None
#     src_pg_db       = cfg.get("src_pg_db")       or None
#     src_pg_user     = cfg.get("src_pg_user")     or None
#     src_pg_password = cfg.get("src_pg_password") or None
#     src_pg_port     = cfg.get("src_pg_port")     or "5432"
#     pg_query        = cfg.get("pg_query")        or None

#     s3_bucket    = cfg.get("s3_bucket")    or None
#     s3_key       = cfg.get("s3_key")       or None
#     s3_file_type = cfg.get("s3_file_type") or "csv"

#     def q(val):
#         if val is None:
#             return "None"
#         safe = str(val).replace("\\", "/").replace('"', '\\"')
#         return f'"{safe}"'

#     header_lines = [
#         "from airflow import DAG",
#         "from airflow.operators.python import PythonOperator",
#         "import pendulum",
#         "import os, json, requests, shutil",
#         "",
#         f"# AUTO-GENERATED — pipeline: {pipeline_id}",
#         f"# Do not manually edit. Use /create_pipeline endpoint to regenerate.",
#         "",
#         f'PIPELINE_ID     = "pipeline_{pipeline_id}"',
#         f'CONNECTOR_TYPE  = "{connector_type}"',
#         f"FOLDER_PATH     = {q(folder_path)}",
#         f"FILE_PATH       = {q(file_path)}",
#         f"SHEET_URL       = {q(sheet_url)}",
#         f"API_URL         = {q(api_url)}",
#         f'SYNC_MODE          = "{sync_mode}"',
#         f"INCREMENTAL_COLUMN = {q(incremental_column)}",
#         f"SRC_PG_HOST     = {q(src_pg_host)}",
#         f"SRC_PG_DB       = {q(src_pg_db)}",
#         f"SRC_PG_USER     = {q(src_pg_user)}",
#         f"SRC_PG_PASSWORD = {q(src_pg_password)}",
#         f'SRC_PG_PORT     = "{src_pg_port}"',
#         f"PG_QUERY        = {q(pg_query)}",
#         f"S3_BUCKET       = {q(s3_bucket)}",
#         f"S3_KEY          = {q(s3_key)}",
#         f'S3_FILE_TYPE    = "{s3_file_type}"',
#         f'OPTION          = "{option}"',
#         f"AFTER_FIRST_RUN = {q(after_first_run)}",
#         f'TABLE_NAME      = "{table_name}"',
#         f'SCHEDULE        = "{schedule}"',
#         f'TIMEZONE        = "{timezone}"',
#         "",
#         # ── Path translation variables injected into every generated DAG ──────
#         #
#         # BASE_URL     : backend service on the Docker network
#         # CONTAINER_PATH / DATASET_BASE_CON : Airflow container paths (for finding files)
#         # WINDOWS_PATH / DATASET_BASE_WIN   : what the user typed (Windows or /app/... paths)
#         #
#         # to_container_path() uses WINDOWS_PATH → CONTAINER_PATH to resolve the file.
#         # to_backend_path()   uses CONTAINER_PATH → /app/data   to call the ingest API.
#         'BASE_URL              = "http://backend:8000"',
#         f'CONTAINER_PATH        = "{CONTAINER_DATA_PATH}"',
#         f'DATASET_BASE_CON      = "{CONTAINER_DATASET_PATH}"',
#         f'WINDOWS_PATH          = "{WINDOWS_DATA_PATH}"',
#         f'DATASET_BASE_WIN      = "{WINDOWS_DATASET_PATH}"',
#         f'DATASET_PIPELINE_CON  = "{CONTAINER_DATASET_PATH}/pipeline_{pipeline_id}"',
#         f'PIPELINE_CON_ROOT     = "{CONTAINER_DATA_PATH}/pipeline_{pipeline_id}"',
#         "",
#         "CONNECTOR_ENDPOINT = {",
#         '    "csv":           "ingest_csv",',
#         '    "excel":         "ingest_excel",',
#         '    "google_sheets": "ingest_google_sheet",',
#         '    "api":           "ingest_api",',
#         '    "postgres":      "ingest_postgres",',
#         '    "s3":            "ingest_s3",',
#         "}",
#     ]

#     static_body = open(
#         os.path.join(os.path.dirname(__file__), "dag_static_body.py"),
#         encoding="utf-8"
#     ).read()

#     dag_block = """

# with DAG(
#     dag_id            = PIPELINE_ID,
#     start_date        = pendulum.datetime(2024, 1, 1, tz=TIMEZONE),
#     schedule_interval = SCHEDULE,
#     catchup           = False,
#     tags              = ["connector", CONNECTOR_TYPE],
# ) as dag:
#     PythonOperator(
#         task_id         = "run_connector",
#         python_callable = run_connector,
#     )
# """
#     return "\n".join(header_lines) + "\n" + static_body + dag_block


# def create_dag_file(config: dict) -> dict:
#     errors = validate_pipeline_config(config)
#     if errors:
#         return {"status": "FAILED", "errors": errors}

#     pipeline_id = _safe_id(config["pipeline_name"])
#     filename    = f"pipeline_{pipeline_id}.py"
#     file_path   = os.path.join(DAGS_FOLDER, filename)

#     if os.path.exists(file_path):
#         return {
#             "status": "FAILED",
#             "error":  f"Pipeline '{pipeline_id}' already exists. Delete it first or rename."
#         }

#     content = _render_template({**config, "pipeline_name": pipeline_id})
#     os.makedirs(DAGS_FOLDER, exist_ok=True)
#     with open(file_path, "w", encoding="utf-8") as f:
#         f.write(content)

#     return {
#         "status":    "SUCCESS",
#         "dag_id":    f"pipeline_{pipeline_id}",
#         "file_path": file_path,
#         "message":   "DAG file created. Airflow will pick it up in ~30 sec."
#     }


# def delete_dag_file(pipeline_name: str) -> dict:
#     pipeline_id = _safe_id(pipeline_name)
#     file_path   = os.path.join(DAGS_FOLDER, f"pipeline_{pipeline_id}.py")
#     if not os.path.exists(file_path):
#         return {"status": "FAILED", "error": f"Pipeline '{pipeline_id}' not found."}
#     os.remove(file_path)
#     return {"status": "SUCCESS", "message": f"pipeline_{pipeline_id}.py deleted."}


# def list_dag_files() -> list:
#     if not os.path.exists(DAGS_FOLDER):
#         return []

#     def read_var(content: str, name: str, default=None):
#         match = re.search(rf'^{name}\s*=\s*"([^"]*)"', content, re.MULTILINE)
#         return match.group(1) if match else default

#     result = []
#     for fname in sorted(os.listdir(DAGS_FOLDER)):
#         if fname.startswith("pipeline_") and fname.endswith(".py"):
#             fpath = os.path.join(DAGS_FOLDER, fname)
#             try:
#                 with open(fpath, "r", encoding="utf-8") as f:
#                     content = f.read()
#             except OSError:
#                 content = ""
#             result.append({
#                 "dag_id":    fname.replace(".py", ""),
#                 "file_name": fname,
#                 "size_kb":   round(os.path.getsize(fpath) / 1024, 1),
#                 "schedule":  read_var(content, "SCHEDULE", "*/5 * * * *"),
#                 "timezone":  read_var(content, "TIMEZONE", "Asia/Kolkata"),
#             })
#     return result


# def edit_dag_file(pipeline_name: str, updates: dict) -> dict:
#     """Update specific variables in an existing DAG file without regenerating it."""
#     import re as _re

#     pipeline_id = _safe_id(pipeline_name)
#     file_path   = os.path.join(DAGS_FOLDER, f"pipeline_{pipeline_id}.py")

#     if not os.path.exists(file_path):
#         return {"status": "FAILED", "error": f"Pipeline 'pipeline_{pipeline_id}' not found."}

#     with open(file_path, "r", encoding="utf-8") as f:
#         content = f.read()

#     changed = []

#     if "timezone" in updates and "TIMEZONE" not in content:
#         content = _re.sub(
#             r'^(SCHEDULE\s*=\s*"[^"]*")$',
#             r'\1\nTIMEZONE        = "Asia/Kolkata"',
#             content, flags=_re.MULTILINE,
#         )
#         content = content.replace("from datetime import datetime", "import pendulum")
#         content = content.replace(
#             "start_date        = datetime(2024, 1, 1)",
#             "start_date        = pendulum.datetime(2024, 1, 1, tz=TIMEZONE)"
#         )

#     field_map = {
#         "schedule":           "SCHEDULE",
#         "timezone":           "TIMEZONE",
#         "option":             "OPTION",
#         "table_name":         "TABLE_NAME",
#         "sync_mode":          "SYNC_MODE",
#         "incremental_column": "INCREMENTAL_COLUMN",
#         "folder_path":        "FOLDER_PATH",
#         "file_path":          "FILE_PATH",
#         "sheet_url":          "SHEET_URL",
#         "api_url":            "API_URL",
#         "after_first_run":    "AFTER_FIRST_RUN",
#         "src_pg_host":        "SRC_PG_HOST",
#         "src_pg_db":          "SRC_PG_DB",
#         "src_pg_user":        "SRC_PG_USER",
#         "src_pg_password":    "SRC_PG_PASSWORD",
#         "src_pg_port":        "SRC_PG_PORT",
#         "pg_query":           "PG_QUERY",
#         "s3_bucket":          "S3_BUCKET",
#         "s3_key":             "S3_KEY",
#         "s3_file_type":       "S3_FILE_TYPE",
#     }

#     for field, new_val in updates.items():
#         var = field_map.get(field)
#         if not var:
#             continue
#         if new_val is None or str(new_val).strip() == "":
#             pattern     = rf'^({var}\s*=\s*).*$'
#             replacement = rf'\g<1>None'
#         else:
#             safe_val    = str(new_val).replace("\\", "/").replace('"', '\\"')
#             pattern     = rf'^({var}\s*=\s*).*$'
#             replacement = rf'\g<1>"{safe_val}"'

#         new_content = _re.sub(pattern, replacement, content, flags=_re.MULTILINE)
#         if new_content != content:
#             changed.append(f"{var} → {new_val!r}")
#             content = new_content

#     if not changed:
#         return {
#             "status":   "NO_CHANGE",
#             "message":  "No matching variables found or values already same.",
#             "pipeline": f"pipeline_{pipeline_id}",
#         }

#     with open(file_path, "w", encoding="utf-8") as f:
#         f.write(content)

#     return {
#         "status":   "SUCCESS",
#         "pipeline": f"pipeline_{pipeline_id}",
#         "changed":  changed,
#         "message":  f"{len(changed)} variable(s) updated. Airflow will reload in ~30s.",
#     }
import os
import re
from dotenv import load_dotenv

load_dotenv()

# ── Paths ─────────────────────────────────────────────────────────────────────
# Where DAG .py files are written inside the backend container.
# Must match the dags_volume mount → /app/dags
DAGS_FOLDER = os.path.normpath(os.getenv("DAGS_FOLDER", "/app/dags"))

# What the USER types in the frontend (Windows path prefix).
# e.g.  D:/DATA_ENG/Spark_data_connector_system/data
WINDOWS_DATA_PATH    = os.getenv("WINDOWS_DATA_PATH",    "").replace("\\", "/")
WINDOWS_DATASET_PATH = os.getenv("WINDOWS_DATASET_PATH", "").replace("\\", "/")

# Where Airflow container sees the same folders.
# Matches docker-compose.yml:  ./data:/opt/airflow/data
CONTAINER_DATA_PATH    = os.getenv("CONTAINER_DATA_PATH",    "/opt/airflow/data")
CONTAINER_DATASET_PATH = os.getenv("CONTAINER_DATASET_PATH", "/opt/airflow/dataset")

VALID_CONNECTORS = {"csv", "excel", "google_sheets", "api", "postgres", "s3", "snowflake"}
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
    """Normalize path — strip quotes, convert backslashes to forward slashes."""
    if val is None:
        return None
    val = val.strip().strip('"').strip("'")
    return val.replace("\\", "/")


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

    sync_mode = config.get("sync_mode", "full")
    if sync_mode not in ("full", "incremental"):
        errors.append("sync_mode must be 'full' or 'incremental'.")
    if sync_mode == "incremental" and not config.get("incremental_column"):
        errors.append("incremental: incremental_column required — e.g. 'updated_at' or 'id'")

    if ct == "postgres":
        for field in ("src_pg_host", "src_pg_db", "src_pg_user", "src_pg_password", "pg_query"):
            if not config.get(field):
                errors.append(f"postgres: {field} required.")

    if ct == "s3":
        if not config.get("s3_bucket"):
            errors.append("s3: s3_bucket required.")
        if not config.get("s3_key"):
            errors.append("s3: s3_key required.")

    if ct == "snowflake":
        for field in ("sf_account", "sf_user", "sf_password", "sf_warehouse", "sf_database", "sf_query"):
            if not config.get(field):
                errors.append(f"snowflake: {field} required.")

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
    timezone        = cfg.get("timezone") or "Asia/Kolkata"
    folder_path     = _fix_path(cfg.get("folder_path") or None)
    file_path       = _fix_path(cfg.get("file_path") or None)
    sheet_url       = cfg.get("sheet_url") or None
    api_url         = cfg.get("api_url") or None

    sync_mode          = cfg.get("sync_mode")          or "full"
    incremental_column = cfg.get("incremental_column") or None

    src_pg_host     = cfg.get("src_pg_host")     or None
    src_pg_db       = cfg.get("src_pg_db")       or None
    src_pg_user     = cfg.get("src_pg_user")     or None
    src_pg_password = cfg.get("src_pg_password") or None
    src_pg_port     = cfg.get("src_pg_port")     or "5432"
    pg_query        = cfg.get("pg_query")        or None

    s3_bucket    = cfg.get("s3_bucket")    or None
    s3_key       = cfg.get("s3_key")       or None
    s3_file_type = cfg.get("s3_file_type") or "csv"

    sf_account   = cfg.get("sf_account")   or None
    sf_user      = cfg.get("sf_user")      or None
    sf_password  = cfg.get("sf_password")  or None
    sf_warehouse = cfg.get("sf_warehouse") or None
    sf_database  = cfg.get("sf_database")  or None
    sf_schema    = cfg.get("sf_schema")    or "PUBLIC"
    sf_role      = cfg.get("sf_role")      or None
    sf_query     = cfg.get("sf_query")     or None

    def q(val):
        if val is None:
            return "None"
        safe = str(val).replace("\\", "/").replace('"', '\\"')
        return f'"{safe}"'

    header_lines = [
        "from airflow import DAG",
        "from airflow.operators.python import PythonOperator",
        "import pendulum",
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
        f'SYNC_MODE          = "{sync_mode}"',
        f"INCREMENTAL_COLUMN = {q(incremental_column)}",
        f"SRC_PG_HOST     = {q(src_pg_host)}",
        f"SRC_PG_DB       = {q(src_pg_db)}",
        f"SRC_PG_USER     = {q(src_pg_user)}",
        f"SRC_PG_PASSWORD = {q(src_pg_password)}",
        f'SRC_PG_PORT     = "{src_pg_port}"',
        f"PG_QUERY        = {q(pg_query)}",
        f"S3_BUCKET       = {q(s3_bucket)}",
        f"S3_KEY          = {q(s3_key)}",
        f'S3_FILE_TYPE    = "{s3_file_type}"',
        f"SF_ACCOUNT      = {q(sf_account)}",
        f"SF_USER         = {q(sf_user)}",
        f"SF_PASSWORD     = {q(sf_password)}",
        f"SF_WAREHOUSE    = {q(sf_warehouse)}",
        f"SF_DATABASE     = {q(sf_database)}",
        f'SF_SCHEMA       = "{sf_schema}"',
        f"SF_ROLE         = {q(sf_role)}",
        f"SF_QUERY        = {q(sf_query)}",
        f'OPTION          = "{option}"',
        f"AFTER_FIRST_RUN = {q(after_first_run)}",
        f'TABLE_NAME      = "{table_name}"',
        f'SCHEDULE        = "{schedule}"',
        f'TIMEZONE        = "{timezone}"',
        "",
        # ── Path translation variables injected into every generated DAG ──────
        #
        # BASE_URL     : backend service on the Docker network
        # CONTAINER_PATH / DATASET_BASE_CON : Airflow container paths (for finding files)
        # WINDOWS_PATH / DATASET_BASE_WIN   : what the user typed (Windows or /app/... paths)
        #
        # to_container_path() uses WINDOWS_PATH → CONTAINER_PATH to resolve the file.
        # to_backend_path()   uses CONTAINER_PATH → /app/data   to call the ingest API.
        'BASE_URL              = "http://backend:8000"',
        f'CONTAINER_PATH        = "{CONTAINER_DATA_PATH}"',
        f'DATASET_BASE_CON      = "{CONTAINER_DATASET_PATH}"',
        f'WINDOWS_PATH          = "{WINDOWS_DATA_PATH}"',
        f'DATASET_BASE_WIN      = "{WINDOWS_DATASET_PATH}"',
        f'DATASET_PIPELINE_CON  = "{CONTAINER_DATASET_PATH}/pipeline_{pipeline_id}"',
        f'PIPELINE_CON_ROOT     = "{CONTAINER_DATA_PATH}/pipeline_{pipeline_id}"',
        "",
        "CONNECTOR_ENDPOINT = {",
        '    "csv":           "ingest_csv",',
        '    "excel":         "ingest_excel",',
        '    "google_sheets": "ingest_google_sheet",',
        '    "api":           "ingest_api",',
        '    "postgres":      "ingest_postgres",',
        '    "s3":            "ingest_s3",',
        '    "snowflake":     "ingest_snowflake",',
        "}",
    ]

    static_body = open(
        os.path.join(os.path.dirname(__file__), "dag_static_body.py"),
        encoding="utf-8"
    ).read()

    dag_block = """

with DAG(
    dag_id            = PIPELINE_ID,
    start_date        = pendulum.datetime(2024, 1, 1, tz=TIMEZONE),
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

    def read_var(content: str, name: str, default=None):
        # Matches:  NAME   = "value"   or   NAME = None
        match = re.search(rf'^{name}\s*=\s*"([^"]*)"', content, re.MULTILINE)
        if match:
            return match.group(1)
        none_match = re.search(rf'^{name}\s*=\s*None\s*$', content, re.MULTILINE)
        if none_match:
            return None
        return default

    result = []
    for fname in sorted(os.listdir(DAGS_FOLDER)):
        if fname.startswith("pipeline_") and fname.endswith(".py"):
            fpath = os.path.join(DAGS_FOLDER, fname)
            try:
                with open(fpath, "r", encoding="utf-8") as f:
                    content = f.read()
            except OSError:
                content = ""

            result.append({
                "dag_id":    fname.replace(".py", ""),
                "file_name": fname,
                "size_kb":   round(os.path.getsize(fpath) / 1024, 1),
                "schedule":  read_var(content, "SCHEDULE", "*/5 * * * *"),
                "timezone":  read_var(content, "TIMEZONE", "Asia/Kolkata"),

                # ── Core load config ─────────────────────────────────────────
                "connector_type":  read_var(content, "CONNECTOR_TYPE"),
                "table_name":      read_var(content, "TABLE_NAME"),
                "option":          read_var(content, "OPTION", "1"),
                "after_first_run": read_var(content, "AFTER_FIRST_RUN"),
                "sync_mode":           read_var(content, "SYNC_MODE", "full"),
                "incremental_column":  read_var(content, "INCREMENTAL_COLUMN"),

                # ── CSV / Excel ───────────────────────────────────────────────
                "folder_path": read_var(content, "FOLDER_PATH"),
                "file_path":   read_var(content, "FILE_PATH"),

                # ── Google Sheets / API ──────────────────────────────────────
                "sheet_url": read_var(content, "SHEET_URL"),
                "api_url":   read_var(content, "API_URL"),

                # ── Postgres ──────────────────────────────────────────────────
                "src_pg_host":     read_var(content, "SRC_PG_HOST"),
                "src_pg_db":       read_var(content, "SRC_PG_DB"),
                "src_pg_user":     read_var(content, "SRC_PG_USER"),
                # NOTE: password intentionally NOT returned — see note below
                "src_pg_port":     read_var(content, "SRC_PG_PORT", "5432"),
                "pg_query":        read_var(content, "PG_QUERY"),

                # ── S3 ────────────────────────────────────────────────────────
                "s3_bucket":    read_var(content, "S3_BUCKET"),
                "s3_key":       read_var(content, "S3_KEY"),
                "s3_file_type": read_var(content, "S3_FILE_TYPE", "csv"),

                # ── Snowflake ─────────────────────────────────────────────────
                "sf_account":   read_var(content, "SF_ACCOUNT"),
                "sf_user":      read_var(content, "SF_USER"),
                # NOTE: password intentionally NOT returned — see note below
                "sf_warehouse": read_var(content, "SF_WAREHOUSE"),
                "sf_database":  read_var(content, "SF_DATABASE"),
                "sf_schema":    read_var(content, "SF_SCHEMA", "PUBLIC"),
                "sf_role":      read_var(content, "SF_ROLE"),
                "sf_query":     read_var(content, "SF_QUERY"),

                # ── Password presence flags ───────────────────────────────────
                # Frontend shows "(unchanged)" placeholder instead of leaking
                # the real password back to the browser.
                "has_src_pg_password": read_var(content, "SRC_PG_PASSWORD") is not None,
                "has_sf_password":     read_var(content, "SF_PASSWORD") is not None,
            })
    return result
# def list_dag_files() -> list:
#     if not os.path.exists(DAGS_FOLDER):
#         return []

#     def read_var(content: str, name: str, default=None):
#         match = re.search(rf'^{name}\s*=\s*"([^"]*)"', content, re.MULTILINE)
#         return match.group(1) if match else default

#     result = []
#     for fname in sorted(os.listdir(DAGS_FOLDER)):
#         if fname.startswith("pipeline_") and fname.endswith(".py"):
#             fpath = os.path.join(DAGS_FOLDER, fname)
#             try:
#                 with open(fpath, "r", encoding="utf-8") as f:
#                     content = f.read()
#             except OSError:
#                 content = ""
#             result.append({
#                 "dag_id":    fname.replace(".py", ""),
#                 "file_name": fname,
#                 "size_kb":   round(os.path.getsize(fpath) / 1024, 1),
#                 "schedule":  read_var(content, "SCHEDULE", "*/5 * * * *"),
#                 "timezone":  read_var(content, "TIMEZONE", "Asia/Kolkata"),
#             })
#     return result


def edit_dag_file(pipeline_name: str, updates: dict) -> dict:
    """Update specific variables in an existing DAG file without regenerating it."""
    import re as _re

    pipeline_id = _safe_id(pipeline_name)
    file_path   = os.path.join(DAGS_FOLDER, f"pipeline_{pipeline_id}.py")

    if not os.path.exists(file_path):
        return {"status": "FAILED", "error": f"Pipeline 'pipeline_{pipeline_id}' not found."}

    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()

    changed = []

    if "timezone" in updates and "TIMEZONE" not in content:
        content = _re.sub(
            r'^(SCHEDULE\s*=\s*"[^"]*")$',
            r'\1\nTIMEZONE        = "Asia/Kolkata"',
            content, flags=_re.MULTILINE,
        )
        content = content.replace("from datetime import datetime", "import pendulum")
        content = content.replace(
            "start_date        = datetime(2024, 1, 1)",
            "start_date        = pendulum.datetime(2024, 1, 1, tz=TIMEZONE)"
        )

    field_map = {
        "schedule":           "SCHEDULE",
        "timezone":           "TIMEZONE",
        "option":             "OPTION",
        "table_name":         "TABLE_NAME",
        "sync_mode":          "SYNC_MODE",
        "incremental_column": "INCREMENTAL_COLUMN",
        "folder_path":        "FOLDER_PATH",
        "file_path":          "FILE_PATH",
        "sheet_url":          "SHEET_URL",
        "api_url":            "API_URL",
        "after_first_run":    "AFTER_FIRST_RUN",
        "src_pg_host":        "SRC_PG_HOST",
        "src_pg_db":          "SRC_PG_DB",
        "src_pg_user":        "SRC_PG_USER",
        "src_pg_password":    "SRC_PG_PASSWORD",
        "src_pg_port":        "SRC_PG_PORT",
        "pg_query":           "PG_QUERY",
        "s3_bucket":          "S3_BUCKET",
        "s3_key":             "S3_KEY",
        "s3_file_type":       "S3_FILE_TYPE",
        "sf_account":         "SF_ACCOUNT",
        "sf_user":            "SF_USER",
        "sf_password":        "SF_PASSWORD",
        "sf_warehouse":       "SF_WAREHOUSE",
        "sf_database":        "SF_DATABASE",
        "sf_schema":          "SF_SCHEMA",
        "sf_role":            "SF_ROLE",
        "sf_query":           "SF_QUERY",
    }

    for field, new_val in updates.items():
        var = field_map.get(field)
        if not var:
            continue
        if new_val is None or str(new_val).strip() == "":
            pattern     = rf'^({var}\s*=\s*).*$'
            replacement = rf'\g<1>None'
        else:
            safe_val    = str(new_val).replace("\\", "/").replace('"', '\\"')
            pattern     = rf'^({var}\s*=\s*).*$'
            replacement = rf'\g<1>"{safe_val}"'

        new_content = _re.sub(pattern, replacement, content, flags=_re.MULTILINE)
        if new_content != content:
            changed.append(f"{var} → {new_val!r}")
            content = new_content

    if not changed:
        return {
            "status":   "NO_CHANGE",
            "message":  "No matching variables found or values already same.",
            "pipeline": f"pipeline_{pipeline_id}",
        }

    with open(file_path, "w", encoding="utf-8") as f:
        f.write(content)

    return {
        "status":   "SUCCESS",
        "pipeline": f"pipeline_{pipeline_id}",
        "changed":  changed,
        "message":  f"{len(changed)} variable(s) updated. Airflow will reload in ~30s.",
    }