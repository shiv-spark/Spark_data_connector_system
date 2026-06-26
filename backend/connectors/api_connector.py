# import requests
# import polars as pl
# import time

# def api_connector(url, retries=3, delay=5):
#     for attempt in range(retries):
#         try:
#             response = requests.get(url, timeout=30)
#             if response.status_code == 200:
#                 return pl.DataFrame(response.json())
#         except Exception as e:
#             print(f"Attempt {attempt+1} failed: {e}")
#             if attempt < retries - 1:
#                 time.sleep(delay)
#     raise Exception(f"API failed after {retries} attempts")

import requests
import polars as pl
import time


def _extract_records(data):
    """
    Find the actual list-of-records inside any JSON API response shape.

    Handles:
      1. Already a flat list:      [ {...}, {...} ]
      2. Wrapped in a known key:   { "data": [...] } / { "results": [...] } / { "items": [...] }
      3. Wrapped in an unknown key: { "carts": [...] }  -> first list-valued key found
      4. A single object:          { ... }  -> wrapped as one-row list
    """
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


def _find_nested_list_columns(df: pl.DataFrame):
    """Return names of columns whose dtype is a List of Struct (nested records)."""
    nested_cols = []
    for name, dtype in zip(df.columns, df.dtypes):
        if isinstance(dtype, pl.List):
            inner = dtype.inner
            if isinstance(inner, pl.Struct):
                nested_cols.append(name)
    return nested_cols


def _flatten_dataframe(df: pl.DataFrame, max_depth: int = 5) -> pl.DataFrame:
    """
    Recursively explode + unnest any List(Struct) columns so every nested
    record becomes its own row, with nested fields prefixed by the parent
    column name to avoid collisions (e.g. products.id, products.price).

    Caps recursion at max_depth to avoid runaway expansion on pathological
    or self-referential schemas.
    """
    depth = 0
    while depth < max_depth:
        nested_cols = _find_nested_list_columns(df)
        if not nested_cols:
            break

        for col in nested_cols:
            # Explode turns each list item into its own row (duplicating
            # the parent row's other columns), nulls become a single null row
            df = df.explode(col)

            # Unnest the struct into separate columns, prefixed by parent name
            struct_df = df.select(col).unnest(col)
            struct_df = struct_df.rename({c: f"{col}.{c}" for c in struct_df.columns})

            df = df.drop(col).hstack(struct_df)

        depth += 1

    return df


def _records_to_dataframe(records) -> pl.DataFrame:
    """Build a DataFrame from records, coercing mixed types, then flatten nesting."""
    df = pl.DataFrame(records, strict=False)
    df = _flatten_dataframe(df)
    return df


def api_connector(url, retries=3, delay=5):
    last_error = None

    for attempt in range(retries):
        try:
            response = requests.get(url, timeout=30)

            if response.status_code == 200:
                try:
                    data = response.json()
                except ValueError as e:
                    last_error = f"Response was not valid JSON: {e} | Body: {response.text[:300]}"
                    print(f"Attempt {attempt + 1} failed: {last_error}")
                    if attempt < retries - 1:
                        time.sleep(delay)
                    continue

                try:
                    records = _extract_records(data)
                    return _records_to_dataframe(records)
                except Exception as e:
                    last_error = f"Could not convert response JSON to DataFrame: {e} | Sample: {str(data)[:300]}"
                    print(f"Attempt {attempt + 1} failed: {last_error}")
                    if attempt < retries - 1:
                        time.sleep(delay)
                    continue

            else:
                last_error = f"HTTP {response.status_code} | Body: {response.text[:300]}"
                print(f"Attempt {attempt + 1} failed: {last_error}")

        except requests.exceptions.Timeout:
            last_error = "Request timed out after 30s"
            print(f"Attempt {attempt + 1} failed: {last_error}")
        except requests.exceptions.ConnectionError as e:
            last_error = f"Connection error: {e}"
            print(f"Attempt {attempt + 1} failed: {last_error}")
        except Exception as e:
            last_error = str(e)
            print(f"Attempt {attempt + 1} failed: {last_error}")

        if attempt < retries - 1:
            time.sleep(delay)

    raise Exception(f"API failed after {retries} attempts. Last error: {last_error}")