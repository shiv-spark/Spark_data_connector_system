"""
dashboard_store.py
Dashboard state persistence using PostgreSQL.
Uses saved_dashboards table to store dashboard state as JSON.
"""

import hashlib
import json
from datetime import datetime
from typing import Optional

import os
import hashlib
import json
from datetime import datetime
from typing import Optional

import psycopg2
import psycopg2.extras
import psycopg2.extensions

# Use the same DB config as main.py
DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "port": int(os.getenv("DB_PORT", "5432")),
    "dbname": os.getenv("DB_NAME", "airflow"),
    "user": os.getenv("DB_USER", "airflow"),
    "password": os.getenv("DB_PASSWORD", "airflow"),
}

# { dashboard_id: { ...full state... } }
_store: dict = {}

_conn: Optional[psycopg2.extensions.connection] = None


def _get_conn() -> psycopg2.extensions.connection:
    global _conn
    if _conn is None or _conn.closed:
        _conn = psycopg2.connect(**DB_CONFIG, connect_timeout=5)
    elif _conn.get_transaction_status() == psycopg2.extensions.TRANSACTION_STATUS_INERROR:
        _conn.rollback()
    return _conn


def _init_db():
    """Create the saved_dashboards table if it doesn't exist."""
    conn = _get_conn()
    with conn.cursor() as cur:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS saved_dashboards (
                id SERIAL PRIMARY KEY,
                dashboard_id VARCHAR(255) UNIQUE NOT NULL,
                state JSONB NOT NULL,
                last_updated TIMESTAMP DEFAULT NOW()
            );
            CREATE INDEX IF NOT EXISTS idx_saved_dashboards_dashboard_id ON saved_dashboards(dashboard_id);
        """)
        conn.commit()


def _load_all_from_db():
    """Load all dashboards from DB into memory on startup."""
    global _store
    conn = _get_conn()
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute("SELECT dashboard_id, state, last_updated FROM saved_dashboards")
        rows = cur.fetchall()
        _store = {}
        for row in rows:
            state = dict(row["state"])
            state["last_updated"] = row["last_updated"].isoformat() if row["last_updated"] else None
            _store[row["dashboard_id"]] = state


# def save_dashboard(dashboard_id: str, state: dict):
#     """Save dashboard state to both memory and DB."""
#     conn = _get_conn()
#     state_with_time = {
#         **state,
#         "last_updated": datetime.utcnow().isoformat(),
#     }
#     _store[dashboard_id] = state_with_time
#     with conn.cursor() as cur:
#         cur.execute("""
#             INSERT INTO saved_dashboards (dashboard_id, state, last_updated)
#             VALUES (%s, %s, NOW())
#             ON CONFLICT (dashboard_id) DO UPDATE SET
#                 state = EXCLUDED.state,
#                 last_updated = NOW()
#         """, (dashboard_id, json.dumps(state, default=str)))
#         conn.commit()


def _sanitize_for_json(obj):
    import math
    if isinstance(obj, float):
        return None if (math.isnan(obj) or math.isinf(obj)) else obj
    if isinstance(obj, dict):
        return {k: _sanitize_for_json(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_sanitize_for_json(v) for v in obj]
    return obj

def save_dashboard(dashboard_id: str, state: dict):
    """Save dashboard state to both memory and DB."""
    conn = _get_conn()
    clean_state = _sanitize_for_json(state)
    state_with_time = {
        **clean_state,
        "last_updated": datetime.utcnow().isoformat(),
    }
    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO saved_dashboards (dashboard_id, state, last_updated)
                VALUES (%s, %s, NOW())
                ON CONFLICT (dashboard_id) DO UPDATE SET
                    state = EXCLUDED.state,
                    last_updated = NOW()
            """, (dashboard_id, json.dumps(clean_state, default=str)))
            conn.commit()
        _store[dashboard_id] = state_with_time
    except Exception:
        conn.rollback()
        raise


def get_dashboard(dashboard_id: str) -> dict | None:
    """Get dashboard from memory (already loaded from DB on startup)."""
    return _store.get(dashboard_id)


def get_dashboard_by_name(name: str) -> str | None:
    """Get dashboard_id by name (case-insensitive). Returns None if not found."""
    name_lower = name.lower()
    for did, s in _store.items():
        if s.get("display_name", "").lower() == name_lower:
            return did
    return None


def get_all_dashboard_names() -> list[str]:
    """Get all dashboard names (case-normalized for comparison)."""
    return [
        {"dashboard_id": did, "name": s.get("display_name", did)}
        for did, s in _store.items()
    ]


def list_dashboards() -> list[dict]:
    """List all dashboards from memory."""
    return [
        {
            "dashboard_id": did,
            "name":         s.get("display_name", did),
            "source_type":  s.get("source_type"),
            "last_updated": s.get("last_updated"),
            "quality_score":s.get("quality_result", {}).get("quality_score"),
            "grade":        s.get("quality_result", {}).get("grade"),
        }
        for did, s in _store.items()
    ]


# def delete_dashboard(dashboard_id: str) -> bool:
#     """Delete a dashboard from both memory and DB."""
#     conn = _get_conn()
#     if dashboard_id in _store:
#         del _store[dashboard_id]
#     with conn.cursor() as cur:
#         cur.execute("DELETE FROM saved_dashboards WHERE dashboard_id = %s", (dashboard_id,))
#         conn.commit()
#         return cur.rowcount > 0

def delete_dashboard(dashboard_id: str) -> bool:
    """Delete a dashboard from both memory and DB."""
    conn = _get_conn()
    if dashboard_id in _store:
        del _store[dashboard_id]
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM saved_dashboards WHERE dashboard_id = %s", (dashboard_id,))
            conn.commit()
            return cur.rowcount > 0
    except Exception:
        conn.rollback()
        raise

def compute_data_hash(data: list[dict]) -> str:
    """Hash the data to detect changes on refresh."""
    try:
        raw = json.dumps(data, default=str, sort_keys=True)
        return hashlib.md5(raw.encode()).hexdigest()
    except Exception:
        return ""


try:
    _init_db()
    _load_all_from_db()
except Exception as e:
    import logging
    logging.warning(f"Failed to initialize dashboard store DB: {e}. Using in-memory fallback.")