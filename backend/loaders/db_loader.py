"""
Generic multi-destination loader.

load_to_db() used to talk to Postgres ONLY (hardcoded psycopg2.connect).
It now dispatches to whichever destination adapter matches
`destination_type` (postgres / mysql / oracle / mongodb / snowflake) — see
destinations/__init__.py for the adapter registry and
destinations/{postgres,mysql,oracle,mongodb,snowflake}.py for each
engine's implementation. All the orchestration logic that used to live
directly in this file (schema-mismatch thresholds, schema evolution,
custom-schema coercion, incremental sync, batched insert, metrics
logging, lineage capture) is UNCHANGED — only the actual DB calls were
extracted into the adapters so they can target five engines instead of one.

Backward compatible: called with no destination_type/destination_config
(as every existing caller does today), this behaves EXACTLY as before —
same env-configured Postgres warehouse, same custom_schema_sql behavior.
"""

import json
import re
import time
from pathlib import Path

import numpy as np
import pandas as pd
import polars as pl
import psycopg2
from dotenv import load_dotenv

from destinations import get_adapter, resolve_destination_config
from destinations import postgres as _pg_adapter

project_root = Path(__file__).parent.parent.parent
load_dotenv(project_root / ".env")

import os

# Legacy default — the app's original single hardcoded Postgres warehouse.
# Still used whenever destination_type="postgres" (the default) AND no
# destination_connection_id / destination_config is supplied, so every
# existing caller (ingest_runner.py, generated Airflow DAGs, etc.) keeps
# writing to exactly the same place it always has.
DB_CONFIG = {
    "host":     os.getenv("DB_HOST",     "postgres"),
    "database": os.getenv("DB_NAME",     "airflow"),
    "user":     os.getenv("DB_USER",     "airflow"),
    "password": os.getenv("DB_PASSWORD", "airflow"),
    "port":     os.getenv("DB_PORT",     "5432"),
}


def get_metrics_conn():
    """Connection to the app's OWN metadata Postgres, used for
    pipeline_metrics / lineage — always Postgres, regardless of what
    destination_type this run's data was loaded into."""
    return psycopg2.connect(**DB_CONFIG)


# ─────────────────────────────────────────────
# CLEAN COLUMN NAMES
# ─────────────────────────────────────────────

def clean_column(name):
    name = str(name).lower().strip()
    name = re.sub(r"[^\w]+", "_", name)
    name = re.sub(r"^_+|_+$", "", name)
    if re.match(r"^\d", name):
        name = f"col_{name}"
    return name or "unnamed"


# ─────────────────────────────────────────────
# VALIDATE TABLE NAME (legacy default — Postgres rules). New code should
# prefer the destination-specific adapter.validate_identifier(), which
# load_to_db() below already uses; this is kept only because it's a public
# name other modules could theoretically still import.
# ─────────────────────────────────────────────

def validate_table_name(table_name: str):
    if not table_name:
        raise ValueError(
            "table_name will be required for all connector types in future, so please provide "
            "a valid table_name in your config. It should contain only letters, numbers, and "
            "underscores, and must start with a letter or underscore."
        )
    if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', table_name):
        raise ValueError(
            f"Invalid table_name '{table_name}' — only letters, numbers, and underscores are allowed"
        )
    if len(table_name) > 63:
        raise ValueError(f"table_name cannot be longer than 63 characters")


# ─────────────────────────────────────────────
# Observability: Log pipeline metrics to a separate table
# (ALWAYS the app's own metadata Postgres — not the destination — so the
# Pipelines/Metrics dashboard has one consistent place to read from no
# matter which engine any given run's data landed in.)
# ─────────────────────────────────────────────

def log_pipeline_metrics(
    pipeline_id,
    table_name,
    rows_inserted=0,
    rows_skipped=0,
    rows_failed=0,
    duration_sec=0.0,
    evolved_columns=None,
    match_pct=100.0,
    file_name=None,
    connector_type=None,
    option=None,
    status="SUCCESS",
    error_message=None,
    destination_type=None,
):
    try:
        conn = get_metrics_conn()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO pipeline_metrics (
                pipeline_id, table_name, rows_inserted, rows_skipped,
                rows_failed, duration_sec, evolved_columns, match_pct,
                file_name, connector_type, option, status, error_message
            ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """, (
            pipeline_id, table_name, rows_inserted, rows_skipped, rows_failed,
            round(duration_sec, 2), evolved_columns or [], match_pct, file_name,
            connector_type, option, status, error_message,
        ))
        conn.commit()
        cursor.close()
        conn.close()
        print(f"Metrics logged — {rows_inserted} rows | {duration_sec:.2f}s | {status}"
              + (f" | destination={destination_type}" if destination_type else ""))
    except Exception as e:
        print(f"Metrics log failed: {e}")  # metrics logging failure should never break the main pipeline


# ─────────────────────────────────────────────
# INCREMENTAL SYNC helpers (destination-agnostic — operate on the
# in-memory DataFrame; the "last value" itself comes from the adapter)
# ─────────────────────────────────────────────

def filter_incremental(df, incremental_column: str, last_value):
    if last_value is None:
        print("No last value found — full load will be performed")
        return df

    if isinstance(df, pl.DataFrame):
        original_count = df.shape[0]
        df = df.filter(pl.col(incremental_column) > last_value)
        print(f"Incremental filter — {original_count} → {df.shape[0]} rows (new only)")
    elif isinstance(df, pd.DataFrame):
        original_count = df.shape[0]
        df = df[df[incremental_column] > last_value]
        print(f"Incremental filter — {original_count} → {df.shape[0]} rows (new only)")

    return df


def _commit(conn):
    commit_fn = getattr(conn, "commit", None)
    if callable(commit_fn):
        commit_fn()


def _rollback(conn):
    rollback_fn = getattr(conn, "rollback", None)
    if callable(rollback_fn):
        try:
            rollback_fn()
        except Exception:
            pass


# ─────────────────────────────────────────────
# MAIN LOAD FUNCTION
# ─────────────────────────────────────────────

def load_to_db(df, option=None, table_name=None,
                pipeline_id=None, connector_type=None, file_name=None,
                sync_mode="full", incremental_column=None,
                custom_schema_sql=None,   # deprecated — native Postgres SQL types, kept for backward compat
                custom_schema=None,       # preferred — CANONICAL types (see utils/schema_applier.py),
                                           # works with every destination, not just Postgres
                destination_type="postgres",
                destination_connection_id=None,
                destination_config=None):
    """
    destination_type          : "postgres" (default) | "mysql" | "oracle" | "mongodb" | "snowflake"
    destination_connection_id : id of a row in saved_connections to use as the destination's
                                 credentials (from the Connections page) — takes priority
    destination_config        : inline {host, database, user, password, port, ...} (or the
                                 engine-specific equivalent — see destinations/__init__.DESTINATION_FIELDS)
                                 used when destination_connection_id is not supplied, or to fill in
                                 fields (e.g. which database/table to target) a saved connection doesn't carry

    With destination_type="postgres" and neither of the two destination_* params set, this behaves
    exactly as the original single-warehouse implementation always did.
    """
    adapter = get_adapter(destination_type)
    adapter.validate_identifier(table_name)

    # ── Resolve custom_schema to the CANONICAL form every adapter expects ──
    # Old callers pass custom_schema_sql (native Postgres SQL type strings,
    # e.g. {"amount": "DOUBLE PRECISION"}) — convert those back to canonical
    # once here so every adapter (including Postgres itself) only ever has
    # to deal with one representation.
    custom_schema_canonical = custom_schema
    if custom_schema_canonical is None and custom_schema_sql:
        custom_schema_canonical = {
            col: _pg_adapter._NATIVE_TO_CANONICAL.get(t, "text")
            for col, t in custom_schema_sql.items()
        }

    # ── Resolve destination connection ──────────────────────────────────
    resolved_config = resolve_destination_config(destination_connection_id, destination_config)
    if destination_type == "postgres" and not resolved_config:
        # Legacy default: no destination specified at all -> the app's
        # single original hardcoded warehouse, unchanged from before.
        resolved_config = DB_CONFIG

    conn = adapter.connect(resolved_config)

    if isinstance(df, pl.DataFrame):
        df = df.rename({col: clean_column(col) for col in df.columns})
        pdf = df.to_pandas()
    else:
        df.columns = [clean_column(c) for c in df.columns]
        pdf = df

    print(f"Destination : {destination_type}")
    print(f"Columns     : {list(pdf.columns)}")
    print(f"Sync mode   : {sync_mode}")

    evolved_cols = []
    match_pct = 100.0
    start_time = time.time()

    try:
        # ── INCREMENTAL FILTER ───────────────────────────
        if sync_mode == "incremental" and incremental_column:
            if incremental_column not in pdf.columns:
                raise ValueError(
                    f"incremental_column '{incremental_column}' not found in data. "
                    f"Available: {list(pdf.columns)}"
                )

            if adapter.table_exists(conn, table_name):
                last_value = adapter.get_last_incremental_value(conn, table_name, incremental_column)
                pdf = filter_incremental(pdf, incremental_column, last_value)

                if pdf.shape[0] == 0:
                    print("No new rows found — skipping insert")
                    adapter.close(conn)
                    log_pipeline_metrics(
                        pipeline_id=pipeline_id or f"pipeline_{table_name}", table_name=table_name,
                        rows_inserted=0, rows_skipped=0, duration_sec=time.time() - start_time,
                        connector_type=connector_type, file_name=file_name, option=option,
                        status="SKIPPED", destination_type=destination_type,
                    )
                    return
            else:
                print("Table not found for incremental load — full load will be performed")

        # ── OPTION 1 — APPEND ────────────────────────────
        if option == "1":
            if not adapter.table_exists(conn, table_name):
                adapter.create_table(conn, pdf, table_name, custom_schema=custom_schema_canonical)
            else:
                if custom_schema_canonical:
                    altered, warnings = adapter.alter_existing_columns_to_custom_schema(
                        conn, table_name, custom_schema_canonical
                    )
                    if altered:
                        print(f"Custom schema — existing columns retyped: {altered}")
                    for w in warnings:
                        print(f"Custom schema — {w}")

                report = adapter.check_schema_mismatch(conn, pdf, table_name)
                match_pct = report["match_pct"]

                if match_pct == 0:
                    raise ValueError(
                        f"0% column match — Seems like a different file. "
                        f"DB columns: {report['matched']} | File columns: {list(pdf.columns)}"
                    )

                if match_pct < 50:
                    print(
                        f"WARNING: Only {match_pct}% columns match. "
                        f"Missing: {report['missing_in_file']} | Extra: {report['extra_in_file']}"
                    )

                if match_pct >= 80:
                    evolved_cols = adapter.evolve_schema(conn, pdf, table_name, custom_schema=custom_schema_canonical)
                    if evolved_cols:
                        print(f"Schema evolved ({match_pct}% match): {evolved_cols}")
                elif 50 <= match_pct < 80:
                    evolved_cols = adapter.evolve_schema(conn, pdf, table_name, custom_schema=custom_schema_canonical)
                    print(f"CAUTION: Schema evolved at only {match_pct}% match. New columns added: {evolved_cols}. Verify the file.")
                else:
                    evolved_cols = []
                    print(f"Schema evolution SKIPPED: {match_pct}% match too low. Only matching columns will be inserted.")
                    matched_cols = list(report["matched"])
                    pdf = pdf[matched_cols]

            adapter.insert_data(conn, pdf, table_name, custom_schema=custom_schema_canonical)

        # ── OPTION 2 — OVERWRITE ─────────────────────────
        elif option == "2":
            if sync_mode == "incremental":
                raise ValueError("option=2 (overwrite) not supported with incremental sync — use option=1.")
            if adapter.table_exists(conn, table_name):
                adapter.drop_table(conn, table_name)
            adapter.create_table(conn, pdf, table_name, custom_schema=custom_schema_canonical)
            adapter.insert_data(conn, pdf, table_name, custom_schema=custom_schema_canonical)

        # ── OPTION 3 — CREATE ONLY ───────────────────────
        elif option == "3":
            if adapter.table_exists(conn, table_name):
                raise ValueError(f"Table '{table_name}' already exists.")
            adapter.create_table(conn, pdf, table_name, custom_schema=custom_schema_canonical)
            adapter.insert_data(conn, pdf, table_name, custom_schema=custom_schema_canonical)

        else:
            raise ValueError(f"Invalid option '{option}'")

        _commit(conn)
        duration = time.time() - start_time
        print(f"Committed — {pdf.shape[0]} rows | {duration:.2f}s")

        log_pipeline_metrics(
            pipeline_id=pipeline_id or f"pipeline_{table_name}", table_name=table_name,
            rows_inserted=pdf.shape[0], duration_sec=duration, evolved_columns=evolved_cols,
            match_pct=match_pct, file_name=file_name, connector_type=connector_type,
            option=option, status="SUCCESS", destination_type=destination_type,
        )

        # ── Lineage capture — one hook point covers every connector AND
        # every destination, since they all funnel through this same
        # load_to_db() success path. Lineage is stored in the app's own
        # metadata store, independent of destination_type. ──────────────
        try:
            from lineage.router import record_lineage
            record_lineage(
                connector_type=connector_type, source_name=file_name, table_name=table_name,
                pipeline_id=pipeline_id or f"pipeline_{table_name}", columns=list(pdf.columns),
                rows_loaded=pdf.shape[0], status="SUCCESS",
            )
        except Exception as lineage_err:
            print(f"[lineage] skipped for this run (non-fatal): {lineage_err}")

        print("\nPipeline completed successfully!")

    except Exception as e:
        _rollback(conn)
        duration = time.time() - start_time
        print(f"ROLLBACK: {e}")
        log_pipeline_metrics(
            pipeline_id=pipeline_id or f"pipeline_{table_name}", table_name=table_name,
            rows_inserted=0, duration_sec=duration, connector_type=connector_type,
            file_name=file_name, option=option, status="FAILED", error_message=str(e),
            destination_type=destination_type,
        )
        try:
            from lineage.router import record_lineage
            record_lineage(
                connector_type=connector_type, source_name=file_name, table_name=table_name,
                pipeline_id=pipeline_id or f"pipeline_{table_name}", columns=None,
                rows_loaded=0, status="FAILED",
            )
        except Exception as lineage_err:
            print(f"[lineage] skipped for this run (non-fatal): {lineage_err}")

        raise

    finally:
        adapter.close(conn)
