"""
dashboard_store.py
Simple in-memory store for dashboard states.
No Redis, no DB — free and zero setup.
State lives as long as the server is running.
"""

import hashlib
import json
from datetime import datetime

# { dashboard_id: { ...full state... } }
_store: dict = {}


def save_dashboard(dashboard_id: str, state: dict):
    _store[dashboard_id] = {
        **state,
        "last_updated": datetime.utcnow().isoformat(),
    }


def get_dashboard(dashboard_id: str) -> dict | None:
    return _store.get(dashboard_id)


def list_dashboards() -> list[dict]:
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


def compute_data_hash(data: list[dict]) -> str:
    """Hash the data to detect changes on refresh."""
    try:
        raw = json.dumps(data, default=str, sort_keys=True)
        return hashlib.md5(raw.encode()).hexdigest()
    except Exception:
        return ""
