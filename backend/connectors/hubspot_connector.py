import time

import pandas as pd
import polars as pl
import requests

DEFAULT_TIMEOUT = 30
DEFAULT_PAGE_SIZE = 100


def hubspot_connector(
    access_token: str,                 # HubSpot Private App token (Bearer)
    object_type: str = "contacts",     # contacts | companies | deals | tickets | line_items | products | <custom object id/name>
    properties: list = None,           # explicit property list; HubSpot returns a default set if omitted
    page_size: int = DEFAULT_PAGE_SIZE,
    max_pages: int = 500,
    retries: int = 3,
    delay: int = 5,
    timeout=DEFAULT_TIMEOUT,
):
    """
    Pull records from a HubSpot CRM object via the v3 Objects API and
    return a Polars DataFrame. Each record's `properties` dict is flattened
    into top-level columns; pagination follows the `after` cursor HubSpot
    returns in `paging.next.after`.
    """
    if not access_token:
        raise Exception("HubSpot: access_token is required.")
    if not object_type:
        raise Exception("HubSpot: object_type is required.")

    headers = {"Authorization": f"Bearer {access_token}"}
    url = f"https://api.hubapi.com/crm/v3/objects/{object_type}"
    base_params = {"limit": page_size}
    if properties:
        base_params["properties"] = ",".join(properties) if isinstance(properties, list) else properties

    all_records = []
    after = None
    pages_fetched = 0
    last_error = None

    while pages_fetched < max_pages:
        params = dict(base_params)
        if after:
            params["after"] = after

        resp = None
        for attempt in range(retries):
            try:
                resp = requests.get(url, headers=headers, params=params, timeout=timeout)
                if resp.status_code == 401:
                    raise Exception("HubSpot authentication failed: 401 Unauthorized (check access_token/scopes).")
                if resp.status_code != 200:
                    raise Exception(f"HubSpot request failed ({resp.status_code}): {resp.text}")
                last_error = None
                break
            except requests.exceptions.RequestException as e:
                last_error = f"Connection error: {e}"
            except Exception as e:
                last_error = str(e)
                if resp is not None and resp.status_code == 401:
                    break  # auth errors won't fix themselves on retry

            print(f"Attempt {attempt + 1}/{retries} failed: {last_error}")
            if attempt < retries - 1:
                time.sleep(delay)

        if last_error:
            raise Exception(f"HubSpot request failed after {retries} attempts. Last error: {last_error}")

        data = resp.json()
        results = data.get("results", [])
        for record in results:
            row = {"id": record.get("id")}
            row.update(record.get("properties", {}) or {})
            all_records.append(row)

        print(f"HubSpot: fetched {len(results)} records (total {len(all_records)})")
        pages_fetched += 1

        after = (data.get("paging") or {}).get("next", {}).get("after")
        if not after or not results:
            break

    if not all_records:
        return pl.DataFrame()

    df = pd.DataFrame(all_records)
    return pl.from_pandas(df)
