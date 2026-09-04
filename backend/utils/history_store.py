"""
Generic version-history store, shared by Pipelines, Reverse ETL, and
SQL saved queries.

Modeled directly on agent/dashboard_store.py's dashboard_history pattern:
  - push a snapshot of the state being REPLACED, before every destructive edit
  - cap history at HISTORY_LIMIT entries per (entity_type, entity_id)
  - list_history() is lightweight (no payload) for the version-list UI
  - restoring a version discards that version AND everything after it —
    there is no redo, same as dashboards. This keeps the semantics identical
    across all three features instead of drifting into per-feature behavior.

Why one table instead of three:
  push/list/discard logic is identical regardless of what's being versioned.
  Only two things differ per entity type, and both are handled by the caller,
  not this module:
    1. what a "snapshot" contains (a JSON config dict, and — for pipelines,
       where credentials live only in the live .py file — optionally the
       raw file text too, since re-rendering from config alone would drop
       passwords that list_dag_files() deliberately never returns)
    2. how a snapshot gets "applied back" (rewrite DAG file / UPDATE a row /
       UPDATE query_text) — that's inherently feature-specific and stays in
       each router.
"""

import json
import os
from datetime import datetime
from typing import Optional

import psycopg2
import psycopg2.extras
import psycopg2.extensions

DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "port": int(os.getenv("DB_PORT", "5432")),
    "dbname": os.getenv("DB_NAME", "airflow"),
    "user": os.getenv("DB_USER", "airflow"),
    "password": os.getenv("DB_PASSWORD", "airflow"),
}

HISTORY_LIMIT = 20

_conn: Optional[psycopg2.extensions.connection] = None


def _get_conn() -> psycopg2.extensions.connection:
    global _conn
    if _conn is None or _conn.closed:
        _conn = psycopg2.connect(**DB_CONFIG, connect_timeout=5)
    elif _conn.get_transaction_status() == psycopg2.extensions.TRANSACTION_STATUS_INERROR:
        _conn.rollback()
    return _conn


def _init_db():
    conn = _get_conn()
    with conn.cursor() as cur:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS entity_history (
                id           SERIAL PRIMARY KEY,
                entity_type  VARCHAR(30)  NOT NULL,   -- 'pipeline' | 'reverse_etl' | 'sql_query'
                entity_id    VARCHAR(200) NOT NULL,   -- pipeline_name / reverse_etl name / query id
                config       JSONB NOT NULL,          -- snapshot of the state being replaced
                raw_content  TEXT,                    -- pipeline-only: exact .py file text (preserves secrets)
                label        TEXT,                    -- "Edited schedule", "Changed query", etc.
                created_by   VARCHAR(100),
                created_at   TIMESTAMP DEFAULT NOW()
            );
            CREATE INDEX IF NOT EXISTS idx_entity_history_lookup
                ON entity_history(entity_type, entity_id, id DESC);
        """)
        conn.commit()


def _sanitize_for_json(obj):
    import math
    if isinstance(obj, float):
        return None if (math.isnan(obj) or math.isinf(obj)) else obj
    if isinstance(obj, dict):
        return {k: _sanitize_for_json(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_sanitize_for_json(v) for v in obj]
    return obj


def push_history(
    entity_type: str,
    entity_id: str,
    config: dict,
    label: str | None = None,
    raw_content: str | None = None,
    created_by: str | None = None,
) -> int:
    """
    Record the state being replaced, BEFORE the caller overwrites it.

    Returns the new history row's id. Call this from inside the same
    request that performs the destructive write, right before the write —
    never after, or a crash mid-write leaves no snapshot to recover from.
    """
    conn = _get_conn()
    clean_config = _sanitize_for_json(config)
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO entity_history
                    (entity_type, entity_id, config, raw_content, label, created_by)
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING id
                """,
                (
                    entity_type,
                    entity_id,
                    json.dumps(clean_config, default=str),
                    raw_content,
                    label,
                    created_by,
                ),
            )
            new_id = cur.fetchone()[0]

            # Keep the log bounded; old versions aren't worth unbounded storage.
            cur.execute(
                """
                DELETE FROM entity_history
                WHERE entity_type = %s AND entity_id = %s AND id NOT IN (
                    SELECT id FROM entity_history
                    WHERE entity_type = %s AND entity_id = %s
                    ORDER BY id DESC LIMIT %s
                )
                """,
                (entity_type, entity_id, entity_type, entity_id, HISTORY_LIMIT),
            )
            conn.commit()
        return new_id
    except Exception:
        conn.rollback()
        raise


def list_history(entity_type: str, entity_id: str) -> list[dict]:
    """Version log, newest first. Snapshots are omitted — they're large; fetch one via get_version()."""
    conn = _get_conn()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                SELECT id, label, created_by, created_at
                FROM entity_history
                WHERE entity_type = %s AND entity_id = %s
                ORDER BY id DESC
                """,
                (entity_type, entity_id),
            )
            return [
                {
                    "version_id": row["id"],
                    "label": row["label"],
                    "created_by": row["created_by"],
                    "created_at": row["created_at"].isoformat() if row["created_at"] else None,
                }
                for row in cur.fetchall()
            ]
    except Exception:
        conn.rollback()
        raise


def get_version(entity_type: str, entity_id: str, version_id: int) -> dict | None:
    """Fetch one snapshot in full (config + raw_content), for the caller to apply."""
    conn = _get_conn()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                SELECT id, config, raw_content, label, created_at
                FROM entity_history
                WHERE entity_type = %s AND entity_id = %s AND id = %s
                """,
                (entity_type, entity_id, version_id),
            )
            row = cur.fetchone()
            if not row:
                return None
            return {
                "version_id": row["id"],
                "config": row["config"],
                "raw_content": row["raw_content"],
                "label": row["label"],
                "created_at": row["created_at"].isoformat() if row["created_at"] else None,
            }
    except Exception:
        conn.rollback()
        raise


def discard_from(entity_type: str, entity_id: str, version_id: int):
    """
    Call AFTER successfully applying a restore: deletes the restored version
    and everything newer than it. Matches dashboard_history's semantics —
    rewinding discards the abandoned future, so there's no redo. Do this
    last, only once the restore actually succeeded, so a failed restore
    doesn't destroy the version you were trying to recover.
    """
    conn = _get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM entity_history WHERE entity_type = %s AND entity_id = %s AND id >= %s",
                (entity_type, entity_id, version_id),
            )
            conn.commit()
    except Exception:
        conn.rollback()
        raise


def rename_entity_id(entity_type: str, old_entity_id: str, new_entity_id: str):
    """If an entity can ever be renamed, carry its history over instead of orphaning it."""
    conn = _get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE entity_history SET entity_id = %s WHERE entity_type = %s AND entity_id = %s",
                (new_entity_id, entity_type, old_entity_id),
            )
            conn.commit()
    except Exception:
        conn.rollback()
        raise


try:
    _init_db()
except Exception as e:
    import logging
    logging.warning(f"Failed to initialize entity_history store: {e}")
