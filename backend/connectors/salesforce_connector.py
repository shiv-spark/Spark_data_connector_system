import time

import pandas as pd
import polars as pl
import requests

API_VERSION = "v59.0"
DEFAULT_TIMEOUT = 30


def _login_password_flow(login_url, client_id, client_secret, username, password, security_token, timeout):
    """
    OAuth2 username-password flow. Good fit for scheduled/unattended
    pipelines (no browser redirect needed) — returns a fresh access_token +
    instance_url on every call, which sidesteps token-expiry issues for
    pipelines that run every few minutes.
    """
    token_url = f"{login_url.rstrip('/')}/services/oauth2/token"
    resp = requests.post(
        token_url,
        data={
            "grant_type": "password",
            "client_id": client_id,
            "client_secret": client_secret,
            "username": username,
            "password": f"{password}{security_token or ''}",
        },
        timeout=timeout,
    )
    if resp.status_code != 200:
        raise Exception(f"Salesforce login failed ({resp.status_code}): {resp.text}")
    data = resp.json()
    return data["access_token"], data["instance_url"]


def _default_soql(access_token, instance_url, object_name, fields, timeout):
    """Build 'SELECT <fields> FROM <object>' when the caller didn't supply
    an explicit SOQL query — describes the object to discover queryable
    field names when no explicit field list was given."""
    if fields:
        field_list = fields if isinstance(fields, str) else ", ".join(fields)
    else:
        describe_url = f"{instance_url}/services/data/{API_VERSION}/sobjects/{object_name}/describe"
        resp = requests.get(
            describe_url,
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=timeout,
        )
        if resp.status_code != 200:
            raise Exception(f"Salesforce describe('{object_name}') failed ({resp.status_code}): {resp.text}")
        describe = resp.json()
        field_list = ", ".join(
            f["name"] for f in describe.get("fields", []) if f.get("name")
        )
        if not field_list:
            raise Exception(f"Salesforce object '{object_name}' has no queryable fields.")
    return f"SELECT {field_list} FROM {object_name}"


def salesforce_connector(
    # ── auth: either a ready-made token, or creds to fetch one each run ──
    access_token: str = None,
    instance_url: str = None,
    login_url: str = "https://login.salesforce.com",
    client_id: str = None,
    client_secret: str = None,
    username: str = None,
    password: str = None,
    security_token: str = None,

    # ── what to fetch ──
    object_name: str = None,          # e.g. "Account", "Contact", "Lead", "Opportunity"
    fields: list = None,              # optional explicit field list; auto-discovered via describe() if omitted
    soql_query: str = None,           # explicit SOQL — overrides object_name/fields entirely

    retries: int = 3,
    delay: int = 5,
    timeout=DEFAULT_TIMEOUT,
):
    """
    Pull records from Salesforce via the REST Query API and return a Polars
    DataFrame. Handles pagination via nextRecordsUrl automatically.
    """
    if not access_token or not instance_url:
        if not (client_id and client_secret and username and password):
            raise Exception(
                "Salesforce: provide either (access_token + instance_url) or "
                "(client_id, client_secret, username, password[, security_token])."
            )
        access_token, instance_url = _login_password_flow(
            login_url, client_id, client_secret, username, password, security_token, timeout
        )

    if not soql_query:
        if not object_name:
            raise Exception("Salesforce: object_name or soql_query is required.")
        soql_query = _default_soql(access_token, instance_url, object_name, fields, timeout)

    headers = {"Authorization": f"Bearer {access_token}"}
    url = f"{instance_url}/services/data/{API_VERSION}/query"
    params = {"q": soql_query}

    all_records = []
    last_error = None
    for attempt in range(retries):
        try:
            while url:
                resp = requests.get(url, headers=headers, params=params, timeout=timeout)
                if resp.status_code != 200:
                    raise Exception(f"Salesforce query failed ({resp.status_code}): {resp.text}")
                data = resp.json()
                batch = data.get("records", [])
                for r in batch:
                    r.pop("attributes", None)
                all_records.extend(batch)
                print(f"Salesforce: fetched {len(batch)} records (total {len(all_records)})")

                if data.get("done", True):
                    url = None
                else:
                    url = f"{instance_url}{data['nextRecordsUrl']}"
                    params = None
            last_error = None
            break
        except requests.exceptions.RequestException as e:
            last_error = f"Connection error: {e}"
        except Exception as e:
            last_error = str(e)

        if last_error:
            print(f"Attempt {attempt + 1}/{retries} failed: {last_error}")
            if attempt < retries - 1:
                time.sleep(delay)

    if last_error:
        raise Exception(f"Salesforce request failed after {retries} attempts. Last error: {last_error}")

    if not all_records:
        return pl.DataFrame()

    df = pd.DataFrame(all_records)
    return pl.from_pandas(df)
