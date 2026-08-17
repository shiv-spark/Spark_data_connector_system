
# import os
# from pathlib import Path
# from dotenv import load_dotenv

# from utils.dag_generator import (
#     DAGS_FOLDER,
#     WINDOWS_DATA_PATH,
#     WINDOWS_DATASET_PATH,
#     CONTAINER_DATA_PATH,
#     CONTAINER_DATASET_PATH,
#     _safe_id,
#     _fix_path,
#     _validate_query_shape,
# )

# project_root = Path(__file__).parent.parent.parent
# load_dotenv(project_root / ".env")

# VALID_MULTI_CONNECTORS = {"csv", "excel", "google_sheets", "api", "s3", "postgres", "snowflake"}


# # ─────────────────────────────────────────────────────────────────────────────
# # VALIDATION — catch missing/empty required fields BEFORE writing a DAG file
# # that is guaranteed to fail every scheduled run.
# # ─────────────────────────────────────────────────────────────────────────────

# def _clean(val):
#     """Treat None, empty string, and whitespace-only strings as 'not provided'."""
#     if val is None:
#         return None
#     if isinstance(val, str) and val.strip() == "":
#         return None
#     return val


# def validate_source(src: dict, index: int) -> list:
#     """Validate a single source dict. Returns a list of error strings (empty if OK)."""
#     errors = []
#     ct = src.get("connector_type")
#     label = f"Source {index + 1}"

#     if ct not in VALID_MULTI_CONNECTORS:
#         errors.append(
#             f"{label}: invalid connector_type '{ct}'. Valid: {sorted(VALID_MULTI_CONNECTORS)}"
#         )
#         return errors  # no point checking type-specific fields further

#     if ct in ("csv", "excel"):
#         if not (_clean(src.get("file_path")) or _clean(src.get("folder_path"))):
#             errors.append(f"{label} ({ct}): file_path or folder_path is required and cannot be empty.")

#     elif ct == "google_sheets":
#         if not _clean(src.get("sheet_url")):
#             errors.append(f"{label} (google_sheets): sheet_url is required and cannot be empty.")

#     elif ct == "api":
#         if not _clean(src.get("api_url")):
#             errors.append(f"{label} (api): api_url is required and cannot be empty.")

#     elif ct == "s3":
#         if not _clean(src.get("s3_bucket")):
#             errors.append(f"{label} (s3): s3_bucket is required and cannot be empty.")
#         if not _clean(src.get("s3_key")):
#             errors.append(f"{label} (s3): s3_key is required and cannot be empty.")

#     elif ct == "postgres":
#         for field in ("src_pg_host", "src_pg_db", "src_pg_user", "src_pg_password"):
#             if not _clean(src.get(field)):
#                 errors.append(f"{label} (postgres): {field} is required and cannot be empty.")
#         query_error = _validate_query_shape("postgres", src.get("pg_query"))
#         if query_error:
#             errors.append(f"{label}: {query_error}")

#     elif ct == "snowflake":
#         for field in ("sf_account", "sf_user", "sf_password", "sf_warehouse", "sf_database"):
#             if not _clean(src.get(field)):
#                 errors.append(f"{label} (snowflake): {field} is required and cannot be empty.")
#         query_error = _validate_query_shape("snowflake", src.get("sf_query"))
#         if query_error:
#             errors.append(f"{label}: {query_error}")

#     return errors


# def validate_multi_pipeline_config(config: dict) -> list:
#     """Validate the full multi-source pipeline config. Returns a list of error strings."""
#     errors = []

#     if not _clean(config.get("pipeline_name")):
#         errors.append("pipeline_name is required.")
#     if not _clean(config.get("table_name")):
#         errors.append("table_name is required.")

#     sources = config.get("sources") or []
#     if not sources:
#         errors.append("At least one source is required.")
#     else:
#         for i, src in enumerate(sources):
#             errors.extend(validate_source(src, i))

#     option = config.get("option", "1")
#     if option not in ("1", "2", "3"):
#         errors.append("option must be '1' (append), '2' (overwrite), or '3' (create new).")

#     sync_mode = config.get("sync_mode", "full")
#     if sync_mode not in ("full", "incremental"):
#         errors.append("sync_mode must be 'full' or 'incremental'.")
#     if sync_mode == "incremental" and not _clean(config.get("incremental_column")):
#         errors.append("incremental_column is required when sync_mode is 'incremental'.")

#     return errors


# # ─────────────────────────────────────────────────────────────────────────────
# # Build the per-source cfg dict that dag_static_body.py's
# # _process_one_source() expects (same shape used by single-source pipelines,
# # uppercase keys).
# # ─────────────────────────────────────────────────────────────────────────────

# def _build_source_entry(src: dict, index: int, table_name: str, sync_mode: str,
#                          inc_col, pipeline_option: str) -> dict:
#     ct = src["connector_type"]
#     # First source uses the pipeline-level option (append/overwrite/create).
#     # Every subsequent source always appends, so it can't stomp on the
#     # first source's rows/overwrite the whole table.
#     src_opt = pipeline_option if index == 0 else "1"

#     entry = {
#         "CONNECTOR_TYPE":     ct,
#         "OPTION":             src_opt,
#         "TABLE_NAME":         table_name,
#         "SYNC_MODE":          sync_mode,
#         "INCREMENTAL_COLUMN": inc_col,
#     }

#     if ct in ("csv", "excel"):
#         folder_path = _clean(src.get("folder_path"))
#         file_path   = _clean(src.get("file_path"))
#         entry["FOLDER_PATH"] = _fix_path(folder_path) if folder_path else None
#         entry["FILE_PATH"]   = _fix_path(file_path)   if file_path   else None

#     elif ct == "google_sheets":
#         entry["SHEET_URL"] = _clean(src.get("sheet_url"))

#     elif ct == "api":
#         entry["API_URL"] = _clean(src.get("api_url"))
#         entry["API_CONFIG"] = src.get("api_config") or {}

#     elif ct == "s3":
#         entry["S3_BUCKET"]    = _clean(src.get("s3_bucket"))
#         entry["S3_KEY"]       = _clean(src.get("s3_key"))
#         entry["S3_FILE_TYPE"] = src.get("s3_file_type", "csv")
#         entry["S3_ACCESS_KEY"] = _clean(src.get("s3_access_key"))
#         entry["S3_SECRET_KEY"] = _clean(src.get("s3_secret_key"))

#     elif ct == "postgres":
#         entry["SRC_PG_HOST"]     = _clean(src.get("src_pg_host"))
#         entry["SRC_PG_DB"]       = _clean(src.get("src_pg_db"))
#         entry["SRC_PG_USER"]     = _clean(src.get("src_pg_user"))
#         entry["SRC_PG_PASSWORD"] = _clean(src.get("src_pg_password"))
#         entry["SRC_PG_PORT"]     = src.get("src_pg_port", "5432")
#         entry["PG_QUERY"]        = _clean(src.get("pg_query"))

#     elif ct == "snowflake":
#         entry["SF_ACCOUNT"]   = _clean(src.get("sf_account"))
#         entry["SF_USER"]      = _clean(src.get("sf_user"))
#         entry["SF_PASSWORD"]  = _clean(src.get("sf_password"))
#         entry["SF_WAREHOUSE"] = _clean(src.get("sf_warehouse"))
#         entry["SF_DATABASE"]  = _clean(src.get("sf_database"))
#         entry["SF_SCHEMA"]    = src.get("sf_schema", "PUBLIC")
#         entry["SF_ROLE"]      = _clean(src.get("sf_role"))
#         entry["SF_QUERY"]     = _clean(src.get("sf_query"))

#     return entry


# # ─────────────────────────────────────────────────────────────────────────────
# # DAG file rendering
# # ─────────────────────────────────────────────────────────────────────────────

# def _render_multi_template(config: dict) -> str:
#     pipeline_id = _safe_id(config["pipeline_name"])
#     table_name  = config["table_name"]
#     schedule    = config.get("schedule", "*/5 * * * *")
#     timezone    = config.get("timezone") or "Asia/Kolkata"
#     sync_mode   = config.get("sync_mode", "full")
#     inc_col     = _clean(config.get("incremental_column"))
#     option      = config.get("option", "1")
#     sources_cfg = config["sources"]

#     sources = [
#         _build_source_entry(src, i, table_name, sync_mode, inc_col, option)
#         for i, src in enumerate(sources_cfg)
#     ]

#     header_lines = [
#         "from airflow import DAG",
#         "from airflow.operators.python import PythonOperator",
#         "import pendulum",
#         "import os, json, requests, shutil",
#         "",
#         f"# AUTO-GENERATED — multi-source pipeline: {pipeline_id}",
#         f"# Do not manually edit. Use /create_multi_pipeline endpoint to regenerate.",
#         "",
#         f'PIPELINE_ID     = "pipeline_{pipeline_id}"',
#         f'TABLE_NAME      = "{table_name}"',
#         f'SCHEDULE        = "{schedule}"',
#         f'TIMEZONE        = "{timezone}"',
#         f'SYNC_MODE       = "{sync_mode}"',
#         f"INCREMENTAL_COLUMN = {inc_col!r}",
#         f'OPTION          = "{option}"',
#         "",
#         # Placeholder single-source fields — kept ONLY so the shared
#         # _log_run_start() / _send_email() helpers (originally written
#         # for single-source DAGs) keep working unmodified for multi-source
#         # DAGs too. They're just used for the dashboard row / email footer.
#         'CONNECTOR_TYPE  = "multi_source"',
#         "FOLDER_PATH     = None",
#         "FILE_PATH       = None",
#         "SHEET_URL       = None",
#         "API_URL         = None",
#         "AFTER_FIRST_RUN = None",
#         "",
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
#         '    "snowflake":     "ingest_snowflake",',
#         "}",
#         "",
#         f"SOURCES = {sources!r}",
#     ]

#     static_body = open(
#         os.path.join(os.path.dirname(__file__), "dag_static_body.py"),
#         encoding="utf-8"
#     ).read()

#     runner_block = '''

# def run_multi_source(**context):
#     """
#     Process every source in SOURCES, reusing the exact same hash dedup /
#     URL dedup / folder listing / file moving / path translation logic
#     (_process_one_source, above) that single-source pipelines use.
#     A failure in one source does not stop the others — all sources are
#     attempted, and the run is marked FAILED at the end if any of them failed.
#     """
#     dag_run_id = _log_run_start()
#     results    = []
#     any_failed = False
#     any_skipped = False
#     any_success = False

#     try:
#         for i, src in enumerate(SOURCES, 1):
#             label = f"source_{i}_{src['CONNECTOR_TYPE']}"
#             try:
#                 status = _process_one_source(src, source_label=label)
#                 results.append((label, status))
#                 print(f"[{label}] -> {status}")
#                 if status == "SUCCESS":
#                     any_success = True
#                 elif status == "SKIPPED":
#                     any_skipped = True

#             except Exception as e:
#                 print(f"[{label}] FAILED: {e}")
#                 results.append((label, "FAILED"))
#                 any_failed = True

#         if any_failed:
#             failed_list = [lbl for lbl, st in results if st == "FAILED"]
#             raise Exception(f"Source(s) failed: {failed_list}")
        
#         overall_status = "SUCCESS" if any_success else "SKIPPED"
#         _log_run_end(dag_run_id, overall_status)
#         print(f"All sources processed. Overall status: {overall_status}")

#         if overall_status == "SUCCESS":
#             _send_email("success", dag_run_id=dag_run_id)

#         # _log_run_end(dag_run_id, "SUCCESS")
#         # print("All sources processed successfully!")
#         # _send_email("success", dag_run_id=dag_run_id)

#     except Exception as e:
#         _log_run_end(dag_run_id, "FAILED", str(e))
#         _send_email("failed", error=str(e), dag_run_id=dag_run_id)
#         raise
# '''

#     dag_block = """

# with DAG(
#     dag_id            = PIPELINE_ID,
#     start_date        = pendulum.datetime(2024, 1, 1, tz=TIMEZONE),
#     schedule_interval = SCHEDULE,
#     catchup           = False,
#     max_active_runs   = 1,
#     tags              = ["multi-source", "connector"],
# ) as dag:
#     PythonOperator(
#         task_id         = "run_multi_source",
#         python_callable = run_multi_source,
#     )
# """

#     return "\n".join(header_lines) + "\n" + static_body + runner_block + dag_block


# def create_multi_dag_file(config: dict) -> dict:
#     # Fail loudly here instead of generating a DAG guaranteed to fail on
#     # every scheduled run.
#     validation_errors = validate_multi_pipeline_config(config)
#     if validation_errors:
#         return {
#             "status": "FAILED",
#             "errors": validation_errors,
#         }

#     pipeline_id = _safe_id(config["pipeline_name"])
#     filename    = f"pipeline_{pipeline_id}.py"
#     file_path   = os.path.join(DAGS_FOLDER, filename)

#     if os.path.exists(file_path):
#         return {
#             "status": "FAILED",
#             "error":  f"Pipeline '{pipeline_id}' already exists."
#         }

#     content = _render_multi_template({**config, "pipeline_name": pipeline_id})

#     os.makedirs(DAGS_FOLDER, exist_ok=True)
#     with open(file_path, "w", encoding="utf-8") as f:
#         f.write(content)

#     return {
#         "status":        "SUCCESS",
#         "dag_id":        f"pipeline_{pipeline_id}",
#         "file_path":     file_path,
#         "sources_count": len(config["sources"]),
#         "message":       f"{len(config['sources'])} sources → table '{config['table_name']}'. "
#                           f"Airflow will pick up in ~30s.",
#     }

import os
from pathlib import Path
from dotenv import load_dotenv

from utils.dag_generator import (
    DAGS_FOLDER,
    WINDOWS_DATA_PATH,
    WINDOWS_DATASET_PATH,
    CONTAINER_DATA_PATH,
    CONTAINER_DATASET_PATH,
    _safe_id,
    _fix_path,
    _validate_query_shape,
)

project_root = Path(__file__).parent.parent.parent
load_dotenv(project_root / ".env")

VALID_MULTI_CONNECTORS = {"csv", "excel", "google_sheets", "api", "s3", "postgres", "snowflake"}


# ─────────────────────────────────────────────────────────────────────────────
# VALIDATION — catch missing/empty required fields BEFORE writing a DAG file
# that is guaranteed to fail every scheduled run.
# ─────────────────────────────────────────────────────────────────────────────

def _clean(val):
    """Treat None, empty string, and whitespace-only strings as 'not provided'."""
    if val is None:
        return None
    if isinstance(val, str) and val.strip() == "":
        return None
    return val


def validate_source(src: dict, index: int) -> list:
    """Validate a single source dict. Returns a list of error strings (empty if OK)."""
    errors = []
    ct = src.get("connector_type")
    label = f"Source {index + 1}"

    if ct not in VALID_MULTI_CONNECTORS:
        errors.append(
            f"{label}: invalid connector_type '{ct}'. Valid: {sorted(VALID_MULTI_CONNECTORS)}"
        )
        return errors  # no point checking type-specific fields further

    if ct in ("csv", "excel"):
        if not (_clean(src.get("file_path")) or _clean(src.get("folder_path"))):
            errors.append(f"{label} ({ct}): file_path or folder_path is required and cannot be empty.")

    elif ct == "google_sheets":
        if not _clean(src.get("sheet_url")):
            errors.append(f"{label} (google_sheets): sheet_url is required and cannot be empty.")

    elif ct == "api":
        if not _clean(src.get("api_url")):
            errors.append(f"{label} (api): api_url is required and cannot be empty.")

    elif ct == "s3":
        if not _clean(src.get("s3_bucket")):
            errors.append(f"{label} (s3): s3_bucket is required and cannot be empty.")
        if not _clean(src.get("s3_key")):
            errors.append(f"{label} (s3): s3_key is required and cannot be empty.")

    elif ct == "postgres":
        for field in ("src_pg_host", "src_pg_db", "src_pg_user", "src_pg_password"):
            if not _clean(src.get(field)):
                errors.append(f"{label} (postgres): {field} is required and cannot be empty.")
        query_error = _validate_query_shape("postgres", src.get("pg_query"))
        if query_error:
            errors.append(f"{label}: {query_error}")

    elif ct == "snowflake":
        for field in ("sf_account", "sf_user", "sf_password", "sf_warehouse", "sf_database"):
            if not _clean(src.get(field)):
                errors.append(f"{label} (snowflake): {field} is required and cannot be empty.")
        query_error = _validate_query_shape("snowflake", src.get("sf_query"))
        if query_error:
            errors.append(f"{label}: {query_error}")

    return errors


def validate_multi_pipeline_config(config: dict) -> list:
    """Validate the full multi-source pipeline config. Returns a list of error strings."""
    errors = []

    if not _clean(config.get("pipeline_name")):
        errors.append("pipeline_name is required.")
    if not _clean(config.get("table_name")):
        errors.append("table_name is required.")

    sources = config.get("sources") or []
    if not sources:
        errors.append("At least one source is required.")
    else:
        for i, src in enumerate(sources):
            errors.extend(validate_source(src, i))

    option = config.get("option", "1")
    if option not in ("1", "2", "3"):
        errors.append("option must be '1' (append), '2' (overwrite), or '3' (create new).")

    sync_mode = config.get("sync_mode", "full")
    if sync_mode not in ("full", "incremental"):
        errors.append("sync_mode must be 'full' or 'incremental'.")
    if sync_mode == "incremental" and not _clean(config.get("incremental_column")):
        errors.append("incremental_column is required when sync_mode is 'incremental'.")

    return errors


# ─────────────────────────────────────────────────────────────────────────────
# Build the per-source cfg dict that dag_static_body.py's
# _process_one_source() expects (same shape used by single-source pipelines,
# uppercase keys).
# ─────────────────────────────────────────────────────────────────────────────

def _build_source_entry(src: dict, index: int, table_name: str, sync_mode: str,
                         inc_col, pipeline_option: str) -> dict:
    ct = src["connector_type"]
    # First source uses the pipeline-level option (append/overwrite/create).
    # Every subsequent source always appends, so it can't stomp on the
    # first source's rows/overwrite the whole table.
    src_opt = pipeline_option if index == 0 else "1"

    entry = {
        "CONNECTOR_TYPE":     ct,
        "OPTION":             src_opt,
        "TABLE_NAME":         table_name,
        "SYNC_MODE":          sync_mode,
        "INCREMENTAL_COLUMN": inc_col,
        "QUALITY_CONNECTION_ID": src.get("quality_connection_id") or None,
        "QUALITY_CONFIG":        src.get("quality_config") or None,
        "QUALITY_ON_FAIL":       src.get("quality_on_fail") or "warn",
        "DF_QUALITY_CONFIG":     src.get("df_quality_config") or None,
        "DF_QUALITY_ON_FAIL":    src.get("df_quality_on_fail") or "warn",
    }

    if ct in ("csv", "excel"):
        folder_path = _clean(src.get("folder_path"))
        file_path   = _clean(src.get("file_path"))
        entry["FOLDER_PATH"] = _fix_path(folder_path) if folder_path else None
        entry["FILE_PATH"]   = _fix_path(file_path)   if file_path   else None

    elif ct == "google_sheets":
        entry["SHEET_URL"] = _clean(src.get("sheet_url"))

    elif ct == "api":
        entry["API_URL"] = _clean(src.get("api_url"))
        entry["API_CONFIG"] = src.get("api_config") or {}

    elif ct == "s3":
        entry["S3_BUCKET"]    = _clean(src.get("s3_bucket"))
        entry["S3_KEY"]       = _clean(src.get("s3_key"))
        entry["S3_FILE_TYPE"] = src.get("s3_file_type", "csv")
        entry["S3_ACCESS_KEY"] = _clean(src.get("s3_access_key"))
        entry["S3_SECRET_KEY"] = _clean(src.get("s3_secret_key"))

    elif ct == "postgres":
        entry["SRC_PG_HOST"]     = _clean(src.get("src_pg_host"))
        entry["SRC_PG_DB"]       = _clean(src.get("src_pg_db"))
        entry["SRC_PG_USER"]     = _clean(src.get("src_pg_user"))
        entry["SRC_PG_PASSWORD"] = _clean(src.get("src_pg_password"))
        entry["SRC_PG_PORT"]     = src.get("src_pg_port", "5432")
        entry["PG_QUERY"]        = _clean(src.get("pg_query"))

    elif ct == "snowflake":
        entry["SF_ACCOUNT"]   = _clean(src.get("sf_account"))
        entry["SF_USER"]      = _clean(src.get("sf_user"))
        entry["SF_PASSWORD"]  = _clean(src.get("sf_password"))
        entry["SF_WAREHOUSE"] = _clean(src.get("sf_warehouse"))
        entry["SF_DATABASE"]  = _clean(src.get("sf_database"))
        entry["SF_SCHEMA"]    = src.get("sf_schema", "PUBLIC")
        entry["SF_ROLE"]      = _clean(src.get("sf_role"))
        entry["SF_QUERY"]     = _clean(src.get("sf_query"))

    return entry


# ─────────────────────────────────────────────────────────────────────────────
# DAG file rendering
# ─────────────────────────────────────────────────────────────────────────────

def _render_multi_template(config: dict) -> str:
    pipeline_id = _safe_id(config["pipeline_name"])
    table_name  = config["table_name"]
    schedule    = config.get("schedule", "*/5 * * * *")
    timezone    = config.get("timezone") or "Asia/Kolkata"
    sync_mode   = config.get("sync_mode", "full")
    inc_col     = _clean(config.get("incremental_column"))
    option      = config.get("option", "1")
    sources_cfg = config["sources"]

    sources = [
        _build_source_entry(src, i, table_name, sync_mode, inc_col, option)
        for i, src in enumerate(sources_cfg)
    ]

    header_lines = [
        "from airflow import DAG",
        "from airflow.operators.python import PythonOperator",
        "import pendulum",
        "import os, json, requests, shutil",
        "",
        f"# AUTO-GENERATED — multi-source pipeline: {pipeline_id}",
        f"# Do not manually edit. Use /create_multi_pipeline endpoint to regenerate.",
        "",
        f'PIPELINE_ID     = "pipeline_{pipeline_id}"',
        f'TABLE_NAME      = "{table_name}"',
        f'SCHEDULE        = "{schedule}"',
        f'TIMEZONE        = "{timezone}"',
        f'SYNC_MODE       = "{sync_mode}"',
        f"INCREMENTAL_COLUMN = {inc_col!r}",
        f'OPTION          = "{option}"',
        "",
        # Placeholder single-source fields — kept ONLY so the shared
        # _log_run_start() / _send_email() helpers (originally written
        # for single-source DAGs) keep working unmodified for multi-source
        # DAGs too. They're just used for the dashboard row / email footer.
        'CONNECTOR_TYPE  = "multi_source"',
        "FOLDER_PATH     = None",
        "FILE_PATH       = None",
        "SHEET_URL       = None",
        "API_URL         = None",
        "AFTER_FIRST_RUN = None",
        "",
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
        "",
        f"SOURCES = {sources!r}",
    ]

    static_body = open(
        os.path.join(os.path.dirname(__file__), "dag_static_body.py"),
        encoding="utf-8"
    ).read()

    runner_block = '''

def run_multi_source(**context):
    """
    Process every source in SOURCES, reusing the exact same hash dedup /
    URL dedup / folder listing / file moving / path translation logic
    (_process_one_source, above) that single-source pipelines use.
    A failure in one source does not stop the others — all sources are
    attempted, and the run is marked FAILED at the end if any of them failed.
    """
    dag_run_id = _log_run_start()
    results    = []
    any_failed = False
    any_skipped = False
    any_success = False

    try:
        for i, src in enumerate(SOURCES, 1):
            label = f"source_{i}_{src['CONNECTOR_TYPE']}"
            try:
                status = _process_one_source(src, source_label=label)
                results.append((label, status))
                print(f"[{label}] -> {status}")
                if status == "SUCCESS":
                    any_success = True
                elif status == "SKIPPED":
                    any_skipped = True

            except Exception as e:
                print(f"[{label}] FAILED: {e}")
                results.append((label, "FAILED"))
                any_failed = True

        if any_failed:
            failed_list = [lbl for lbl, st in results if st == "FAILED"]
            raise Exception(f"Source(s) failed: {failed_list}")
        
        overall_status = "SUCCESS" if any_success else "SKIPPED"
        _log_run_end(dag_run_id, overall_status)
        print(f"All sources processed. Overall status: {overall_status}")

        if overall_status == "SUCCESS":
            _send_email("success", dag_run_id=dag_run_id)

        # _log_run_end(dag_run_id, "SUCCESS")
        # print("All sources processed successfully!")
        # _send_email("success", dag_run_id=dag_run_id)

    except Exception as e:
        _log_run_end(dag_run_id, "FAILED", str(e))
        _send_email("failed", error=str(e), dag_run_id=dag_run_id)
        raise
'''

    dag_block = """

with DAG(
    dag_id            = PIPELINE_ID,
    start_date        = pendulum.datetime(2024, 1, 1, tz=TIMEZONE),
    schedule_interval = SCHEDULE,
    catchup           = False,
    max_active_runs   = 1,
    tags              = ["multi-source", "connector"],
) as dag:
    PythonOperator(
        task_id         = "run_multi_source",
        python_callable = run_multi_source,
    )
"""

    return "\n".join(header_lines) + "\n" + static_body + runner_block + dag_block


def create_multi_dag_file(config: dict) -> dict:
    # Fail loudly here instead of generating a DAG guaranteed to fail on
    # every scheduled run.
    validation_errors = validate_multi_pipeline_config(config)
    if validation_errors:
        return {
            "status": "FAILED",
            "errors": validation_errors,
        }

    pipeline_id = _safe_id(config["pipeline_name"])
    filename    = f"pipeline_{pipeline_id}.py"
    file_path   = os.path.join(DAGS_FOLDER, filename)

    if os.path.exists(file_path):
        return {
            "status": "FAILED",
            "error":  f"Pipeline '{pipeline_id}' already exists."
        }

    content = _render_multi_template({**config, "pipeline_name": pipeline_id})

    os.makedirs(DAGS_FOLDER, exist_ok=True)
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(content)

    return {
        "status":        "SUCCESS",
        "dag_id":        f"pipeline_{pipeline_id}",
        "file_path":     file_path,
        "sources_count": len(config["sources"]),
        "message":       f"{len(config['sources'])} sources → table '{config['table_name']}'. "
                          f"Airflow will pick up in ~30s.",
    }