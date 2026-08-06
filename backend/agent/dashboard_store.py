"""
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

            CREATE TABLE IF NOT EXISTS dashboard_history (
                id SERIAL PRIMARY KEY,
                dashboard_id VARCHAR(255) NOT NULL,
                state JSONB NOT NULL,
                label TEXT,
                created_at TIMESTAMP DEFAULT NOW()
            );
            CREATE INDEX IF NOT EXISTS idx_dashboard_history_lookup
                ON dashboard_history(dashboard_id, id DESC);
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


def _sanitize_for_json(obj):
    import math
    if isinstance(obj, float):
        return None if (math.isnan(obj) or math.isinf(obj)) else obj
    if isinstance(obj, dict):
        return {k: _sanitize_for_json(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_sanitize_for_json(v) for v in obj]
    return obj

HISTORY_LIMIT = 20
LAYOUT_COALESCE_SECONDS = 30


def _push_history(cur, dashboard_id: str, previous: dict, label: str):
    """
    Record the state being replaced, labelled with the change that replaced it,
    so "undo" can name what it is about to reverse.

    Consecutive layout saves inside a short window collapse into one entry —
    dragging four charts should be one undo step, not four.
    """
    if label == "Rearranged layout":
        cur.execute(
            """
            SELECT label, created_at FROM dashboard_history
            WHERE dashboard_id = %s ORDER BY id DESC LIMIT 1
            """,
            (dashboard_id,),
        )
        row = cur.fetchone()
        if row and row[0] == "Rearranged layout":
            age = (datetime.utcnow() - row[1]).total_seconds()
            if age < LAYOUT_COALESCE_SECONDS:
                return

    cur.execute(
        "INSERT INTO dashboard_history (dashboard_id, state, label) VALUES (%s, %s, %s)",
        (dashboard_id, json.dumps(_sanitize_for_json(previous), default=str), label),
    )

    # Keep the log bounded; old versions are not worth unbounded storage.
    cur.execute(
        """
        DELETE FROM dashboard_history
        WHERE dashboard_id = %s AND id NOT IN (
            SELECT id FROM dashboard_history
            WHERE dashboard_id = %s ORDER BY id DESC LIMIT %s
        )
        """,
        (dashboard_id, dashboard_id, HISTORY_LIMIT),
    )


def save_dashboard(dashboard_id: str, state: dict, label: str | None = None):
    """
    Save dashboard state to both memory and DB.

    When `label` is given and a previous state exists, the outgoing state is
    pushed onto the history log first. Passing no label skips history — used by
    undo/restore, which must not record their own rewind as a new change.
    """
    conn = _get_conn()
    clean_state = _sanitize_for_json(state)
    state_with_time = {
        **clean_state,
        "last_updated": datetime.utcnow().isoformat(),
    }
    previous = _store.get(dashboard_id)

    try:
        with conn.cursor() as cur:
            if label and previous:
                _push_history(cur, dashboard_id, previous, label)
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


def list_history(dashboard_id: str) -> list[dict]:
    """Version log for a dashboard, newest first. States are omitted — they're large."""
    conn = _get_conn()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                SELECT id, label, created_at FROM dashboard_history
                WHERE dashboard_id = %s ORDER BY id DESC
                """,
                (dashboard_id,),
            )
            return [
                {
                    "version_id": row["id"],
                    "label": row["label"],
                    "created_at": row["created_at"].isoformat() if row["created_at"] else None,
                }
                for row in cur.fetchall()
            ]
    except Exception:
        conn.rollback()
        raise


def rewind_dashboard(dashboard_id: str, version_id: int | None = None) -> dict | None:
    """
    Restore a previous state.

    With no version_id this is a single undo step: the newest entry. With one,
    it jumps straight to that version. Either way the restored entry and
    everything after it are dropped — rewinding discards the abandoned future,
    which is why there is no redo.
    """
    conn = _get_conn()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            if version_id is None:
                cur.execute(
                    """
                    SELECT id, state, label FROM dashboard_history
                    WHERE dashboard_id = %s ORDER BY id DESC LIMIT 1
                    """,
                    (dashboard_id,),
                )
            else:
                cur.execute(
                    "SELECT id, state, label FROM dashboard_history WHERE dashboard_id = %s AND id = %s",
                    (dashboard_id, version_id),
                )
            row = cur.fetchone()
            if not row:
                return None

            cur.execute(
                "DELETE FROM dashboard_history WHERE dashboard_id = %s AND id >= %s",
                (dashboard_id, row["id"]),
            )
            conn.commit()
    except Exception:
        conn.rollback()
        raise

    restored = dict(row["state"])
    # No label: the rewind itself must not become a new history entry.
    save_dashboard(dashboard_id, restored)
    return {"label": row["label"], "state": get_dashboard(dashboard_id)}


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