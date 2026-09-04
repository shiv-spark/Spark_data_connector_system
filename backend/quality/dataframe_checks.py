
# """
# DataFrame-level Data Quality Checks
# ────────────────────────────────────
# Unlike quality/checks.py (which runs SQL against a table that is ALREADY
# loaded into a warehouse), these checks run purely in-memory — BEFORE any DB
# write happens. This lets ingestion be blocked before bad data ever reaches
# the target table, which the post-load SQL gate in quality/checks.py cannot
# do (see the NOTE in utils/ingest_runner.py about why "block" there can't
# roll back an already-committed load).
 
# Connectors in this app return either a Polars DataFrame (csv/excel/api/s3)
# or a Pandas DataFrame (snowflake/google_sheets), but these checks are
# written against pandas semantics (df.duplicated(), dtype.kind, etc.), so
# run_dataframe_quality_checks() normalizes any Polars input to pandas right
# at the top before doing anything else.
 
# Every check function returns a plain dict shaped like quality/checks.py's
# `_result()` output, so results from both gates can be logged/displayed the
# same way. `run_dataframe_quality_checks()` is the orchestrator the ingest
# runner calls; it mirrors quality/router.run_quality_checks()'s shape
# (status / total_checks / passed / failed / results) minus persistence,
# since this gate does not need its own audit tables — it runs inline,
# before a run_id even exists yet in some flows.
# """
 
# from typing import Any, Dict, List, Optional
 
# import pandas as pd
 
# try:
#     import polars as pl
# except ImportError:  # pragma: no cover - polars is a hard dependency elsewhere in the app
#     pl = None
 
 
# def _result(check_name: str, status: str, failed_rows: int = 0,
#             source_value: Any = None, target_value: Any = None,
#             message: str = "") -> Dict[str, Any]:
#     return {
#         "check_name": check_name,
#         "status": status,
#         "failed_rows": failed_rows,
#         "source_value": source_value,
#         "target_value": target_value,
#         "message": message,
#     }
 
 
# def check_empty_dataframe(df: pd.DataFrame) -> Dict[str, Any]:
#     row_count = len(df)
#     status = "FAIL" if row_count == 0 else "PASS"
#     return _result(
#         "EMPTY_DATAFRAME_CHECK", status,
#         failed_rows=1 if status == "FAIL" else 0,
#         source_value=row_count,
#         message="DataFrame has 0 rows" if status == "FAIL" else f"{row_count} row(s) fetched",
#     )
 
 
# def check_required_columns(df: pd.DataFrame, required_columns: List[str]) -> Dict[str, Any]:
#     actual_cols = set(df.columns)
#     missing = [c for c in required_columns if c not in actual_cols]
#     status = "PASS" if not missing else "FAIL"
#     return _result(
#         "REQUIRED_COLUMNS_CHECK", status,
#         failed_rows=len(missing),
#         target_value=required_columns,
#         source_value=list(df.columns),
#         message="All required columns present" if status == "PASS"
#                 else f"Missing column(s): {missing}",
#     )
 
 
# def check_null_percentage(df: pd.DataFrame, null_thresholds: Dict[str, float]) -> List[Dict[str, Any]]:
#     results = []
#     total_rows = len(df)
#     for col, max_pct in null_thresholds.items():
#         if col not in df.columns:
#             results.append(_result(
#                 f"NULL_PCT_CHECK[{col}]", "FAIL",
#                 message=f"Column '{col}' not found in dataframe",
#             ))
#             continue
#         if total_rows == 0:
#             results.append(_result(
#                 f"NULL_PCT_CHECK[{col}]", "PASS",
#                 message="No rows to evaluate (dataframe is empty)",
#             ))
#             continue
#         null_count = int(df[col].isna().sum())
#         null_pct = round((null_count / total_rows) * 100, 2)
#         status = "PASS" if null_pct <= max_pct else "FAIL"
#         results.append(_result(
#             f"NULL_PCT_CHECK[{col}]", status,
#             failed_rows=null_count,
#             source_value=null_pct, target_value=max_pct,
#             message=f"{col}: {null_pct}% NULL (threshold {max_pct}%, {null_count}/{total_rows} rows)",
#         ))
#     return results
 
 
# def check_duplicate_rows(df: pd.DataFrame, subset: Optional[List[str]] = None) -> Dict[str, Any]:
#     if subset:
#         missing = [c for c in subset if c not in df.columns]
#         if missing:
#             return _result(
#                 "DUPLICATE_ROWS_CHECK", "FAIL",
#                 message=f"Duplicate-check column(s) not found: {missing}",
#             )
#     dup_mask = df.duplicated(subset=subset, keep="first")
#     dup_count = int(dup_mask.sum())
#     status = "PASS" if dup_count == 0 else "FAIL"
#     label = f"on ({', '.join(subset)})" if subset else "across full row"
#     return _result(
#         "DUPLICATE_ROWS_CHECK", status,
#         failed_rows=dup_count,
#         message=f"{dup_count} duplicate row(s) {label}",
#     )
 
 
# _KIND_MAP = {
#     "numeric": "if",
#     "int": "i",
#     "float": "f",
#     "string": "OSU",
#     "text": "OSU",
#     "datetime": "M",
#     "date": "M",
#     "bool": "b",
#     "boolean": "b",
# }
 
 
# def check_dtype_mismatch(df: pd.DataFrame, expected_dtypes: Dict[str, str]) -> List[Dict[str, Any]]:
#     results = []
#     for col, expected in expected_dtypes.items():
#         if col not in df.columns:
#             results.append(_result(
#                 f"DTYPE_CHECK[{col}]", "FAIL",
#                 message=f"Column '{col}' not found in dataframe",
#             ))
#             continue
 
#         expected_key = str(expected).lower().strip()
#         allowed_kinds = _KIND_MAP.get(expected_key)
#         actual_kind = df[col].dtype.kind
#         actual_dtype_name = str(df[col].dtype)
 
#         if allowed_kinds and actual_kind in allowed_kinds:
#             results.append(_result(
#                 f"DTYPE_CHECK[{col}]", "PASS",
#                 source_value=actual_dtype_name, target_value=expected_key,
#                 message=f"{col}: dtype '{actual_dtype_name}' matches expected '{expected_key}'",
#             ))
#             continue
 
#         non_null = df[col].dropna()
#         if expected_key in ("numeric", "int", "float"):
#             coerced = pd.to_numeric(non_null, errors="coerce")
#             bad_count = int(coerced.isna().sum())
#         elif expected_key in ("datetime", "date"):
#             coerced = pd.to_datetime(non_null, errors="coerce")
#             bad_count = int(coerced.isna().sum())
#         elif expected_key in ("bool", "boolean"):
#             bad_count = int((~non_null.isin([True, False, 0, 1, "true", "false",
#                                               "True", "False", "0", "1"])).sum())
#         else:
#             bad_count = 0
 
#         status = "PASS" if bad_count == 0 else "FAIL"
#         results.append(_result(
#             f"DTYPE_CHECK[{col}]", status,
#             failed_rows=bad_count,
#             source_value=actual_dtype_name, target_value=expected_key,
#             message=(
#                 f"{col}: stored as '{actual_dtype_name}' but {bad_count} value(s) "
#                 f"don't convert cleanly to '{expected_key}'"
#                 if bad_count else
#                 f"{col}: stored as '{actual_dtype_name}' but all values convert cleanly to '{expected_key}'"
#             ),
#         ))
#     return results
 
 
# def run_dataframe_quality_checks(df: Any, config: Dict[str, Any]) -> Dict[str, Any]:
#     config = config or {}
#     results: List[Dict[str, Any]] = []
 
#     if pl is not None and isinstance(df, pl.DataFrame):
#         df = df.to_pandas()
 
#     if config.get("check_empty", True):
#         results.append(check_empty_dataframe(df))
 
#     required_columns = config.get("required_columns")
#     if required_columns:
#         results.append(check_required_columns(df, required_columns))
 
#     null_thresholds = config.get("null_thresholds")
#     if null_thresholds:
#         results.extend(check_null_percentage(df, null_thresholds))
 
#     if config.get("check_duplicates") or config.get("duplicate_subset"):
#         results.append(check_duplicate_rows(df, config.get("duplicate_subset")))
 
#     expected_dtypes = config.get("expected_dtypes")
#     if expected_dtypes:
#         results.extend(check_dtype_mismatch(df, expected_dtypes))
 
#     passed = sum(1 for r in results if r["status"] == "PASS")
#     failed = sum(1 for r in results if r["status"] == "FAIL")
#     overall_status = "PASS" if failed == 0 else "FAIL"
 
#     return {
#         "status": overall_status,
#         "total_checks": len(results),
#         "passed": passed,
#         "failed": failed,
#         "results": results,
#     }
 
"""
DataFrame-level Data Quality Checks
────────────────────────────────────
Unlike quality/checks.py (which runs SQL against a table that is ALREADY
loaded into a warehouse), these checks run purely in-memory — BEFORE any DB
write happens. This lets ingestion be blocked before bad data ever reaches
the target table, which the post-load SQL gate in quality/checks.py cannot
do (see the NOTE in utils/ingest_runner.py about why "block" there can't
roll back an already-committed load).

Connectors in this app return either a Polars DataFrame (csv/excel/api/s3)
or a Pandas DataFrame (snowflake/google_sheets), but these checks are
written against pandas semantics (df.duplicated(), dtype.kind, etc.), so
run_dataframe_quality_checks() normalizes any Polars input to pandas right
at the top before doing anything else.

Every check function returns a plain dict shaped like quality/checks.py's
`_result()` output, so results from both gates can be logged/displayed the
same way. `run_dataframe_quality_checks()` is the orchestrator the ingest
runner calls; it mirrors quality/router.run_quality_checks()'s shape
(status / total_checks / passed / failed / results) minus persistence,
since this gate does not need its own audit tables — it runs inline,
before a run_id even exists yet in some flows.
"""

from typing import Any, Dict, List, Optional
import re

import pandas as pd

try:
    import polars as pl
except ImportError:  # pragma: no cover - polars is a hard dependency elsewhere in the app
    pl = None


def _result(check_name: str, status: str, failed_rows: int = 0,
            source_value: Any = None, target_value: Any = None,
            message: str = "") -> Dict[str, Any]:
    return {
        "check_name": check_name,
        "status": status,
        "failed_rows": failed_rows,
        "source_value": source_value,
        "target_value": target_value,
        "message": message,
    }


def check_empty_dataframe(df: pd.DataFrame) -> Dict[str, Any]:
    row_count = len(df)
    status = "FAIL" if row_count == 0 else "PASS"
    return _result(
        "EMPTY_DATAFRAME_CHECK", status,
        failed_rows=1 if status == "FAIL" else 0,
        source_value=row_count,
        message="DataFrame has 0 rows" if status == "FAIL" else f"{row_count} row(s) fetched",
    )


def check_required_columns(df: pd.DataFrame, required_columns: List[str]) -> Dict[str, Any]:
    actual_cols = set(df.columns)
    missing = [c for c in required_columns if c not in actual_cols]
    status = "PASS" if not missing else "FAIL"
    return _result(
        "REQUIRED_COLUMNS_CHECK", status,
        failed_rows=len(missing),
        target_value=required_columns,
        source_value=list(df.columns),
        message="All required columns present" if status == "PASS"
                else f"Missing column(s): {missing}",
    )


def check_null_percentage(df: pd.DataFrame, null_thresholds: Dict[str, float]) -> List[Dict[str, Any]]:
    results = []
    total_rows = len(df)
    for col, max_pct in null_thresholds.items():
        if col not in df.columns:
            results.append(_result(
                f"NULL_PCT_CHECK[{col}]", "FAIL",
                message=f"Column '{col}' not found in dataframe",
            ))
            continue
        if total_rows == 0:
            results.append(_result(
                f"NULL_PCT_CHECK[{col}]", "PASS",
                message="No rows to evaluate (dataframe is empty)",
            ))
            continue
        null_count = int(df[col].isna().sum())
        null_pct = round((null_count / total_rows) * 100, 2)
        status = "PASS" if null_pct <= max_pct else "FAIL"
        results.append(_result(
            f"NULL_PCT_CHECK[{col}]", status,
            failed_rows=null_count,
            source_value=null_pct, target_value=max_pct,
            message=f"{col}: {null_pct}% NULL (threshold {max_pct}%, {null_count}/{total_rows} rows)",
        ))
    return results


def check_duplicate_rows(df: pd.DataFrame, subset: Optional[List[str]] = None) -> Dict[str, Any]:
    if subset:
        missing = [c for c in subset if c not in df.columns]
        if missing:
            return _result(
                "DUPLICATE_ROWS_CHECK", "FAIL",
                message=f"Duplicate-check column(s) not found: {missing}",
            )
    dup_mask = df.duplicated(subset=subset, keep="first")
    dup_count = int(dup_mask.sum())
    status = "PASS" if dup_count == 0 else "FAIL"
    label = f"on ({', '.join(subset)})" if subset else "across full row"
    return _result(
        "DUPLICATE_ROWS_CHECK", status,
        failed_rows=dup_count,
        message=f"{dup_count} duplicate row(s) {label}",
    )


_KIND_MAP = {
    "numeric": "if",
    "int": "i",
    "float": "f",
    "string": "OSU",
    "text": "OSU",
    "datetime": "M",
    "date": "M",
    "bool": "b",
    "boolean": "b",
}


def check_dtype_mismatch(df: pd.DataFrame, expected_dtypes: Dict[str, str]) -> List[Dict[str, Any]]:
    results = []
    for col, expected in expected_dtypes.items():
        if col not in df.columns:
            results.append(_result(
                f"DTYPE_CHECK[{col}]", "FAIL",
                message=f"Column '{col}' not found in dataframe",
            ))
            continue

        expected_key = str(expected).lower().strip()
        allowed_kinds = _KIND_MAP.get(expected_key)
        actual_kind = df[col].dtype.kind
        actual_dtype_name = str(df[col].dtype)

        if allowed_kinds and actual_kind in allowed_kinds:
            results.append(_result(
                f"DTYPE_CHECK[{col}]", "PASS",
                source_value=actual_dtype_name, target_value=expected_key,
                message=f"{col}: dtype '{actual_dtype_name}' matches expected '{expected_key}'",
            ))
            continue

        non_null = df[col].dropna()
        if expected_key in ("numeric", "int", "float"):
            coerced = pd.to_numeric(non_null, errors="coerce")
            bad_count = int(coerced.isna().sum())
        elif expected_key in ("datetime", "date"):
            coerced = pd.to_datetime(non_null, errors="coerce")
            bad_count = int(coerced.isna().sum())
        elif expected_key in ("bool", "boolean"):
            bad_count = int((~non_null.isin([True, False, 0, 1, "true", "false",
                                              "True", "False", "0", "1"])).sum())
        else:
            bad_count = 0

        status = "PASS" if bad_count == 0 else "FAIL"
        results.append(_result(
            f"DTYPE_CHECK[{col}]", status,
            failed_rows=bad_count,
            source_value=actual_dtype_name, target_value=expected_key,
            message=(
                f"{col}: stored as '{actual_dtype_name}' but {bad_count} value(s) "
                f"don't convert cleanly to '{expected_key}'"
                if bad_count else
                f"{col}: stored as '{actual_dtype_name}' but all values convert cleanly to '{expected_key}'"
            ),
        ))
    return results


# ─────────────────────────────────────────────────────────────────────────
# Value range check — numeric column min/max bounds
# range_checks = {"age": {"min": 0, "max": 120}, "price": {"min": 0}}
# Non-numeric / unparseable values are ignored here (dtype check catches
# those separately) — this check only judges values that ARE numeric.
# ─────────────────────────────────────────────────────────────────────────
def check_value_range(df: pd.DataFrame, range_checks: Dict[str, Dict[str, float]]) -> List[Dict[str, Any]]:
    results = []
    for col, bounds in range_checks.items():
        if col not in df.columns:
            results.append(_result(
                f"RANGE_CHECK[{col}]", "FAIL",
                message=f"Column '{col}' not found in dataframe",
            ))
            continue

        min_bound = bounds.get("min")
        max_bound = bounds.get("max")

        values = pd.to_numeric(df[col], errors="coerce").dropna()
        bad_mask = pd.Series(False, index=values.index)
        if min_bound is not None:
            bad_mask |= values < min_bound
        if max_bound is not None:
            bad_mask |= values > max_bound

        bad_count = int(bad_mask.sum())
        status = "PASS" if bad_count == 0 else "FAIL"
        bound_label = f"[{min_bound if min_bound is not None else '-inf'}, {max_bound if max_bound is not None else '+inf'}]"
        results.append(_result(
            f"RANGE_CHECK[{col}]", status,
            failed_rows=bad_count,
            target_value=bounds,
            message=f"{col}: {bad_count} value(s) outside {bound_label}",
        ))
    return results


# ─────────────────────────────────────────────────────────────────────────
# Regex / pattern match check
# pattern_checks = {"email": ".+@.+\\..+", "phone": "^\\d{10}$"}
# Only non-null values are checked; nulls are the null_thresholds check's job.
# ─────────────────────────────────────────────────────────────────────────
def check_pattern_match(df: pd.DataFrame, pattern_checks: Dict[str, str]) -> List[Dict[str, Any]]:
    results = []
    for col, pattern in pattern_checks.items():
        if col not in df.columns:
            results.append(_result(
                f"PATTERN_CHECK[{col}]", "FAIL",
                message=f"Column '{col}' not found in dataframe",
            ))
            continue

        try:
            compiled = re.compile(pattern)
        except re.error as e:
            results.append(_result(
                f"PATTERN_CHECK[{col}]", "FAIL",
                message=f"Invalid regex pattern for '{col}': {e}",
            ))
            continue

        non_null = df[col].dropna().astype(str)
        matches = non_null.apply(lambda v: bool(compiled.search(v)))
        bad_count = int((~matches).sum())
        status = "PASS" if bad_count == 0 else "FAIL"
        results.append(_result(
            f"PATTERN_CHECK[{col}]", status,
            failed_rows=bad_count,
            target_value=pattern,
            message=f"{col}: {bad_count} value(s) don't match pattern '{pattern}'",
        ))
    return results


# ─────────────────────────────────────────────────────────────────────────
# Allowed values (enum) check
# allowed_values = {"status": ["active", "inactive", "pending"]}
# Comparison is exact string match (case-sensitive) against non-null values.
# ─────────────────────────────────────────────────────────────────────────
def check_allowed_values(df: pd.DataFrame, allowed_values: Dict[str, List[Any]]) -> List[Dict[str, Any]]:
    results = []
    for col, allowed in allowed_values.items():
        if col not in df.columns:
            results.append(_result(
                f"ENUM_CHECK[{col}]", "FAIL",
                message=f"Column '{col}' not found in dataframe",
            ))
            continue

        allowed_set = set(allowed)
        non_null = df[col].dropna()
        bad_values = non_null[~non_null.isin(allowed_set)]
        bad_count = int(len(bad_values))
        status = "PASS" if bad_count == 0 else "FAIL"

        unexpected_sample = sorted(set(bad_values.astype(str).tolist()))[:5]
        results.append(_result(
            f"ENUM_CHECK[{col}]", status,
            failed_rows=bad_count,
            target_value=allowed,
            message=(
                f"{col}: {bad_count} value(s) not in allowed set {allowed}"
                + (f" — e.g. {unexpected_sample}" if unexpected_sample else "")
                if bad_count else
                f"{col}: all values within allowed set {allowed}"
            ),
        ))
    return results


def run_dataframe_quality_checks(df: Any, config: Dict[str, Any]) -> Dict[str, Any]:
    config = config or {}
    results: List[Dict[str, Any]] = []

    if pl is not None and isinstance(df, pl.DataFrame):
        df = df.to_pandas()

    if config.get("check_empty", True):
        results.append(check_empty_dataframe(df))

    required_columns = config.get("required_columns")
    if required_columns:
        results.append(check_required_columns(df, required_columns))

    null_thresholds = config.get("null_thresholds")
    if null_thresholds:
        results.extend(check_null_percentage(df, null_thresholds))

    if config.get("check_duplicates") or config.get("duplicate_subset"):
        results.append(check_duplicate_rows(df, config.get("duplicate_subset")))

    expected_dtypes = config.get("expected_dtypes")
    if expected_dtypes:
        results.extend(check_dtype_mismatch(df, expected_dtypes))

    range_checks = config.get("range_checks")
    if range_checks:
        results.extend(check_value_range(df, range_checks))

    pattern_checks = config.get("pattern_checks")
    if pattern_checks:
        results.extend(check_pattern_match(df, pattern_checks))

    allowed_values = config.get("allowed_values")
    if allowed_values:
        results.extend(check_allowed_values(df, allowed_values))

    from quality.fix_suggestions import annotate_results
    annotate_results(results, source="dataframe")

    passed = sum(1 for r in results if r["status"] == "PASS")
    failed = sum(1 for r in results if r["status"] == "FAIL")
    overall_status = "PASS" if failed == 0 else "FAIL"

    return {
        "status": overall_status,
        "total_checks": len(results),
        "passed": passed,
        "failed": failed,
        "results": results,
    }