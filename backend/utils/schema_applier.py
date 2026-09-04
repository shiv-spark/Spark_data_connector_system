"""
User-defined ("custom") schema support for ingestion.

Lets a user say, for any connector/source (file, DB, API, CRM — any type,
any shape) — "column X is an integer, column Y is a date, ..." — and have
that enforced on ingest instead of relying purely on auto-detected dtypes.

Two things happen with a custom_schema:
  1. The incoming DataFrame is *coerced* toward the requested types
     (best-effort — values that can't be cast become NULL, never a hard
     failure, since a user can point this at literally any source and the
     data quality of that source is out of our control).
  2. The Postgres table is *created/evolved* using the requested SQL types
     for those columns, instead of whatever the auto-detector would have
     picked.

Used by utils/ingest_runner.py (step 1) and loaders/db_loader.py (step 2).
"""

import json as _json
import re

import numpy as np
import pandas as pd
import polars as pl

# ── Canonical type vocabulary ────────────────────────────────────────────
# What a user can type (case-insensitive) → canonical internal name.
_TYPE_ALIASES = {
    "integer":   {"integer", "int", "int64", "int32", "bigint", "smallint", "number", "long"},
    "float":     {"float", "double", "float64", "decimal", "real", "numeric"},
    "boolean":   {"boolean", "bool"},
    "date":      {"date"},
    "timestamp": {"timestamp", "datetime", "datetime64", "time"},
    "text":      {"text", "string", "str", "varchar", "char"},
    "json":      {"json", "object", "dict", "list", "array"},
}
_ALIAS_TO_CANONICAL = {alias: canon for canon, aliases in _TYPE_ALIASES.items() for alias in aliases}

CANONICAL_TYPES = sorted(_TYPE_ALIASES.keys())

# Canonical type → Postgres column type, for CREATE TABLE / ALTER TABLE.
CANONICAL_TO_SQL = {
    "integer":   "BIGINT",
    "float":     "DOUBLE PRECISION",
    "boolean":   "BOOLEAN",
    "date":      "DATE",
    "timestamp": "TIMESTAMP",
    "text":      "TEXT",
    "json":      "JSONB",
}


def normalize_type(raw_type: str) -> str:
    """User-typed type string -> canonical type name. Unknown strings fall back to 'text'
    rather than raising, so a typo in one column's type never blocks the whole ingest."""
    key = str(raw_type or "").strip().lower()
    return _ALIAS_TO_CANONICAL.get(key, "text")


def _clean_col(name) -> str:
    """Mirrors loaders.db_loader.clean_column exactly. Duplicated locally
    (rather than imported) to avoid a circular import between this module
    and loaders/db_loader.py."""
    name = str(name).lower().strip()
    name = re.sub(r"[^\w]+", "_", name)
    name = re.sub(r"^_+|_+$", "", name)
    if re.match(r"^\d", name):
        name = f"col_{name}"
    return name or "unnamed"


def resolve_custom_schema(custom_schema: dict | None) -> dict:
    """{"Raw Col Name": "int"} -> {"raw_col_name": "integer"} (cleaned column
    names + canonical types), so it can be matched against the same cleaned
    column names loaders.db_loader.load_to_db() uses everywhere else."""
    if not custom_schema:
        return {}
    resolved = {}
    for col, raw_type in custom_schema.items():
        resolved[_clean_col(col)] = normalize_type(raw_type)
    return resolved


def custom_schema_to_sql(resolved_schema: dict) -> dict:
    """cleaned column name -> Postgres SQL type string."""
    return {col: CANONICAL_TO_SQL.get(t, "TEXT") for col, t in resolved_schema.items()}


def _cast_series(series: "pd.Series", canonical_type: str):
    """Best-effort cast of a pandas Series to canonical_type. Values that
    can't be cast become NULL (never raises) — 'coerce, don't crash' is the
    only strategy that works when the schema can be pointed at data of any
    shape/quality. Returns (new_series, newly_null_count)."""
    before_na = int(series.isna().sum())

    if canonical_type == "integer":
        out = pd.to_numeric(series, errors="coerce")
        # Nullable Int64 keeps failed casts as <NA> instead of silently
        # becoming float64 (which is what plain .astype(int) would force).
        out = out.round()
        try:
            out = out.astype("Int64")
        except (TypeError, ValueError):
            out = out.astype("float64")

    elif canonical_type == "float":
        out = pd.to_numeric(series, errors="coerce").astype("float64")

    elif canonical_type == "boolean":
        def _to_bool(v):
            if pd.isna(v):
                return None
            if isinstance(v, bool):
                return v
            s = str(v).strip().lower()
            if s in ("true", "1", "yes", "y", "t"):
                return True
            if s in ("false", "0", "no", "n", "f"):
                return False
            return None
        out = series.map(_to_bool).astype("boolean")

    elif canonical_type in ("date", "timestamp"):
        out = pd.to_datetime(series, errors="coerce", utc=False)
        if canonical_type == "date":
            out = out.dt.date

    elif canonical_type == "json":
        def _to_json(v):
            if isinstance(v, (dict, list)):
                return _json.dumps(v, default=str)
            if isinstance(v, np.ndarray):
                return _json.dumps(v.tolist(), default=str)
            if v is None or (not isinstance(v, (dict, list)) and pd.isna(v)):
                return None
            s = str(v)
            try:
                _json.loads(s)
                return s
            except (TypeError, ValueError):
                return _json.dumps(s)
        out = series.map(_to_json)

    else:  # text
        out = series.map(lambda v: None if pd.isna(v) else str(v))

    try:
        after_na = int(out.isna().sum())
    except (TypeError, ValueError):
        after_na = sum(1 for v in out if v is None)

    newly_null = max(0, after_na - before_na)
    return out, newly_null


def apply_custom_schema(df, custom_schema: dict | None):
    """Coerce `df` (pandas or polars) toward a user-defined schema.

    - Columns present in BOTH `custom_schema` and `df` get cast to the
      requested type.
    - Columns in `custom_schema` but missing from this particular `df` are
      added as an all-NULL column of that type, so sources with slightly
      different shapes (different files/API pages/etc.) still land in the
      same consistent target schema.
    - Columns in `df` that aren't mentioned in `custom_schema` are left
      untouched — this is additive/selective, not a strict allow-list.

    Returns (df, report) — report = {"applied": {col: type}, "warnings": [str, ...]}.
    Always returns a plain pandas DataFrame when custom_schema is non-empty
    (every downstream step in loaders/db_loader.py already supports pandas),
    otherwise returns `df` unchanged.
    """
    resolved = resolve_custom_schema(custom_schema)
    report = {"applied": {}, "warnings": []}
    if not resolved:
        return df, report

    pdf = df.to_pandas() if isinstance(df, pl.DataFrame) else df.copy()
    col_lookup = {_clean_col(c): c for c in pdf.columns}

    for cleaned_name, canonical_type in resolved.items():
        if cleaned_name in col_lookup:
            actual_col = col_lookup[cleaned_name]
            try:
                pdf[actual_col], newly_null = _cast_series(pdf[actual_col], canonical_type)
                report["applied"][actual_col] = canonical_type
                if newly_null:
                    report["warnings"].append(
                        f"Column '{actual_col}': {newly_null} value(s) couldn't be cast to "
                        f"'{canonical_type}' and were set to NULL."
                    )
            except Exception as e:
                report["warnings"].append(
                    f"Column '{actual_col}': schema cast to '{canonical_type}' failed ({e}) — left as-is."
                )
        else:
            pdf[cleaned_name] = pd.Series([None] * len(pdf), dtype="object")
            report["applied"][cleaned_name] = canonical_type
            report["warnings"].append(
                f"Column '{cleaned_name}' from custom_schema was not present in this source — added as all-NULL."
            )

    return pdf, report
