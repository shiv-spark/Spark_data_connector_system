"""
Pushes rows OUT to any generic REST endpoint (internal microservice, Zapier
/ Make webhook, etc). Mirror image of connectors/api_connector.py, reusing
the same auth_type vocabulary already used across the platform
(none / bearer / api_key_header / api_key_query / basic) so it feels
familiar in the Connections UI.

config keys:
  url            (required unless object_name/destination_object is the URL)
  method         POST | PUT   (default POST)
  auth_type      none | bearer | api_key_header | api_key_query | basic
  api_key, header_name, bearer_prefix, query_param_name
  user, password (for basic auth)
  batch_key      name of the JSON field the row array is sent under
                 (default "records"); set to null/"" to POST a bare array
"""

import requests
from requests.auth import HTTPBasicAuth


def _build_auth_kwargs(config: dict) -> dict:
    auth_type = config.get("auth_type", "none")
    headers, params, auth = {}, {}, None

    if auth_type == "bearer":
        prefix = config.get("bearer_prefix", "Bearer")
        headers["Authorization"] = f"{prefix} {config.get('api_key', '')}"
    elif auth_type == "api_key_header":
        headers[config.get("header_name", "Authorization")] = config.get("api_key", "")
    elif auth_type == "api_key_query":
        params[config.get("query_param_name", "api_key")] = config.get("api_key", "")
    elif auth_type == "basic":
        auth = HTTPBasicAuth(config.get("user", ""), config.get("password", ""))

    return {"headers": headers, "params": params, "auth": auth}


def webhook_writer(records: list, config: dict, object_name: str,
                    upsert_key: str | None, write_mode: str, batch_size: int = 100) -> dict:
    if not records:
        return {"success": 0, "failed": 0, "errors": []}

    url = config.get("url") or object_name
    if not url or not (url.startswith("http://") or url.startswith("https://")):
        raise ValueError(f"Webhook destination requires a valid URL starting with http:// or https:// (got: {url!r})")

    method = config.get("method", "POST").upper()
    batch_key = config.get("batch_key", "records")
    auth_kwargs = _build_auth_kwargs(config)

    success, failed, errors = 0, 0, []
    for i in range(0, len(records), batch_size):
        batch = records[i:i + batch_size]
        payload = batch if not batch_key else {batch_key: batch, "write_mode": write_mode, "upsert_key": upsert_key}
        try:
            resp = requests.request(method, url, json=payload, timeout=30, **auth_kwargs)
            if resp.status_code >= 400:
                failed += len(batch)
                errors.append(f"{resp.status_code}: {resp.text[:300]}")
            else:
                success += len(batch)
        except Exception as e:
            failed += len(batch)
            errors.append(str(e))

    return {"success": success, "failed": failed, "errors": errors[:20]}
