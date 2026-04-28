"""
data_tools.py
Fetches raw data from all pipeline tables in Postgres.
Each function returns a list of dicts — ready for analysis.
"""
import pandas as pd
from agent.db import query
from agent.logger import get_logger

logger = get_logger(__name__)


# ─── pipeline_runs ────────────────────────────────────────────────────────────

def fetch_pipeline_runs(pipeline_name: str = None, limit: int = 200) -> list[dict]:
    """Fetch records from pipeline_runs. Filter by connector_name if given."""
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
    else:
        sql = """
            SELECT run_id, connector_name, source, start_time, end_time,
                   status, records_count, error
            FROM pipeline_runs
            ORDER BY start_time DESC
            LIMIT %s
        """
        return query(sql, [limit])


# ─── pipeline_logs ────────────────────────────────────────────────────────────

def fetch_pipeline_logs(run_id: str = None, limit: int = 500) -> list[dict]:
    """Fetch logs. Filter by run_id if given."""
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
    else:
        sql = """
            SELECT id, run_id, log_time, level, message
            FROM pipeline_logs
            ORDER BY log_time DESC
            LIMIT %s
        """
        return query(sql, [limit])


# ─── pipeline_metrics ─────────────────────────────────────────────────────────

def fetch_pipeline_metrics(pipeline_name: str = None, table_name: str = None, limit: int = 200) -> list[dict]:
    """Fetch metrics. Filter by pipeline or table name."""
    logger.info("fetch_pipeline_metrics(pipeline=%s, table=%s, limit=%d)",
                pipeline_name, table_name, limit)
    conditions = []
    params = []

    if pipeline_name:
        conditions.append("connector_type = %s")
        params.append(pipeline_name)
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


# ─── airflow_pipeline_runs ────────────────────────────────────────────────────

def fetch_airflow_runs(pipeline_name: str = None, limit: int = 200) -> list[dict]:
    """Fetch Airflow DAG run records."""
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
    else:
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


# ─── pipeline_dag_logs ────────────────────────────────────────────────────────

def fetch_dag_logs(pipeline_id: str = None, dag_run_id: str = None, limit: int = 200) -> list[dict]:
    """Fetch DAG task logs."""
    logger.info("fetch_dag_logs(pipeline_id=%s, dag_run_id=%s, limit=%d)",
                pipeline_id, dag_run_id, limit)
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


# ─── Cross-table summary ──────────────────────────────────────────────────────

def fetch_full_pipeline_summary(pipeline_name: str) -> dict:
    """
    Aggregates data from all tables for a single pipeline.
    Returns a combined dict the agent can pass to analysis tools.
    """
    logger.info("fetch_full_pipeline_summary(pipeline=%s)", pipeline_name)
    return {
        "pipeline_name": pipeline_name,
        "runs":          fetch_pipeline_runs(pipeline_name),
        "logs":          fetch_pipeline_logs(),          # filtered per run later
        "metrics":       fetch_pipeline_metrics(pipeline_name),
        "airflow_runs":  fetch_airflow_runs(pipeline_name),
        "dag_logs":      fetch_dag_logs(),
    }



def fetch_data_by_source(source_type, **kwargs) -> list[dict]:
    logger.info("fetch_data_by_source(source=%s)", source_type)
    logger.debug("Source kwargs: %s", kwargs)

    try:
        if source_type == "postgres":
            return fetch_pipeline_metrics(kwargs.get("pipeline_name"))

        elif source_type == "csv":
            path = kwargs.get("file_path")
            logger.info("Reading CSV: %s", path)
            df = pd.read_csv(path)
            logger.info("CSV loaded: %d rows × %d cols", len(df), len(df.columns))
            return df.to_dict(orient="records")

        elif source_type == "excel":
            path = kwargs.get("file_path")
            logger.info("Reading Excel: %s", path)
            df = pd.read_excel(path)
            logger.info("Excel loaded: %d rows × %d cols", len(df), len(df.columns))
            return df.to_dict(orient="records")

        elif source_type == "google_sheet":
            url = kwargs.get("sheet_url")
            logger.info("Reading Google Sheet: %s", url)
            df = pd.read_csv(url)  # export as csv link
            logger.info("Sheet loaded: %d rows × %d cols", len(df), len(df.columns))
            return df.to_dict(orient="records")

        elif source_type == "s3":
            logger.info("S3 source — not yet implemented")
            # fetch from S3, read into pandas
            ...

        elif source_type == "api":
            import requests
            api_url = kwargs.get("api_url")
            logger.info("Fetching API data from: %s", api_url)
            r = requests.get(api_url)
            logger.info("API response status: %d", r.status_code)
            return r.json()

        else:
            logger.error("Unsupported source type: %s", source_type)
            return []

    except Exception as e:
        logger.error("fetch_data_by_source failed for '%s': %s", source_type, e, exc_info=True)
        raise