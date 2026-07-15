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


def save_dashboard(dashboard_id: str, state: dict):
    """Save dashboard state to both memory and DB."""
    conn = _get_conn()
    state_with_time = {
        **state,
        "last_updated": datetime.utcnow().isoformat(),
    }
    _store[dashboard_id] = state_with_time
    with conn.cursor() as cur:
        cur.execute("""
            INSERT INTO saved_dashboards (dashboard_id, state, last_updated)
            VALUES (%s, %s, NOW())
            ON CONFLICT (dashboard_id) DO UPDATE SET
                state = EXCLUDED.state,
                last_updated = NOW()
        """, (dashboard_id, json.dumps(state, default=str)))
        conn.commit()


def get_dashboard(dashboard_id: str) -> dict | None:
    """Get dashboard from memory (already loaded from DB on startup)."""
    return _store.get(dashboard_id)


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


def delete_dashboard(dashboard_id: str) -> bool:
    """Delete a dashboard from both memory and DB."""
    conn = _get_conn()
    if dashboard_id in _store:
        del _store[dashboard_id]
    with conn.cursor() as cur:
        cur.execute("DELETE FROM saved_dashboards WHERE dashboard_id = %s", (dashboard_id,))
        conn.commit()
        return cur.rowcount > 0


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