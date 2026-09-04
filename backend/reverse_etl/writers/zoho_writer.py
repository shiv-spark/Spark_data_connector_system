"""
Pushes rows OUT to Zoho CRM (create / update records on a given module),
using the v3 REST bulk endpoints. Reuses the same OAuth vocabulary as
connectors/zoho_connector.py, so an existing Zoho saved connection can be
used as a reverse-ETL destination unchanged.

config keys: access_token (ready-made), OR refresh_token/client_id/client_secret
             accounts_url (default https://accounts.zoho.com)
             api_domain    (default https://www.zohoapis.com)
"""

import requests

DEFAULT_TIMEOUT = 30


def _get_access_token(config: dict, timeout=DEFAULT_TIMEOUT) -> str:
    if config.get("access_token"):
        return config["access_token"]

    accounts_url = (config.get("accounts_url") or "https://accounts.zoho.com").rstrip("/")
    resp = requests.post(
        f"{accounts_url}/oauth/v2/token",
        data={
            "grant_type": "refresh_token",
            "client_id": config.get("client_id"),
            "client_secret": config.get("client_secret"),
            "refresh_token": config.get("refresh_token"),
        },
        timeout=timeout,
    )
    if resp.status_code != 200 or "access_token" not in resp.json():
        raise Exception(f"Zoho token refresh failed ({resp.status_code}): {resp.text}")
    return resp.json()["access_token"]


def zoho_writer(records: list, config: dict, object_name: str,
                 upsert_key: str | None, write_mode: str, batch_size: int = 100) -> dict:
    if not records:
        return {"success": 0, "failed": 0, "errors": []}

    module = object_name or config.get("module")
    if not module:
        raise ValueError("zoho destination requires a destination_object (CRM module, e.g. 'Leads')")

    access_token = _get_access_token(config)
    api_domain = (config.get("api_domain") or "https://www.zohoapis.com").rstrip("/")
    headers = {"Authorization": f"Zoho-oauthtoken {access_token}", "Content-Type": "application/json"}

    # Zoho's v3 bulk endpoint doubles as create AND update: include the
    # record's own "id" field to update, omit it to create — this is what
    # "upsert" maps to here since Zoho has no separate upsert-by-key route
    # for generic external fields (only Salesforce-style external ID fields
    # configured per-module, which we can't assume exist).
    url = f"{api_domain}/crm/v3/{module}"
    duplicate_check_fields = [upsert_key] if (write_mode == "upsert" and upsert_key) else None

    success, failed, errors = 0, 0, []
    batch_size = min(batch_size, 100)  # Zoho bulk limit

    for i in range(0, len(records), batch_size):
        batch = records[i:i + batch_size]
        body = {"data": batch}
        if duplicate_check_fields:
            body["duplicate_check_fields"] = duplicate_check_fields
        try:
            resp = requests.post(url, json=body, headers=headers, timeout=60)
            if resp.status_code not in (200, 201):
                failed += len(batch)
                errors.append(f"{resp.status_code}: {resp.text[:300]}")
                continue
            for result in resp.json().get("data", []):
                if result.get("status") == "success":
                    success += 1
                else:
                    failed += 1
                    errors.append(str(result.get("message") or result))
        except Exception as e:
            failed += len(batch)
            errors.append(str(e))

    return {"success": success, "failed": failed, "errors": errors[:20]}
