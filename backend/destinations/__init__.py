"""
Destination registry — the single place that knows about all five
supported ingest destinations (Postgres, MySQL, Oracle, MongoDB,
Snowflake) and how to resolve a destination's connection config, either
from a saved connection (Connections page / `saved_connections` table) or
from an inline config the caller supplies directly. Mirrors the pattern
reverse_etl/db.py already uses for reverse-ETL destinations
(`resolve_destination_config`) — same idea, same table, applied to ingest.
"""

import json
import os

import psycopg2

from destinations import postgres, mysql, oracle, mongodb, snowflake

# ── Adapter registry ───────────────────────────────────────────────────
# Every adapter module implements the same functions:
#   connect, close, validate_identifier, table_exists, check_schema_mismatch,
#   create_table, evolve_schema, alter_existing_columns_to_custom_schema,
#   insert_data, drop_table, get_last_incremental_value
ADAPTERS = {
    "postgres":  postgres,
    "mysql":     mysql,
    "oracle":    oracle,
    "mongodb":   mongodb,
    "snowflake": snowflake,
}

# What the frontend needs to render a manual-entry destination form per
# type (used by a new /destinations/types endpoint — see main.py wiring).
DESTINATION_FIELDS = {
    "postgres":  ["host", "port", "database", "user", "password"],
    "mysql":     ["host", "port", "database", "user", "password"],
    "oracle":    ["host", "port", "database", "user", "password"],  # database = service name
    "mongodb":   ["connection_string"],  # OR host/port/user/password below
    "snowflake": ["account", "user", "password", "warehouse", "database", "schema", "role"],
}
DESTINATION_LABELS = {
    "postgres": "PostgreSQL", "mysql": "MySQL", "oracle": "Oracle",
    "mongodb": "MongoDB", "snowflake": "Snowflake",
}


def list_supported_destinations() -> list[dict]:
    return [
        {"type": t, "label": DESTINATION_LABELS[t], "fields": DESTINATION_FIELDS[t]}
        for t in ADAPTERS
    ]


def get_adapter(destination_type: str):
    destination_type = (destination_type or "postgres").lower()
    adapter = ADAPTERS.get(destination_type)
    if adapter is None:
        raise ValueError(
            f"Unsupported destination_type '{destination_type}'. "
            f"Supported: {', '.join(sorted(ADAPTERS))}"
        )
    return adapter


# ── Saved-connection resolution ─────────────────────────────────────────
# Reads from the SAME app metadata Postgres (env-configured) that
# main.py's saved_connections table already lives in — this is the app's
# own internal store, unrelated to whichever engine the user picks as
# their destination.
_APP_DB_CONFIG = {
    "host":     os.getenv("DB_HOST", "postgres"),
    "database": os.getenv("DB_NAME", "airflow"),
    "user":     os.getenv("DB_USER", "airflow"),
    "password": os.getenv("DB_PASSWORD", "airflow"),
    "port":     os.getenv("DB_PORT", "5432"),
}


def _app_conn():
    return psycopg2.connect(**_APP_DB_CONFIG)


def resolve_destination_config(connection_id: int | None, inline_config: dict | None) -> dict:
    """A saved connection's stored credentials win when connection_id is
    given; any fields also present in inline_config fill in what the saved
    connection doesn't have (e.g. a saved connection missing `database`
    while the caller specifies which database/table to target). With no
    connection_id, inline_config alone is used (pure manual entry)."""
    if not connection_id:
        return dict(inline_config or {})

    conn = _app_conn()
    try:
        cur = conn.cursor()
        cur.execute("SELECT config FROM saved_connections WHERE id = %s", (connection_id,))
        row = cur.fetchone()
    finally:
        conn.close()

    if not row:
        raise ValueError(f"Saved connection {connection_id} not found")

    saved_config = row[0] if isinstance(row[0], dict) else json.loads(row[0])
    merged = dict(inline_config or {})
    # Saved credentials take priority over any inline duplicate — the
    # saved connection is the source of truth once it's picked.
    merged.update({k: v for k, v in saved_config.items() if v not in (None, "")})
    return merged
