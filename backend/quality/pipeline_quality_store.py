"""
Pipeline Quality Snapshot Store
────────────────────────────────
Every ingest run already computes a df_quality (pre-ingest) and/or quality
(post-load) result — see utils/ingest_runner.py. Those results already carry
a rule-based `fix_suggestion` per failed check (quality/fix_suggestions.py),
but until now the only place they were visible was inside plain-text
pipeline logs.

This module persists the LATEST snapshot per pipeline (one row per run,
queryable by pipeline_id) so the Pipelines page can show a structured
"last run quality" panel — reusing the same QualityGateSummary component
DirectIngest already uses — instead of the person having to read raw logs.

Deliberately its own small table rather than a new column on
pipeline_metrics: pipeline_metrics rows are written by loaders/db_loader.py
DURING load_to_db(), before the quality gates in ingest_runner.py run, so
there's no single row left to update afterward without an awkward
find-and-UPDATE. Writing a fresh row here, once, after both gates have run,
is simpler and always correct.
"""

import json
import os
from datetime import datetime
from typing import Any, Dict, Optional

import psycopg2
import psycopg2.extras

DB_CONFIG = {
    "host":     os.getenv("DB_HOST", "postgres"),
    "database": os.getenv("DB_NAME", "airflow"),
    "user":     os.getenv("DB_USER", "airflow"),
    "password": os.getenv("DB_PASSWORD", "airflow"),
    "port":     os.getenv("DB_PORT", "5432"),
}


def _get_conn():
    return psycopg2.connect(**DB_CONFIG)


def _ensure_table():
    conn = _get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS pipeline_quality_snapshots (
                    id            SERIAL PRIMARY KEY,
                    pipeline_id   VARCHAR(200) NOT NULL,
                    table_name    VARCHAR(160),
                    ingest_status VARCHAR(20),
                    df_quality    JSONB,
                    quality       JSONB,
                    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
                );
                CREATE INDEX IF NOT EXISTS idx_pipeline_quality_snapshots_lookup
                    ON pipeline_quality_snapshots(pipeline_id, id DESC);
            """)
            conn.commit()
    finally:
        conn.close()


def _sanitize(obj):
    """JSON can't encode NaN/Infinity; quality results are pure Python
    dicts/lists/strings/numbers by the time they get here, so this just
    guards against a stray float edge case slipping through."""
    import math
    if isinstance(obj, float):
        return None if (math.isnan(obj) or math.isinf(obj)) else obj
    if isinstance(obj, dict):
        return {k: _sanitize(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_sanitize(v) for v in obj]
    return obj


def save_quality_snapshot(
    pipeline_id: str,
    table_name: Optional[str],
    ingest_status: str,
    df_quality: Optional[Dict[str, Any]] = None,
    quality: Optional[Dict[str, Any]] = None,
) -> None:
    """
    Record this run's quality gate result(s). No-ops (does not write a row)
    if neither gate was configured for this run, so pipelines without any
    quality checks don't accumulate empty snapshot rows.

    Never raises — a failure here should never take down an otherwise-
    successful (or otherwise-already-failed) ingest run.
    """
    if not df_quality and not quality:
        return
    try:
        _ensure_table()
        conn = _get_conn()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO pipeline_quality_snapshots
                        (pipeline_id, table_name, ingest_status, df_quality, quality)
                    VALUES (%s, %s, %s, %s, %s)
                    """,
                    (
                        pipeline_id,
                        table_name,
                        ingest_status,
                        json.dumps(_sanitize(df_quality), default=str) if df_quality else None,
                        json.dumps(_sanitize(quality), default=str) if quality else None,
                    ),
                )
                conn.commit()
        finally:
            conn.close()
    except Exception as e:
        import logging
        logging.warning(f"Could not save pipeline quality snapshot for {pipeline_id!r}: {e}")


def get_latest_quality_snapshot(pipeline_id: str) -> Optional[Dict[str, Any]]:
    """Most recent snapshot for a pipeline, or None if it has never run
    with any quality checks configured."""
    _ensure_table()
    conn = _get_conn()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                SELECT pipeline_id, table_name, ingest_status, df_quality, quality, created_at
                FROM pipeline_quality_snapshots
                WHERE pipeline_id = %s
                ORDER BY id DESC
                LIMIT 1
                """,
                (pipeline_id,),
            )
            row = cur.fetchone()
            if not row:
                return None
            return {
                "pipeline_id":   row["pipeline_id"],
                "table_name":    row["table_name"],
                "ingest_status": row["ingest_status"],
                "df_quality":    row["df_quality"],
                "quality":       row["quality"],
                "created_at":    row["created_at"].isoformat() if row["created_at"] else None,
            }
    finally:
        conn.close()
