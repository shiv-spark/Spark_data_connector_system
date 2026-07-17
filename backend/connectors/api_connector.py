import copy
import time

import polars as pl
import requests
from requests.auth import HTTPBasicAuth


# ═══════════════════════════════════════════════════════════════════════════
# JSON → DataFrame helpers (unchanged from the original connector)
# ═══════════════════════════════════════════════════════════════════════════

def _extract_records(data):

    if isinstance(data, list):
        return data

    if isinstance(data, dict):
        for key in ("data", "results", "items", "records", "rows"):
            if key in data and isinstance(data[key], list):
                return data[key]

        for key, value in data.items():
            if isinstance(value, list):
                return value

        return [data]

    raise ValueError(f"Unsupported JSON top-level type: {type(data)}")



def _find_plain_struct_columns(df: pl.DataFrame):

    return [
        name for name, dtype in zip(df.columns, df.dtypes)
        if isinstance(dtype, pl.Struct)
    ]


def _unnest_plain_struct_columns(df: pl.DataFrame) -> pl.DataFrame:
   
    struct_cols = _find_plain_struct_columns(df)
    for col in struct_cols:
        struct_df = df.select(col).unnest(col)
        struct_df = struct_df.rename({c: f"{col}.{c}" for c in struct_df.columns})
        df = df.drop(col).hstack(struct_df)
    return df
def _find_nested_list_columns(df: pl.DataFrame):
    """Return names of columns whose dtype is a List of Struct (nested records)."""
    nested_cols = []
    for name, dtype in zip(df.columns, df.dtypes):
        if isinstance(dtype, pl.List):
            inner = dtype.inner
            if isinstance(inner, pl.Struct):
                nested_cols.append(name)
    return nested_cols


def _find_simple_list_columns(df: pl.DataFrame):

    simple_list_cols = []
    for name, dtype in zip(df.columns, df.dtypes):
        if isinstance(dtype, pl.List):
            inner = dtype.inner
            if not isinstance(inner, pl.Struct):
                simple_list_cols.append(name)
    return simple_list_cols


def _stringify_simple_list_columns(df: pl.DataFrame, delimiter: str = ", ") -> pl.DataFrame:

    simple_list_cols = _find_simple_list_columns(df)
    if not simple_list_cols:
        return df

    for col in simple_list_cols:
        df = df.with_columns(
            pl.col(col).list.eval(pl.element().cast(pl.Utf8)).list.join(delimiter).alias(col)
        )
    return df
def _flatten_dataframe(df: pl.DataFrame, max_depth: int = 5) -> pl.DataFrame:

    depth = 0
    while depth < max_depth:
        nested_cols = _find_nested_list_columns(df)
        if not nested_cols:
            break

        for col in nested_cols:
            df = df.explode(col)

            struct_df = df.select(col).unnest(col)
            struct_df = struct_df.rename({c: f"{col}.{c}" for c in struct_df.columns})

            df = df.drop(col).hstack(struct_df)

        depth += 1
    df = _unnest_plain_struct_columns(df)
    df = _stringify_simple_list_columns(df)   

    return df


def _records_to_dataframe(records, flatten: bool = True) -> pl.DataFrame:
    """Build a DataFrame from records, coercing mixed types, then flatten nesting."""
    df = pl.DataFrame(records, strict=False)
    if flatten:
        df = _flatten_dataframe(df)
    return df

def _dig(data, path):
    """
    Navigate a dot-notation path into a nested dict/list response.
    e.g. _dig(response_json, "data.items") -> response_json["data"]["items"]
    Returns None if any part of the path is missing.
    """
    if not path:
        return data
    current = data
    for key in path.split("."):
        if isinstance(current, dict):
            current = current.get(key)
        elif isinstance(current, list) and key.isdigit():
            idx = int(key)
            current = current[idx] if idx < len(current) else None
        else:
            return None
        if current is None:
            return None
    return current


def _get_nested_dict(container: dict, path):
    """
    Navigate to a nested dict via dot-path, creating intermediate dicts
    if they don't exist yet. Returns the dict at that path (or the
    container itself if path is falsy).
    """
    target = container
    if path:
        for key in path.split("."):
            if key not in target or not isinstance(target[key], dict):
                target[key] = {}
            target = target[key]
    return target


def _merge_custom_fields(container: dict, path, fields: dict):
    """
    Merge an arbitrary flat dict of user-specific fields into a
    (possibly nested) location inside container, in place.
    """
    if not fields:
        return
    target = _get_nested_dict(container, path)
    target.update(fields)


def _set_nested_bounds(body: dict, path, lower_field: str, higher_field: str, lower_val, higher_val):
    """
    Mutate lower/higher bound fields inside a (possibly nested) request body
    in place. path is dot-notation to the dict that actually holds the bound
    fields — e.g. path="getpoEncumbranceInfo" for:
        { "getpoEncumbranceInfo": { "lowerBound": ..., "higherBound": ... } }
    Leave path=None if the bound fields live at the top level of the body.
    """
    target = _get_nested_dict(body, path)
    target[lower_field] = lower_val
    target[higher_field] = higher_val


# ═══════════════════════════════════════════════════════════════════════════
# Auth — 4 generic methods
# ═══════════════════════════════════════════════════════════════════════════

VALID_AUTH_TYPES = {"none", "api_key_header", "bearer", "basic", "api_key_query"}


def _build_auth(
    auth_type: str,
    api_key: str = None,
    header_name: str = "Authorization",
    bearer_token: str = None,
    bearer_prefix: str = "Bearer",
    basic_user: str = None,
    basic_password: str = None,
    query_param_name: str = "api_key",
    extra_headers: dict = None,
):

    if auth_type not in VALID_AUTH_TYPES:
        raise ValueError(f"Unknown auth_type '{auth_type}'. Valid: {sorted(VALID_AUTH_TYPES)}")

    headers = dict(extra_headers or {})
    requests_auth = None
    auth_params = {}

    if auth_type == "api_key_header":
        if not api_key:
            raise ValueError("api_key is required for auth_type='api_key_header'")
        headers[header_name or "Authorization"] = api_key

    elif auth_type == "bearer":
        if not bearer_token:
            raise ValueError("bearer_token is required for auth_type='bearer'")
        prefix = f"{bearer_prefix} " if bearer_prefix else ""
        headers["Authorization"] = f"{prefix}{bearer_token}"

    elif auth_type == "basic":
        if not basic_user or not basic_password:
            raise ValueError("basic_user and basic_password are required for auth_type='basic'")
        requests_auth = HTTPBasicAuth(basic_user, basic_password)

    elif auth_type == "api_key_query":
        if not api_key:
            raise ValueError("api_key is required for auth_type='api_key_query'")
        auth_params[query_param_name or "api_key"] = api_key

    # auth_type == "none" -> nothing to add

    return headers, requests_auth, auth_params


# ═══════════════════════════════════════════════════════════════════════════
# Single HTTP request with retry
# ═══════════════════════════════════════════════════════════════════════════

def _request_with_retries(
    method, url, headers, params, json_body, timeout, requests_auth, retries, delay
):
    last_error = None

    for attempt in range(retries):
        try:
            response = requests.request(
                method=method,
                url=url,
                headers=headers or None,
                params=params or None,
                json=json_body if json_body is not None else None,
                timeout=timeout,
                auth=requests_auth,
            )

            if response.status_code == 200:
                try:
                    return response.json()
                except ValueError as e:
                    last_error = f"Response was not valid JSON: {e} | Body: {response.text[:300]}"
            else:
                last_error = f"HTTP {response.status_code} | Body: {response.text[:300]}"

        except requests.exceptions.Timeout:
            last_error = f"Request timed out (timeout={timeout})"
        except requests.exceptions.ConnectionError as e:
            last_error = f"Connection error: {e}"
        except Exception as e:
            last_error = str(e)

        print(f"Attempt {attempt + 1}/{retries} failed: {last_error}")
        if attempt < retries - 1:
            time.sleep(delay)

    raise Exception(f"Request failed after {retries} attempts. Last error: {last_error}")


# ═══════════════════════════════════════════════════════════════════════════
# MAIN ENTRY POINT
# ═══════════════════════════════════════════════════════════════════════════

def api_connector(
    url,
    method: str = "GET",
    retries: int = 3,
    delay: int = 5,
    timeout=30,

    # ── auth (pick one of: none | api_key_header | bearer | basic | api_key_query) ──
    auth_type: str = "none",
    api_key: str = None,
    header_name: str = "Authorization",     # header name used by api_key_header
    bearer_token: str = None,
    bearer_prefix: str = "Bearer",
    basic_user: str = None,
    basic_password: str = None,
    query_param_name: str = "api_key",      # query param name used by api_key_query

    # ── request shaping ──
    extra_headers: dict = None,
    extra_params: dict = None,
    body: dict = None,                      # JSON body template (for POST/PUT)

    # ── user/API-specific custom fields ──
    # Every third-party API has its own arbitrary field names (pUserName,
    # pPoNum, pReservDateFrom, ...) that no fixed parameter list can predict.
    # custom_fields is a flat dict of exactly those — supplied per-pipeline
    # by whoever configures this connector for their specific API — merged
    # into whichever part of the request custom_fields_location points at.
    custom_fields: dict = None,
    custom_fields_location: str = "body",   # body | params | headers
    custom_fields_path: str = None,         # dot-path inside body to merge into (location="body" only)

    # ── response shaping ──
    records_path: str = None,               # dot-path to the records list, e.g. "data.items"
    flatten: bool = True,

    # ── pagination (pick one of: none | page | offset_limit | body_bounds) ──
    pagination_type: str = "none",
    max_pages: int = 500,

    # page-number pagination (query params)
    page_param: str = "page",
    page_start: int = 1,

    # offset/limit pagination (query params)
    offset_param: str = "offset",
    limit_param: str = "limit",
    limit_size: int = 100,

    # body-mutation pagination — for APIs that take pagination bounds inside
    # the POST body itself instead of query params, e.g.:
    #   {"getpoEncumbranceInfo": {"lowerBound": 0, "higherBound": 999, ...}}
    body_pagination_path: str = None,       # dot-path to the dict holding the bound fields, or None if top-level
    lower_bound_field: str = "lowerBound",
    higher_bound_field: str = "higherBound",
    initial_lower_bound: int = 0,
    step_size: int = 1000,
):
    """
    Generic REST API connector :
      - GET or POST (or any HTTP method requests supports)
      - auth methods: api_key_header, bearer, basic, api_key_query (or none)
      - pagination strategies: page, offset_limit, body_bounds (or none)
      - retry with backoff on transient failures
      - flexible response shapes via records_path + the existing
        auto-detecting _extract_records fallback

    Backward compatible: api_connector(url) still does a single plain GET,
    exactly like the original implementation.
    """
    method = (method or "GET").upper()

    if custom_fields_location not in ("body", "params", "headers"):
        raise ValueError(
            f"Unknown custom_fields_location '{custom_fields_location}'. "
            f"Valid: body, params, headers"
        )

    headers, requests_auth, auth_params = _build_auth(
        auth_type=auth_type,
        api_key=api_key,
        header_name=header_name,
        bearer_token=bearer_token,
        bearer_prefix=bearer_prefix,
        basic_user=basic_user,
        basic_password=basic_password,
        query_param_name=query_param_name,
        extra_headers=extra_headers,
    )

    base_params = {**(extra_params or {}), **auth_params}

    # Work on a copy so we never mutate the caller's original body dict —
    # important since body_bounds pagination also deep-copies this per page.
    working_body = copy.deepcopy(body) if body is not None else None

    if custom_fields:
        if custom_fields_location == "headers":
            headers.update(custom_fields)
        elif custom_fields_location == "params":
            base_params.update(custom_fields)
        elif custom_fields_location == "body":
            if working_body is None:
                working_body = {}
            _merge_custom_fields(working_body, custom_fields_path, custom_fields)

    body = working_body

    def _extract_page_records(response_json):
        scoped = _dig(response_json, records_path) if records_path else response_json
        if scoped is None:
            return []
        return _extract_records(scoped)

    all_records = []

    # ── NO PAGINATION — single request ──────────────────────────────────
    if pagination_type == "none":
        response_json = _request_with_retries(
            method, url, headers, base_params, body, timeout, requests_auth, retries, delay
        )
        all_records = _extract_page_records(response_json)

    # ── PAGE-NUMBER PAGINATION (query params) ───────────────────────────
    elif pagination_type == "page":
        page_num = page_start
        pages_fetched = 0
        while pages_fetched < max_pages:
            params = {**base_params, page_param: page_num}
            response_json = _request_with_retries(
                method, url, headers, params, body, timeout, requests_auth, retries, delay
            )
            page_records = _extract_page_records(response_json)
            if not page_records:
                print(f"Page {page_num}: no records — stopping pagination.")
                break
            print(f"Page {page_num}: fetched {len(page_records)} records")
            all_records.extend(page_records)
            pages_fetched += 1
            page_num += 1

    # ── OFFSET/LIMIT PAGINATION (query params) ──────────────────────────
    elif pagination_type == "offset_limit":
        offset = 0
        pages_fetched = 0
        while pages_fetched < max_pages:
            params = {**base_params, offset_param: offset, limit_param: limit_size}
            response_json = _request_with_retries(
                method, url, headers, params, body, timeout, requests_auth, retries, delay
            )
            page_records = _extract_page_records(response_json)
            if not page_records:
                print(f"Offset {offset}: no records — stopping pagination.")
                break
            print(f"Offset {offset}: fetched {len(page_records)} records")
            all_records.extend(page_records)
            pages_fetched += 1
            if len(page_records) < limit_size:
                # short page => last page
                break
            offset += limit_size

    # ── BODY-MUTATION BOUNDED PAGINATION (bounds inside the JSON body) ──
    elif pagination_type == "body_bounds":
        if body is None:
            raise ValueError("body is required for pagination_type='body_bounds'")
        lower = initial_lower_bound
        pages_fetched = 0
        while pages_fetched < max_pages:
            higher = lower + step_size - 1
            current_body = copy.deepcopy(body)
            _set_nested_bounds(
                current_body, body_pagination_path,
                lower_bound_field, higher_bound_field, lower, higher,
            )
            print(f"Fetching bounds: {lower_bound_field}={lower}, {higher_bound_field}={higher}")
            response_json = _request_with_retries(
                method, url, headers, base_params, current_body, timeout, requests_auth, retries, delay
            )
            page_records = _extract_page_records(response_json)
            if not page_records:
                print("No more records — stopping pagination.")
                break
            print(f"Bounds [{lower}, {higher}]: fetched {len(page_records)} records")
            all_records.extend(page_records)
            pages_fetched += 1
            lower += step_size

    else:
        raise ValueError(
            f"Unknown pagination_type '{pagination_type}'. "
            f"Valid: none, page, offset_limit, body_bounds"
        )

    if not all_records:
        return pl.DataFrame()

    return _records_to_dataframe(all_records, flatten=flatten)



