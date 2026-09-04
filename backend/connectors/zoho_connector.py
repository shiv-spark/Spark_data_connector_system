import time

import pandas as pd
import polars as pl
import requests

DEFAULT_TIMEOUT = 30
DEFAULT_PAGE_SIZE = 200  # Zoho's max per_page for the v3 module-list endpoint


def _refresh_access_token(accounts_url, client_id, client_secret, refresh_token, timeout):
    """
    Zoho access tokens expire after ~1 hour, which doesn't play well with
    pipelines scheduled every few minutes/hours — so when a refresh_token is
    supplied, mint a fresh access_token on every run instead of relying on a
    long-lived one.
    """
    token_url = f"{accounts_url.rstrip('/')}/oauth/v2/token"
    resp = requests.post(
        token_url,
        data={
            "grant_type": "refresh_token",
            "client_id": client_id,
            "client_secret": client_secret,
            "refresh_token": refresh_token,
        },
        timeout=timeout,
    )
    if resp.status_code != 200 or "access_token" not in resp.json():
        raise Exception(f"Zoho token refresh failed ({resp.status_code}): {resp.text}")
    return resp.json()["access_token"]


def zoho_connector(
    # ── auth: either a ready-made token, or refresh creds to mint one each run ──
    access_token: str = None,
    refresh_token: str = None,
    client_id: str = None,
    client_secret: str = None,
    accounts_url: str = "https://accounts.zoho.com",   # regional: .com / .eu / .in / .com.au / .jp
    api_domain: str = "https://www.zohoapis.com",       # regional: matches accounts_url's TLD

    # ── what to fetch ──
    module: str = None,              # e.g. "Leads", "Contacts", "Deals", "Accounts"
    fields: list = None,             # optional explicit field list
    criteria: str = None,            # optional Zoho search criteria, e.g. "(Email:equals:a@b.com)"

    page_size: int = DEFAULT_PAGE_SIZE,
    max_pages: int = 500,
    retries: int = 3,
    delay: int = 5,
    timeout=DEFAULT_TIMEOUT,
):
    """
    Pull records from a Zoho CRM module via the v3 REST API and return a
    Polars DataFrame. Paginates using Zoho's `page` / `info.more_records`
    convention. Uses the /search endpoint when `criteria` is given, otherwise
    the plain module list endpoint.
    """
    if not access_token:
        if not (refresh_token and client_id and client_secret):
            raise Exception(
                "Zoho: provide either access_token or "
                "(refresh_token, client_id, client_secret) to mint one."
            )
        access_token = _refresh_access_token(accounts_url, client_id, client_secret, refresh_token, timeout)

    if not module:
        raise Exception("Zoho: module is required (e.g. 'Leads', 'Contacts', 'Deals').")

    headers = {"Authorization": f"Zoho-oauthtoken {access_token}"}
    url = f"{api_domain.rstrip('/')}/crm/v3/{module}/search" if criteria else f"{api_domain.rstrip('/')}/crm/v3/{module}"

    base_params = {"per_page": page_size}
    if fields:
        base_params["fields"] = ",".join(fields) if isinstance(fields, list) else fields
    if criteria:
        base_params["criteria"] = criteria

    all_records = []
    page = 1
    pages_fetched = 0
    last_error = None

    while pages_fetched < max_pages:
        params = {**base_params, "page": page}

        resp = None
        for attempt in range(retries):
            try:
                resp = requests.get(url, headers=headers, params=params, timeout=timeout)
                if resp.status_code == 204:
                    # No content — no more records at/after this page.
                    last_error = None
                    break
                if resp.status_code == 401:
                    raise Exception("Zoho authentication failed: 401 Unauthorized (check access_token/refresh_token).")
                if resp.status_code != 200:
                    raise Exception(f"Zoho request failed ({resp.status_code}): {resp.text}")
                last_error = None
                break
            except requests.exceptions.RequestException as e:
                last_error = f"Connection error: {e}"
            except Exception as e:
                last_error = str(e)
                if resp is not None and resp.status_code == 401:
                    break

            print(f"Attempt {attempt + 1}/{retries} failed: {last_error}")
            if attempt < retries - 1:
                time.sleep(delay)

        if last_error:
            raise Exception(f"Zoho request failed after {retries} attempts. Last error: {last_error}")

        if resp.status_code == 204:
            break

        data = resp.json()
        records = data.get("data", [])
        all_records.extend(records)
        print(f"Zoho: fetched {len(records)} records (total {len(all_records)})")
        pages_fetched += 1

        more_records = (data.get("info") or {}).get("more_records", False)
        if not more_records or not records:
            break
        page += 1

    if not all_records:
        return pl.DataFrame()

    df = pd.DataFrame(all_records)
    return pl.from_pandas(df)
