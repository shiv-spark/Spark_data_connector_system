"""
Shared DB helpers for the Reverse ETL module.

Reuses the SAME central warehouse Postgres ("airflow" DB) that the rest of
the platform already writes to via loaders/db_loader1.py — that warehouse is
both the destination of forward ingestion AND the *source* of reverse ETL.
"""

import os
import json
import psycopg2
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


def get_conn():
    return psycopg2.connect(**DB_CONFIG)


def ensure_reverse_etl_tables():
    """Creates the reverse-ETL pipeline-definition table if missing.

    Run history/logs deliberately reuse the EXISTING pipeline_runs /
    pipeline_logs / pipeline_metrics tables (same ones utils/run_tracker.py,
    utils/logger.py and loaders/db_loader1.log_pipeline_metrics already
    write to for forward ingestion) so the Logs/Metrics pages keep working
    unmodified for reverse syncs too — they're just rows with a
    connector_name/connector_type that starts with "reverse_".
    """
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS reverse_etl_pipelines (
            id                  SERIAL PRIMARY KEY,
            pipeline_name       VARCHAR(200) UNIQUE NOT NULL,

            -- source side: always reads from the warehouse Postgres itself
            source_table        VARCHAR(200),
            source_query        TEXT,             -- advanced: raw SELECT, overrides source_table
            filter_sql          TEXT,             -- optional WHERE clause (no "WHERE" keyword) applied to source_table

            -- destination side
            destination_type    VARCHAR(50)  NOT NULL,   -- postgres | mysql | salesforce | hubspot | google_sheets | webhook
            connection_id       INTEGER REFERENCES saved_connections(id) ON DELETE SET NULL,
            destination_config  JSONB DEFAULT '{}'::jsonb,   -- used when connection_id is not supplied
            destination_object  VARCHAR(300),     -- table name / SF object / HubSpot object type / sheet name / webhook URL

            field_mapping       JSONB DEFAULT '{}'::jsonb,   -- {source_column: destination_field}; empty = 1:1 same-name
            upsert_key          VARCHAR(200),                -- destination field used to match existing records
            write_mode          VARCHAR(20) DEFAULT 'upsert',-- insert | upsert | update
            batch_size          INTEGER DEFAULT 200,

            sync_mode           VARCHAR(20) DEFAULT 'full',  -- full | incremental
            incremental_column  VARCHAR(200),                -- column on source_table, e.g. updated_at
            last_synced_value   TEXT,                        -- bookmark, persisted after each successful incremental run

            schedule            VARCHAR(100) DEFAULT '*/15 * * * *',
            timezone            VARCHAR(50)  DEFAULT 'Asia/Kolkata',
            status              VARCHAR(30)  DEFAULT 'created',

            created_at          TIMESTAMP DEFAULT NOW(),
            updated_at          TIMESTAMP DEFAULT NOW()
        )
    """)
    conn.commit()
    cur.close()
    conn.close()


def get_pipeline(pipeline_name: str) -> dict | None:
    ensure_reverse_etl_tables()
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM reverse_etl_pipelines WHERE pipeline_name = %s", (pipeline_name,))
    row = cur.fetchone()
    if not row:
        cur.close(); conn.close()
        return None
    cols = [d[0] for d in cur.description]
    data = dict(zip(cols, row))
    cur.close(); conn.close()
    return data


def update_bookmark(pipeline_name: str, value):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "UPDATE reverse_etl_pipelines SET last_synced_value = %s, updated_at = NOW() WHERE pipeline_name = %s",
        (str(value) if value is not None else None, pipeline_name),
    )
    conn.commit()
    cur.close(); conn.close()


def resolve_destination_config(connection_id: int | None, inline_config: dict | None) -> dict:
    """Same pattern main.py already uses for source connections
    (_resolve_saved_connection): a saved connection's real credentials win
    when connection_id is given, otherwise fall back to inline config the
    caller supplied directly."""
    if not connection_id:
        return inline_config or {}

    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT config FROM saved_connections WHERE id = %s", (connection_id,))
    row = cur.fetchone()
    cur.close(); conn.close()
    if not row:
        raise ValueError(f"Saved connection {connection_id} not found")
    config = row[0] if isinstance(row[0], dict) else json.loads(row[0])
    merged = dict(inline_config or {})
    merged.update({k: v for k, v in config.items() if v not in (None, "")})
    return merged
