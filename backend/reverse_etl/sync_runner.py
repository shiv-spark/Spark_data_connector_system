"""
Orchestrates one reverse-ETL sync: extract from warehouse -> apply field
mapping -> write to destination -> track run/log/metrics.

Deliberately mirrors utils/ingest_runner.py's shape (RunTracker + DBLogger +
log_pipeline_metrics + lineage) so every existing Logs / Metrics / Lineage
page keeps working for reverse syncs without any changes — they just see a
connector_name/connector_type like "reverse_salesforce" instead of
"SalesforceConnector".
"""

import time
import psycopg2

from reverse_etl.db import DB_CONFIG, resolve_destination_config, update_bookmark
from reverse_etl.extractor import extract_from_warehouse, latest_incremental_value
from reverse_etl.writers import WRITER_MAP, VALID_DESTINATIONS
from utils.run_tracker import RunTracker
from utils.logger import DBLogger
from loaders.db_loader import log_pipeline_metrics


def _apply_field_mapping(df, field_mapping: dict):
    if field_mapping:
        rename = {src: dst for src, dst in field_mapping.items() if src in df.columns}
        df = df.select(list(rename.keys())).rename(rename) if rename else df
    return df


def run_reverse_sync(
    pipeline_name: str,
    destination_type: str,
    destination_object: str,
    source_table: str | None = None,
    source_query: str | None = None,
    filter_sql: str | None = None,
    connection_id: int | None = None,
    destination_config: dict | None = None,
    field_mapping: dict | None = None,
    upsert_key: str | None = None,
    write_mode: str = "upsert",
    batch_size: int = 200,
    sync_mode: str = "full",
    incremental_column: str | None = None,
    last_synced_value=None,
) -> dict:

    if destination_type not in VALID_DESTINATIONS:
        raise ValueError(f"Unknown destination_type '{destination_type}'. Valid: {sorted(VALID_DESTINATIONS)}")

    conn = psycopg2.connect(**DB_CONFIG)
    tracker = RunTracker(conn)
    source_label = source_table or "(custom query)"
    run_id = tracker.start_run(f"reverse_{destination_type}", f"{source_label} -> {destination_type}:{destination_object}")
    logger = DBLogger(conn, run_id)

    connector_type = f"reverse_{destination_type}"
    start_time = time.time()

    try:
        logger.log("INFO", f"Reverse ETL sync started | pipeline={pipeline_name} | mode={sync_mode}")

        last_value = last_synced_value if sync_mode == "incremental" else None
        df = extract_from_warehouse(
            source_table=source_table, source_query=source_query,
            filter_sql=filter_sql, incremental_column=incremental_column,
            last_value=last_value,
        )
        row_count = df.shape[0]
        logger.log("INFO", f"Extracted {row_count} row(s) from warehouse")

        if row_count == 0:
            tracker.end_run(run_id, "SUCCESS", 0)
            log_pipeline_metrics(
                pipeline_id=f"reverse_{pipeline_name}", table_name=destination_object,
                rows_inserted=0, duration_sec=time.time() - start_time,
                connector_type=connector_type, file_name=source_label,
                option=write_mode, status="SKIPPED",
            )
            return {"status": "SUCCESS", "run_id": run_id, "rows_read": 0, "rows_written": 0, "message": "No new rows to sync"}

        df = _apply_field_mapping(df, field_mapping or {})
        records = df.to_dicts()

        config = resolve_destination_config(connection_id, destination_config)
        writer = WRITER_MAP[destination_type]
        result = writer(records, config, destination_object, upsert_key, write_mode, batch_size)

        logger.log("INFO", f"Wrote {result['success']} row(s), {result['failed']} failed, to {destination_type}:{destination_object}")
        for err in result.get("errors", [])[:10]:
            logger.log("WARNING", f"[{destination_type}] {err}")

        status = "SUCCESS" if result["failed"] == 0 else ("FAILED" if result["success"] == 0 else "PARTIAL")
        tracker.end_run(run_id, status, result["success"], "; ".join(result.get("errors", [])[:5]) or None)

        log_pipeline_metrics(
            pipeline_id=f"reverse_{pipeline_name}", table_name=destination_object,
            rows_inserted=result["success"], rows_failed=result["failed"],
            duration_sec=time.time() - start_time, connector_type=connector_type,
            file_name=source_label, option=write_mode, status=status,
            error_message="; ".join(result.get("errors", [])[:5]) or None,
        )

        try:
            from lineage.router import record_lineage
            record_lineage(
                connector_type=connector_type,
                source_name=source_label,
                table_name=f"{destination_type}:{destination_object}",
                pipeline_id=f"reverse_{pipeline_name}",
                columns=list(df.columns),
                rows_loaded=result["success"],
                status=status,
            )
        except Exception as lineage_err:
            print(f"[lineage] skipped for reverse sync (non-fatal): {lineage_err}")

        if sync_mode == "incremental" and incremental_column and status != "FAILED":
            new_bookmark = latest_incremental_value(df, incremental_column)
            if new_bookmark is not None:
                update_bookmark(pipeline_name, new_bookmark)

        return {
            "status": status, "run_id": run_id,
            "rows_read": row_count, "rows_written": result["success"],
            "rows_failed": result["failed"], "errors": result.get("errors", []),
        }

    except Exception as e:
        logger.log("ERROR", str(e))
        tracker.end_run(run_id, "FAILED", 0, str(e))
        log_pipeline_metrics(
            pipeline_id=f"reverse_{pipeline_name}", table_name=destination_object,
            rows_inserted=0, duration_sec=time.time() - start_time,
            connector_type=connector_type, file_name=source_label,
            option=write_mode, status="FAILED", error_message=str(e),
        )
        return {"status": "FAILED", "run_id": run_id, "error": str(e)}

    finally:
        conn.close()
