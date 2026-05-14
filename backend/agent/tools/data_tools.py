"""
data_tools.py
Fetches raw data from files, S3-compatible paths, APIs, and pipeline tables.
Each function returns a list of dicts ready for analysis.
"""

import pandas as pd
from agent.db import query
from agent.logger import get_logger

logger = get_logger(__name__)


def fetch_pipeline_runs(pipeline_name: str = None, limit: int = 200) -> list[dict]:
    logger.info("fetch_pipeline_runs(pipeline=%s, limit=%d)", pipeline_name, limit)
    if pipeline_name:
        sql = """
            SELECT run_id, connector_name, source, start_time, end_time,
                   status, records_count, error
            FROM pipeline_runs
            WHERE connector_name = %s
            ORDER BY start_time DESC
            LIMIT %s
        """
        return query(sql, [pipeline_name, limit])

    sql = """
        SELECT run_id, connector_name, source, start_time, end_time,
               status, records_count, error
        FROM pipeline_runs
        ORDER BY start_time DESC
        LIMIT %s
    """
    return query(sql, [limit])


def fetch_pipeline_logs(run_id: str = None, limit: int = 500) -> list[dict]:
    logger.info("fetch_pipeline_logs(run_id=%s, limit=%d)", run_id, limit)
    if run_id:
        sql = """
            SELECT id, run_id, log_time, level, message
            FROM pipeline_logs
            WHERE run_id = %s
            ORDER BY log_time DESC
            LIMIT %s
        """
        return query(sql, [run_id, limit])

    sql = """
        SELECT id, run_id, log_time, level, message
        FROM pipeline_logs
        ORDER BY log_time DESC
        LIMIT %s
    """
    return query(sql, [limit])


def fetch_pipeline_metrics(pipeline_name: str = None, table_name: str = None, limit: int = 200) -> list[dict]:
    logger.info("fetch_pipeline_metrics(pipeline=%s, table=%s, limit=%d)", pipeline_name, table_name, limit)
    conditions = []
    params = []

    if pipeline_name:
        conditions.append("(pipeline_id = %s OR connector_type = %s)")
        params.extend([pipeline_name, pipeline_name])
    if table_name:
        conditions.append("table_name = %s")
        params.append(table_name)

    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
    params.append(limit)

    sql = f"""
        SELECT id, pipeline_id, table_name, rows_inserted, rows_skipped,
               rows_failed, duration_sec, evolved_columns, match_pct,
               file_name, connector_type, option, status, error_message, logged_at
        FROM pipeline_metrics
        {where}
        ORDER BY logged_at DESC
        LIMIT %s
    """
    return query(sql, params)


def fetch_airflow_runs(pipeline_name: str = None, limit: int = 200) -> list[dict]:
    logger.info("fetch_airflow_runs(pipeline=%s, limit=%d)", pipeline_name, limit)
    if pipeline_name:
        sql = """
            SELECT id, dag_id, dag_run_id, pipeline_name, connector_type,
                   file_path, folder_path, sheet_url, api_url, operation,
                   table_name, schedule, status, execution_date,
                   triggered_by, error_message, created_at
            FROM airflow_pipeline_runs
            WHERE pipeline_name = %s
            ORDER BY created_at DESC
            LIMIT %s
        """
        return query(sql, [pipeline_name, limit])

    sql = """
        SELECT id, dag_id, dag_run_id, pipeline_name, connector_type,
               file_path, folder_path, sheet_url, api_url, operation,
               table_name, schedule, status, execution_date,
               triggered_by, error_message, created_at
        FROM airflow_pipeline_runs
        ORDER BY created_at DESC
        LIMIT %s
    """
    return query(sql, [limit])


def fetch_dag_logs(pipeline_id: str = None, dag_run_id: str = None, limit: int = 200) -> list[dict]:
    logger.info("fetch_dag_logs(pipeline_id=%s, dag_run_id=%s, limit=%d)", pipeline_id, dag_run_id, limit)
    conditions = []
    params = []

    if pipeline_id:
        conditions.append("pipeline_id = %s")
        params.append(pipeline_id)
    if dag_run_id:
        conditions.append("dag_run_id = %s")
        params.append(dag_run_id)

    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
    params.append(limit)

    sql = f"""
        SELECT id, pipeline_id, dag_run_id, task_id,
               status, log_content, log_file_path, created_at
        FROM pipeline_dag_logs
        {where}
        ORDER BY created_at DESC
        LIMIT %s
    """
    return query(sql, params)


def fetch_full_pipeline_summary(pipeline_name: str) -> dict:
    logger.info("fetch_full_pipeline_summary(pipeline=%s)", pipeline_name)
    return {
        "pipeline_name": pipeline_name,
        "runs": fetch_pipeline_runs(pipeline_name),
        "logs": fetch_pipeline_logs(),
        "metrics": fetch_pipeline_metrics(pipeline_name),
        "airflow_runs": fetch_airflow_runs(pipeline_name),
        "dag_logs": fetch_dag_logs(),
    }


def _resolve_dataset_path(path: str) -> str:
    """
    The frontend may submit a relative path like 'Dataset/foo.csv' or just
    'foo.csv'. Inside the container the file lives under one of several
    mounted roots (/app/dataset, /app/data, /app/uploads, /opt/airflow/dataset_win).
    Try the path as-is first, then fall back to those roots with case-insensitive
    matching so dataset filenames work regardless of how the user typed them.
    """
    import os, glob

    if not path:
        return path

    # 1) Exact path (absolute or relative to CWD).
    if os.path.exists(path):
        return path

    # 2) Strip any leading "Dataset/" / "dataset/" / "data/" prefix and try roots.
    cleaned = path.replace("\\", "/").lstrip("./")
    parts = cleaned.split("/", 1)
    tail  = parts[1] if len(parts) > 1 and parts[0].lower() in {"dataset", "data", "uploads"} else cleaned

    roots = [
        "/app/dataset", "/app/data", "/app/uploads",
        "/opt/airflow/dataset_win", "/opt/airflow/dataset",
        "Dataset", "dataset", "data", ".",
    ]
    for root in roots:
        cand = os.path.join(root, tail)
        if os.path.exists(cand):
            return cand
        # case-insensitive lookup inside the root
        if os.path.isdir(root):
            target = os.path.basename(tail).lower()
            for entry in os.listdir(root):
                if entry.lower() == target:
                    return os.path.join(root, entry)

    # 3) Last resort: glob anywhere under /app for the bare filename.
    matches = glob.glob(f"/app/**/{os.path.basename(path)}", recursive=True)
    if matches:
        return matches[0]

    # Nothing found — return original so the caller's error message stays clear.
    return path


def _read_dataframe(path: str) -> pd.DataFrame:
    resolved = _resolve_dataset_path(path)
    if resolved != path:
        logger.info("Resolved dataset path: %r → %r", path, resolved)
    lower = resolved.lower()
    if lower.endswith(".csv"):
        return pd.read_csv(resolved)
    if lower.endswith((".xlsx", ".xls")):
        return pd.read_excel(resolved)
    if lower.endswith(".json"):
        return pd.read_json(resolved)
    if lower.endswith(".parquet"):
        return pd.read_parquet(resolved)
    return pd.read_csv(resolved)


def fetch_data_by_source(source_type, **kwargs) -> list[dict]:
    logger.info("fetch_data_by_source(source=%s)", source_type)
    logger.debug("Source kwargs: %s", kwargs)

    try:
        if source_type == "postgres":
            return fetch_pipeline_metrics(kwargs.get("pipeline_name"), kwargs.get("table_name"))

        if source_type == "csv":
            path = kwargs.get("file_path")
            logger.info("Reading CSV: %s", path)
            return _read_dataframe(path).to_dict(orient="records")

        if source_type == "excel":
            path = kwargs.get("file_path")
            logger.info("Reading Excel: %s", path)
            return _read_dataframe(path).to_dict(orient="records")

        if source_type == "google_sheet":
            url = kwargs.get("sheet_url")
            logger.info("Reading Google Sheet: %s", url)
            return pd.read_csv(url).to_dict(orient="records")

        if source_type == "s3":
            s3_path = kwargs.get("s3_path")
            logger.info("Reading S3/path data: %s", s3_path)
            if not s3_path:
                return []
            return _read_dataframe(s3_path).to_dict(orient="records")

        if source_type == "api":
            import requests
            api_url = kwargs.get("api_url")
            api_headers = kwargs.get("api_headers") or {}
            logger.info("Fetching API data from: %s", api_url)
            payload = requests.get(api_url, headers=api_headers, timeout=30).json()
            if isinstance(payload, list):
                return payload
            if isinstance(payload, dict):
                for value in payload.values():
                    if isinstance(value, list):
                        return value
                return [payload]
            return []

        logger.error("Unsupported source type: %s", source_type)
        return []

    except Exception as e:
        logger.error("fetch_data_by_source failed for '%s': %s", source_type, e, exc_info=True)
        raise
