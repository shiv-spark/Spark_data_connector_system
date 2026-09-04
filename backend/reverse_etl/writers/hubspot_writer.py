"""
Pushes rows OUT to HubSpot (contacts / companies / deals / tickets / custom
objects), using the CRM v3 batch APIs. Reuses the same access_token auth as
connectors/hubspot_connector.py.

config keys: access_token
"""

import requests

BASE_URL = "https://api.hubapi.com/crm/v3/objects"


def hubspot_writer(records: list, config: dict, object_name: str,
                    upsert_key: str | None, write_mode: str, batch_size: int = 100) -> dict:
    if not records:
        return {"success": 0, "failed": 0, "errors": []}

    access_token = config.get("access_token")
    if not access_token:
        raise ValueError("hubspot destination requires access_token")

    headers = {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}
    object_type = object_name or "contacts"

    if write_mode == "upsert" and upsert_key:
        endpoint = f"{BASE_URL}/{object_type}/batch/upsert"
        def to_input(rec):
            return {"id": rec.get(upsert_key), "idProperty": upsert_key,
                    "properties": {k: v for k, v in rec.items() if k != upsert_key}}
    else:
        endpoint = f"{BASE_URL}/{object_type}/batch/create"
        def to_input(rec):
            return {"properties": rec}

    success, failed, errors = 0, 0, []
    batch_size = min(batch_size, 100)  # HubSpot batch limit

    for i in range(0, len(records), batch_size):
        batch = records[i:i + batch_size]
        body = {"inputs": [to_input(r) for r in batch]}
        try:
            resp = requests.post(endpoint, json=body, headers=headers, timeout=60)
            if resp.status_code in (200, 201):
                success += len(batch)
            else:
                failed += len(batch)
                errors.append(f"{resp.status_code}: {resp.text[:300]}")
        except Exception as e:
            failed += len(batch)
            errors.append(str(e))

    return {"success": success, "failed": failed, "errors": errors[:20]}
