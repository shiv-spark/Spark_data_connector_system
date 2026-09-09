"""
Shared, engine-agnostic helpers used by every destination adapter
(destinations/postgres.py, mysql.py, oracle.py, mongodb.py, snowflake.py).

Keeping these in one place means every adapter cleans column names and
validates identifiers EXACTLY the same way — important because the same
DataFrame can be routed to any of the five engines depending on what the
user picks as the destination, and the cleaned column name is what
downstream code (custom_schema matching, schema-mismatch reports, lineage)
keys off everywhere.
"""

import re

# ─────────────────────────────────────────────
# CLEAN COLUMN NAMES
# (identical logic to the original loaders/db_loader.py clean_column and
#  utils/schema_applier.py _clean_col — kept in sync deliberately)
# ─────────────────────────────────────────────


def clean_column(name) -> str:
    name = str(name).lower().strip()
    name = re.sub(r"[^\w]+", "_", name)
    name = re.sub(r"^_+|_+$", "", name)
    if re.match(r"^\d", name):
        name = f"col_{name}"
    return name or "unnamed"


_IDENT_RE = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")


def validate_table_name(table_name: str, max_len: int = 63):
    """Generic identifier validator shared by every engine. max_len differs
    per engine (Postgres/MySQL: 63/64, Oracle: 30/128 depending on version,
    Snowflake: 255) — each adapter passes its own limit; 63 is a safe
    lowest-common-denominator default."""
    if not table_name:
        raise ValueError(
            "table_name is required. It should contain only letters, "
            "numbers, and underscores, and must start with a letter or underscore."
        )
    if not _IDENT_RE.match(table_name):
        raise ValueError(
            f"Invalid table_name '{table_name}' — only letters, numbers, "
            f"and underscores are allowed"
        )
    if len(table_name) > max_len:
        raise ValueError(f"table_name cannot be longer than {max_len} characters")


def get_schema(df) -> dict:
    """{column: dtype string} for either a pandas or polars DataFrame."""
    import pandas as pd
    import polars as pl

    if isinstance(df, pl.DataFrame):
        return {col: str(dtype) for col, dtype in df.schema.items()}
    elif isinstance(df, pd.DataFrame):
        return {col: str(dtype) for col, dtype in df.dtypes.items()}
    else:
        raise TypeError(f"Unsupported DataFrame type: {type(df)}")


def to_pandas(df):
    import polars as pl

    return df.to_pandas() if isinstance(df, pl.DataFrame) else df


def sanitize_value(v):
    """Engine-agnostic Python-level value cleanup shared by every adapter's
    insert path: NaN/NaT/pd.NA -> None, numpy scalars -> native Python,
    pandas Timestamp -> datetime, list/dict/ndarray -> JSON string (for
    engines whose column ended up TEXT because the value didn't fit the
    declared type). Engine-specific insert code may still do extra work on
    top of this (e.g. Mongo can keep dicts/lists as native BSON instead of
    JSON-stringifying them — see destinations/mongodb.py)."""
    import numpy as np
    import pandas as pd

    if v is None:
        return None
    if isinstance(v, (np.ndarray, list, dict)):
        import json

        try:
            return json.dumps(v.tolist() if isinstance(v, np.ndarray) else v, default=str)
        except (TypeError, ValueError):
            return str(v)
    try:
        if pd.isna(v):
            return None
    except (TypeError, ValueError):
        pass
    if isinstance(v, np.bool_):
        return bool(v)
    if isinstance(v, (np.integer, np.floating)):
        return v.item()
    if isinstance(v, pd.Timestamp):
        return v.to_pydatetime()
    return v
