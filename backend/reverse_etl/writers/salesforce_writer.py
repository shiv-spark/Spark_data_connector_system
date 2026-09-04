"""
Pushes rows OUT to Salesforce (create / update / upsert records on a given
sObject). Reuses the exact same OAuth2 username-password flow as
connectors/salesforce_connector.py, so an existing Salesforce saved
connection can be used as a reverse-ETL destination unchanged.

config keys: access_token/instance_url (ready-made), OR
             login_url/client_id/client_secret/username/password/security_token
"""

import requests

API_VERSION = "v59.0"


def _login(config: dict, timeout=30):
    if config.get("access_token") and config.get("instance_url"):
        return config["access_token"], config["instance_url"]

    login_url = config.get("login_url", "https://login.salesforce.com")
    resp = requests.post(
        f"{login_url.rstrip('/')}/services/oauth2/token",
        data={
            "grant_type": "password",
            "client_id": config.get("client_id"),
            "client_secret": config.get("client_secret"),
            "username": config.get("username"),
            "password": f"{config.get('password', '')}{config.get('security_token') or ''}",
        },
        timeout=timeout,
    )
    if resp.status_code != 200:
        raise Exception(f"Salesforce login failed ({resp.status_code}): {resp.text}")
    data = resp.json()
    return data["access_token"], data["instance_url"]


def salesforce_writer(records: list, config: dict, object_name: str,
                       upsert_key: str | None, write_mode: str, batch_size: int = 200) -> dict:
    if not records:
        return {"success": 0, "failed": 0, "errors": []}

    access_token, instance_url = _login(config)
    headers = {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}

    success, failed, errors = 0, 0, []

    if write_mode == "upsert" and upsert_key:
        # Salesforce upsert-by-external-ID is a per-record PATCH — the
        # Composite sObject Collections API only supports create/update by
        # record Id, not upsert-by-external-id, so this is the correct call.
        url_base = f"{instance_url}/services/data/{API_VERSION}/sobjects/{object_name}/{upsert_key}"
        for rec in records:
            key_value = rec.get(upsert_key)
            body = {k: v for k, v in rec.items() if k != upsert_key}
            try:
                resp = requests.patch(f"{url_base}/{key_value}", json=body, headers=headers, timeout=30)
                if resp.status_code in (200, 201, 204):
                    success += 1
                else:
                    failed += 1
                    errors.append(f"{key_value}: {resp.status_code} {resp.text[:200]}")
            except Exception as e:
                failed += 1
                errors.append(f"{key_value}: {e}")
    else:
        # Composite sObject Collections — up to 200 records per call.
        url = f"{instance_url}/services/data/{API_VERSION}/composite/sobjects"
        for i in range(0, len(records), min(batch_size, 200)):
            batch = records[i:i + min(batch_size, 200)]
            body = {
                "allOrNone": False,
                "records": [{**rec, "attributes": {"type": object_name}} for rec in batch],
            }
            try:
                resp = requests.post(url, json=body, headers=headers, timeout=60)
                if resp.status_code != 200:
                    failed += len(batch)
                    errors.append(f"{resp.status_code}: {resp.text[:300]}")
                    continue
                for result in resp.json():
                    if result.get("success"):
                        success += 1
                    else:
                        failed += 1
                        errors.append(str(result.get("errors")))
            except Exception as e:
                failed += len(batch)
                errors.append(str(e))

    return {"success": success, "failed": failed, "errors": errors[:20]}
