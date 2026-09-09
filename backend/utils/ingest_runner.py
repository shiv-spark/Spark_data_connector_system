



import os
import time                                          
import psycopg2
from utils.logger import DBLogger
from utils.run_tracker import RunTracker
from utils.schema_detector import detect_schema
from utils.schema_applier import apply_custom_schema, resolve_custom_schema, custom_schema_to_sql
from loaders.db_loader import load_to_db, log_pipeline_metrics   
from pathlib import Path
from dotenv import load_dotenv

project_root = Path(__file__).parent.parent.parent
load_dotenv(project_root / ".env")

DB_CONFIG = {
    "host":     os.getenv("DB_HOST",     "postgres"),
    "database": os.getenv("DB_NAME",     "airflow"),
    "user":     os.getenv("DB_USER",     "airflow"),
    "password": os.getenv("DB_PASSWORD", "airflow"),
    "port":     os.getenv("DB_PORT",     "5432"),
}


def _first_fix_suggestions(quality_result: dict, limit: int = 2) -> str:
    """Pull the fix_suggestion(s) off the first `limit` failed/errored
    results so a blocked pipeline's error message says what to do next,
    not just that it stopped. Every result already carries a fix_suggestion
    (see quality/fix_suggestions.py), so this is just formatting."""
    failing = [
        r for r in (quality_result.get("results") or [])
        if r.get("status") in ("FAIL", "ERROR") and r.get("fix_suggestion")
    ]
    if not failing:
        return ""
    lines = [f"[{r['check_name']}] {r['fix_suggestion']}" for r in failing[:limit]]
    more = len(failing) - limit
    suffix = f" (+{more} more failed check(s) — see the full report)" if more > 0 else ""
    return "Suggested fix — " + " | ".join(lines) + suffix


def _save_quality_snapshot(pipeline_id, table_name, ingest_status, df_quality_result, quality_result):
    """Persist this run's quality gate result(s) so the Pipelines page can
    show a structured 'last run quality' panel instead of raw logs. See
    quality/pipeline_quality_store.py. Best-effort — never raises."""
    try:
        from quality.pipeline_quality_store import save_quality_snapshot
        save_quality_snapshot(
            pipeline_id=pipeline_id, table_name=table_name, ingest_status=ingest_status,
            df_quality=df_quality_result, quality=quality_result,
        )
    except Exception:
        pass


# ─────────────────────────────────────────────────────────────────────────
# DataFrame-level quality gate — runs BEFORE load_to_db(), directly on the
# in-memory df. Unlike the post-load SQL gate below, "block" here has a real
# effect: load_to_db() is never called, so nothing bad reaches the table.
# ─────────────────────────────────────────────────────────────────────────
def _run_dataframe_quality_gate(df, df_quality_config: dict, logger: "DBLogger") -> dict:
    from quality.dataframe_checks import run_dataframe_quality_checks

    result = run_dataframe_quality_checks(df, df_quality_config)

    logger.log(
        "INFO",
        f"DataFrame quality (pre-ingest): {result['status']} "
        f"({result['passed']}/{result['total_checks']} checks passed)",
    )
    for r in result["results"]:
        if r["status"] != "PASS":
            logger.log("WARNING", f"[{r['check_name']}] {r['status']}: {r['message']}")
            if r.get("fix_suggestion"):
                logger.log("INFO", f"  ↳ Suggested fix: {r['fix_suggestion']}")

    return result


# ─────────────────────────────────────────────────────────────────────────
# Data-quality gate — runs right after load_to_db() succeeds, against the
# table that was just loaded. Reuses the existing quality/router.py checks
# module (the same code the Data Quality page calls), just invoked directly
# as a function instead of over HTTP, since this call already happens
# inside the backend process.
#
# NOTE on "block": load_to_db() has already committed the rows by the time
# this runs, so "block" does not roll the load back — it means the ingest
# run itself is marked FAILED (and alerted on) rather than SUCCESS, so bad
# loads are visible and don't silently look fine. If you need a true
# all-or-nothing guarantee, use the dataframe-level gate above instead
# (df_quality_config / df_quality_on_fail), which runs before load.
# ─────────────────────────────────────────────────────────────────────────
def _run_quality_gate(connection_id: int, table_name: str, quality_config: dict, logger: "DBLogger") -> dict:
    import asyncio
    from quality.router import RunQualityRequest, TableCheckSpec, run_quality_checks

    spec_kwargs = dict(quality_config or {})
    spec_kwargs.pop("table_name", None)  # table_name is always the just-loaded table, not user-configurable here
    table_spec = TableCheckSpec(table_name=table_name, **spec_kwargs)
    request = RunQualityRequest(connection_id=connection_id, tables=[table_spec])

    result = asyncio.run(run_quality_checks(request))

    logger.log(
        "INFO",
        f"Data quality: {result['status']} ({result['passed']}/{result['total_checks']} checks passed) "
        f"— quality_run_id={result['run_id']}",
    )
    for r in result["results"]:
        if r["status"] != "PASS":
            logger.log("WARNING", f"[{r['check_name']}] {r['status']}: {r['message']}")
            if r.get("fix_suggestion"):
                logger.log("INFO", f"  ↳ Suggested fix: {r['fix_suggestion']}")

    return result

def run_ingestion(connector_func, source, connector_name, *args,
                  option=None, table_name=None,
                  sync_mode="full", incremental_column=None, pipeline_id=None,
                  quality_connection_id=None, quality_config=None, quality_on_fail="warn",
                  df_quality_config=None, df_quality_on_fail="warn",
                  custom_schema=None,
                  destination_type="postgres", destination_connection_id=None, destination_config=None,
                  **connector_kwargs):

    conn     = psycopg2.connect(**DB_CONFIG)
    tracker  = RunTracker(conn)
    run_id   = tracker.start_run(connector_name, source)
    logger   = DBLogger(conn, run_id)

    connector_type_map = {
        "CSVConnector":          "csv",
        "ExcelConnector":        "excel",
        "GoogleSheetsConnector": "google_sheets",
        "APIConnector":          "api",
        "PostgresConnector":     "postgres",
        "MySQLConnector":        "mysql",
        "OracleConnector":       "oracle",
        "MongoDBConnector":      "mongodb",
        "S3Connector":           "s3",
        "SalesforceConnector":  "salesforce",
        "HubSpotConnector":     "hubspot",
        "ZohoConnector":        "zoho",
        "SnowflakeConnector":   "snowflake",
    }
    connector_type = connector_type_map.get(connector_name, connector_name)
    file_name = os.path.basename(source) if (source and os.path.exists(source)) else (source[:50] if source else None)
    pipeline_id    = pipeline_id or f"pipeline_{table_name}"
    start_time     = time.time()         
    load_attempted    = False
    quality_result    = None   # ← visible in except block too, so a "block" failure still returns the report
    df_quality_result = None

    try:
        logger.log("INFO", f"{connector_name} started | sync_mode={sync_mode}")

        if connector_kwargs:
            df = connector_func(**connector_kwargs)
        else:
            df = connector_func(*args)

        row_count = df.shape[0]
        logger.log("INFO", f"Fetched {row_count} rows")

        detect_schema(df)
        logger.log("INFO", "Schema detected")

        # ── User-defined schema (optional) ────────────────────────────────
        # Any source, any shape — if the user has defined their own
        # {column: type} schema, coerce the data toward it here (before the
        # quality gates and the DB write), and hand the resolved CANONICAL
        # types (integer/float/boolean/date/timestamp/text/json) down to
        # load_to_db() — every destination adapter maps canonical -> its
        # own native SQL type, so this works unchanged for any destination
        # (see backend/destinations/).
        custom_schema_canonical = None
        if custom_schema:
            df, schema_report = apply_custom_schema(df, custom_schema)
            row_count = df.shape[0]
            custom_schema_canonical = resolve_custom_schema(custom_schema)
            logger.log(
                "INFO",
                f"Custom schema applied to columns: {list(schema_report['applied'].keys())}",
            )
            for w in schema_report["warnings"]:
                logger.log("WARNING", f"[custom_schema] {w}")

        # ── DataFrame-level quality gate (optional, runs BEFORE ingest) ──
        # This is the only gate that can truly stop bad data from ever
        # reaching the table — it runs before load_attempted is set, so a
        # "block" here raises before load_to_db() is ever called.
        if df_quality_config:
            try:
                df_quality_result = _run_dataframe_quality_gate(
                    df=df, df_quality_config=df_quality_config, logger=logger,
                )
            except Exception as dqe:
                # A malformed df_quality_config should never silently block
                # a run that would otherwise have been fine — log it and
                # proceed as if no pre-ingest gate had been configured.
                logger.log("ERROR", f"DataFrame quality gate could not run: {dqe}")
                df_quality_result = {"status": "ERROR", "error": str(dqe)}

            if (
                df_quality_result
                and df_quality_result.get("status") == "FAIL"
                and df_quality_on_fail == "block"
            ):
                raise RuntimeError(
                    "DataFrame quality gate blocked this run before ingest: "
                    f"{df_quality_result.get('failed', 0)}/{df_quality_result.get('total_checks', 0)} "
                    f"check(s) failed. No rows were written to '{table_name}'. "
                    + _first_fix_suggestions(df_quality_result)
                )

        load_attempted = True             
        load_to_db(
            df,
            option             = option,
            table_name         = table_name,
            pipeline_id        = pipeline_id,
            connector_type     = connector_type,
            file_name          = file_name,
            sync_mode          = sync_mode,
            incremental_column = incremental_column,
            custom_schema      = custom_schema_canonical,
            destination_type            = destination_type,
            destination_connection_id   = destination_connection_id,
            destination_config          = destination_config,
        )

        logger.log("INFO", "Data loaded to DB")

        # ── Data-quality gate (optional) ────────────────────────────────
        if quality_connection_id and quality_config:
            try:
                quality_result = _run_quality_gate(
                    connection_id=quality_connection_id,
                    table_name=table_name,
                    quality_config=quality_config,
                    logger=logger,
                )
            except Exception as qe:
                # A malformed quality_config (bad column name, etc.) should
                # never silently swallow a successful load — log it and
                # keep going as if no quality gate had been configured.
                logger.log("ERROR", f"Data quality gate could not run: {qe}")
                quality_result = {"status": "ERROR", "error": str(qe)}

            if (
                quality_result
                and quality_result.get("status") == "FAIL"
                and quality_on_fail == "block"
            ):
                raise RuntimeError(
                    "Data quality gate blocked this run: "
                    f"{quality_result.get('failed', 0)}/{quality_result.get('total_checks', 0)} check(s) failed "
                    f"(quality_run_id={quality_result.get('run_id')}). Rows were already loaded to "
                    f"'{table_name}' — this only marks the ingestion run FAILED so it's visible. "
                    + _first_fix_suggestions(quality_result)
                )

        tracker.end_run(run_id, "SUCCESS", row_count)
        _save_quality_snapshot(pipeline_id, table_name, "SUCCESS", df_quality_result, quality_result)
        return {
            "status": "SUCCESS", "run_id": run_id, "rows": row_count,
            "df_quality": df_quality_result, "quality": quality_result,
        }

    except Exception as e:
        logger.log("ERROR", str(e))
        tracker.end_run(run_id, "FAILED", 0, str(e))
        _save_quality_snapshot(pipeline_id, table_name, "FAILED", df_quality_result, quality_result)

        if not load_attempted:

            log_pipeline_metrics(
                pipeline_id    = pipeline_id,
                table_name     = table_name,
                rows_inserted  = 0,
                duration_sec   = time.time() - start_time,
                connector_type = connector_type,
                file_name      = file_name,
                option         = option,
                status         = "FAILED",
                error_message  = str(e),
            )

        return {
            "status": "FAILED", "run_id": run_id, "error": str(e),
            "df_quality": df_quality_result, "quality": quality_result,
        }

    finally:
        conn.close()