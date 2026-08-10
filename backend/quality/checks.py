

# """
# Generic Data Quality Checks
# ───────────────────────────
# Unlike the original standalone version (which hardcoded Postgres + Snowflake
# credentials and a fixed 4-table list), these checks run against ANY
# connection already saved in `saved_connections`, using the project's
# existing `sql_executors` abstraction (sql_executors.get_executor).

# Every check function takes a live BaseSqlExecutor instance and returns a
# plain dict matching the `quality_results` table columns, so the router can
# insert results directly without any extra mapping.
# """

# import re
# from typing import Any, Dict, List, Optional

# from sql_executors.base import BaseSqlExecutor

# # Only allow simple identifiers (letters, numbers, underscore, dot for
# # schema.table). Table/column names always come from the platform's own
# # schema-introspection endpoints or from values the user typed into a
# # "table name" field — never from raw free-text — but we validate anyway
# # since these values get interpolated into SQL text.
# _IDENTIFIER_RE = re.compile(r"^[A-Za-z0-9_.]+$")


# def _safe_identifier(name: str) -> str:
#     if not _IDENTIFIER_RE.match(name):
#         raise ValueError(f"Unsafe identifier rejected: {name!r}")
#     return name


# def _split_schema_table(table_name: str) -> tuple:
#     """'public.customers' -> ('public', 'customers'); 'customers' -> (None, 'customers')."""
#     table = _safe_identifier(table_name)
#     if "." in table:
#         schema, _, bare = table.rpartition(".")
#         return schema, bare
#     return None, table


# def _sql_literal(value: str) -> str:
#     """Escape a plain string for use as a SQL string literal (single-quote doubling)."""
#     return str(value).replace("'", "''")


# async def _scalar(executor: BaseSqlExecutor, query: str) -> Any:
#     result = await executor.execute(query, limit=1, timeout_seconds=30)
#     if not result.rows:
#         return None
#     return result.rows[0][0]


# def _result(table_name, check_name, status, failed_rows=0,
#             source_value=None, target_value=None, message=""):
#     return {
#         "table_name": table_name,
#         "check_name": check_name,
#         "status": status,
#         "failed_rows": failed_rows,
#         "source_value": source_value,
#         "target_value": target_value,
#         "message": message,
#     }


# # ─────────────────────────────────────────────────────────────────────────
# # Row count
# # ─────────────────────────────────────────────────────────────────────────
# async def run_row_count_check(
#     executor: BaseSqlExecutor,
#     table_name: str,
#     expected_min_rows: Optional[int] = None,
# ) -> Dict[str, Any]:
#     table = _safe_identifier(table_name)
#     count = await _scalar(executor, f"SELECT COUNT(*) FROM {table}")

#     if expected_min_rows is None:
#         # Informational only — no threshold given, so we can't fail it.
#         return _result(table_name, "ROW_COUNT", "PASS",
#                         source_value=count,
#                         message=f"{table_name} has {count} rows")

#     status = "PASS" if count >= expected_min_rows else "FAIL"
#     return _result(
#         table_name, "ROW_COUNT", status,
#         failed_rows=0 if status == "PASS" else expected_min_rows - count,
#         source_value=count, target_value=expected_min_rows,
#         message=f"{table_name}: {count} rows (expected >= {expected_min_rows})",
#     )


# # ─────────────────────────────────────────────────────────────────────────
# # Null check
# # ─────────────────────────────────────────────────────────────────────────
# async def run_null_check(
#     executor: BaseSqlExecutor,
#     table_name: str,
#     columns: List[str],
# ) -> List[Dict[str, Any]]:
#     table = _safe_identifier(table_name)
#     results = []
#     for col in columns:
#         column = _safe_identifier(col)
#         null_count = await _scalar(
#             executor, f"SELECT COUNT(*) FROM {table} WHERE {column} IS NULL"
#         )
#         status = "PASS" if null_count == 0 else "FAIL"
#         results.append(_result(
#             table_name, f"NULL_CHECK[{col}]", status,
#             failed_rows=null_count,
#             message=f"{col}: {null_count} NULL value(s)",
#         ))
#     return results


# # ─────────────────────────────────────────────────────────────────────────
# # Duplicate check (based on primary key columns)
# # ─────────────────────────────────────────────────────────────────────────
# async def run_duplicate_check(
#     executor: BaseSqlExecutor,
#     table_name: str,
#     key_columns_list: List[str],
#     check_label: str = "DUPLICATE_CHECK",
# ) -> Dict[str, Any]:
#     """Generic duplicate-group check. Used both for primary-key uniqueness
#     (Uniqueness) and for arbitrary business-key duplicate detection
#     (Duplicate Detection), which are conceptually different even though the
#     SQL is the same — the check_label distinguishes them in results."""
#     table = _safe_identifier(table_name)
#     key_columns = ", ".join(_safe_identifier(c) for c in key_columns_list)

#     dup_count = await _scalar(executor, f"""
#         SELECT COUNT(*) FROM (
#             SELECT {key_columns} FROM {table}
#             GROUP BY {key_columns}
#             HAVING COUNT(*) > 1
#         ) dup
#     """)
#     status = "PASS" if dup_count == 0 else "FAIL"
#     return _result(
#         table_name, check_label, status,
#         failed_rows=dup_count,
#         message=f"{dup_count} duplicate group(s) on ({key_columns})",
#     )


# # ─────────────────────────────────────────────────────────────────────────
# # Business rule check — a boolean SQL condition that SHOULD MATCH ZERO rows
# # e.g. condition="price <= 0"  → any row matching this is a violation
# # ─────────────────────────────────────────────────────────────────────────
# async def run_business_rule_check(
#     executor: BaseSqlExecutor,
#     table_name: str,
#     column: str,
#     condition: str,
# ) -> Dict[str, Any]:
#     table = _safe_identifier(table_name)
#     # `condition` is a boolean SQL expression (e.g. "price <= 0"), not a bare
#     # identifier, so we don't run it through _safe_identifier. It must come
#     # from a trusted, admin-defined rule set (see router.py), never from
#     # free-text user input, since it is interpolated directly into SQL.
#     violations = await _scalar(
#         executor, f"SELECT COUNT(*) FROM {table} WHERE {condition}"
#     )
#     status = "PASS" if violations == 0 else "FAIL"
#     return _result(
#         table_name, f"BUSINESS_RULE[{column}]", status,
#         failed_rows=violations,
#         message=f"Rule '{condition}': {violations} violation(s)",
#     )


# # ─────────────────────────────────────────────────────────────────────────
# # Freshness check
# # ─────────────────────────────────────────────────────────────────────────
# async def run_freshness_check(
#     executor: BaseSqlExecutor,
#     table_name: str,
#     timestamp_column: str,
#     threshold_hours: float,
# ) -> Dict[str, Any]:
#     table = _safe_identifier(table_name)
#     column = _safe_identifier(timestamp_column)

#     age_hours = await _scalar(executor, f"""
#         SELECT EXTRACT(EPOCH FROM (now() - MAX({column}))) / 3600.0
#         FROM {table}
#     """)

#     if age_hours is None:
#         return _result(table_name, "FRESHNESS_CHECK", "FAIL",
#                         message=f"No rows found in {table_name}")

#     status = "PASS" if age_hours <= threshold_hours else "FAIL"
#     return _result(
#         table_name, "FRESHNESS_CHECK", status,
#         source_value=round(float(age_hours), 2), target_value=threshold_hours,
#         message=f"Last update {round(float(age_hours), 1)}h ago (threshold {threshold_hours}h)",
#     )


# # ─────────────────────────────────────────────────────────────────────────
# # Referential integrity — child rows whose FK value has no matching parent
# # ─────────────────────────────────────────────────────────────────────────
# async def run_referential_integrity_check(
#     executor: BaseSqlExecutor,
#     child_table: str,
#     child_column: str,
#     parent_table: str,
#     parent_column: str,
# ) -> Dict[str, Any]:
#     child = _safe_identifier(child_table)
#     child_col = _safe_identifier(child_column)
#     parent = _safe_identifier(parent_table)
#     parent_col = _safe_identifier(parent_column)

#     orphans = await _scalar(executor, f"""
#         SELECT COUNT(*) FROM {child} c
#         WHERE c.{child_col} IS NOT NULL
#           AND NOT EXISTS (
#               SELECT 1 FROM {parent} p WHERE p.{parent_col} = c.{child_col}
#           )
#     """)
#     status = "PASS" if orphans == 0 else "FAIL"
#     return _result(
#         child_table, f"REFERENTIAL_INTEGRITY[{child_column}->{parent_table}.{parent_column}]",
#         status, failed_rows=orphans,
#         message=f"{orphans} orphan row(s) in {child_table}.{child_column}",
#     )


# # ─────────────────────────────────────────────────────────────────────────
# # Data Type Validation — actual column type (information_schema) vs expected
# # e.g. expected_types = {"customer_id": "integer", "email": "varchar"}
# # Matching is a case-insensitive substring match so "int" matches "integer"/
# # "bigint" and "varchar" matches "character varying", across Postgres and
# # Snowflake's differing type-name spellings.
# # ─────────────────────────────────────────────────────────────────────────
# async def run_data_type_check(
#     executor: BaseSqlExecutor,
#     table_name: str,
#     expected_types: Dict[str, str],
# ) -> List[Dict[str, Any]]:
#     schema, bare_table = _split_schema_table(table_name)
#     where_schema = f"AND table_schema = '{_sql_literal(schema)}'" if schema else ""
#     rows_result = await executor.execute(f"""
#         SELECT column_name, data_type
#         FROM information_schema.columns
#         WHERE table_name = '{_sql_literal(bare_table)}' {where_schema}
#     """, limit=500, timeout_seconds=30)

#     actual_types = {r[0].lower(): str(r[1]).lower() for r in rows_result.rows}

#     results = []
#     for column, expected_type in expected_types.items():
#         actual = actual_types.get(column.lower())
#         if actual is None:
#             results.append(_result(
#                 table_name, f"DATA_TYPE[{column}]", "FAIL",
#                 message=f"Column '{column}' not found in {table_name}",
#             ))
#             continue
#         match = expected_type.lower() in actual or actual in expected_type.lower()
#         status = "PASS" if match else "FAIL"
#         results.append(_result(
#             table_name, f"DATA_TYPE[{column}]", status,
#             source_value=actual, target_value=expected_type.lower(),
#             message=f"{column}: actual '{actual}' vs expected '{expected_type}'",
#         ))
#     return results


# # ─────────────────────────────────────────────────────────────────────────
# # Range Checks — values outside [min, max] for a numeric/date column
# # e.g. ranges = {"age": {"min": 0, "max": 120}, "discount_pct": {"max": 100}}
# # ─────────────────────────────────────────────────────────────────────────
# async def run_range_check(
#     executor: BaseSqlExecutor,
#     table_name: str,
#     ranges: Dict[str, Dict[str, float]],
# ) -> List[Dict[str, Any]]:
#     table = _safe_identifier(table_name)
#     results = []
#     for col, bounds in ranges.items():
#         column = _safe_identifier(col)
#         conditions = []
#         if bounds.get("min") is not None:
#             conditions.append(f"{column} < {bounds['min']}")
#         if bounds.get("max") is not None:
#             conditions.append(f"{column} > {bounds['max']}")
#         if not conditions:
#             continue
#         where_clause = " OR ".join(conditions)
#         violations = await _scalar(
#             executor, f"SELECT COUNT(*) FROM {table} WHERE {where_clause}"
#         )
#         status = "PASS" if violations == 0 else "FAIL"
#         bounds_desc = f"[{bounds.get('min', '-inf')}, {bounds.get('max', '+inf')}]"
#         results.append(_result(
#             table_name, f"RANGE_CHECK[{col}]", status,
#             failed_rows=violations,
#             message=f"{col}: {violations} row(s) outside {bounds_desc}",
#         ))
#     return results


# # ─────────────────────────────────────────────────────────────────────────
# # Outlier Detection — IQR (Tukey's fences) method, works on Postgres and
# # Snowflake since both support PERCENTILE_CONT ... WITHIN GROUP.
# # ─────────────────────────────────────────────────────────────────────────
# async def run_outlier_check(
#     executor: BaseSqlExecutor,
#     table_name: str,
#     column: str,
#     iqr_multiplier: float = 1.5,
# ) -> Dict[str, Any]:
#     table = _safe_identifier(table_name)
#     col = _safe_identifier(column)

#     row = await executor.execute(f"""
#         WITH stats AS (
#             SELECT
#                 percentile_cont(0.25) WITHIN GROUP (ORDER BY {col}) AS q1,
#                 percentile_cont(0.75) WITHIN GROUP (ORDER BY {col}) AS q3
#             FROM {table}
#             WHERE {col} IS NOT NULL
#         )
#         SELECT
#             (SELECT COUNT(*) FROM {table}, stats
#              WHERE {col} < stats.q1 - {iqr_multiplier} * (stats.q3 - stats.q1)
#                 OR {col} > stats.q3 + {iqr_multiplier} * (stats.q3 - stats.q1)) AS outliers,
#             stats.q1, stats.q3
#         FROM stats
#     """, limit=1, timeout_seconds=30)

#     if not row.rows:
#         return _result(table_name, f"OUTLIER_CHECK[{column}]", "PASS",
#                         message=f"No data to evaluate in {table_name}.{column}")

#     outliers, q1, q3 = row.rows[0][0], row.rows[0][1], row.rows[0][2]
#     status = "PASS" if outliers == 0 else "FAIL"
#     return _result(
#         table_name, f"OUTLIER_CHECK[{column}]", status,
#         failed_rows=outliers,
#         source_value=f"Q1={q1}, Q3={q3}",
#         message=f"{column}: {outliers} outlier(s) beyond {iqr_multiplier}×IQR of [{q1}, {q3}]",
#     )


# # ─────────────────────────────────────────────────────────────────────────
# # Consistency — compare an aggregate expression between two tables in the
# # SAME connection (e.g. SUM(amount) in `orders` vs SUM(amount) in
# # `order_summary`). Cross-connection consistency is intentionally out of
# # scope for now (see Accuracy / Record-Count source-vs-target, deferred).
# # ─────────────────────────────────────────────────────────────────────────
# async def run_consistency_check(
#     executor: BaseSqlExecutor,
#     table_a: str,
#     expr_a: str,
#     table_b: str,
#     expr_b: str,
#     tolerance: float = 0,
# ) -> Dict[str, Any]:
#     tbl_a = _safe_identifier(table_a)
#     tbl_b = _safe_identifier(table_b)
#     # expr_a / expr_b are trusted aggregate expressions (e.g. "SUM(amount)"),
#     # analogous to business_rules.condition — never free-text user input.
#     value_a = await _scalar(executor, f"SELECT {expr_a} FROM {tbl_a}")
#     value_b = await _scalar(executor, f"SELECT {expr_b} FROM {tbl_b}")

#     try:
#         diff = abs(float(value_a) - float(value_b))
#         status = "PASS" if diff <= tolerance else "FAIL"
#     except (TypeError, ValueError):
#         diff = None
#         status = "PASS" if value_a == value_b else "FAIL"

#     return _result(
#         f"{table_a} vs {table_b}", "CONSISTENCY_CHECK", status,
#         source_value=value_a, target_value=value_b,
#         message=(
#             f"{table_a}.[{expr_a}]={value_a} vs {table_b}.[{expr_b}]={value_b}"
#             + (f" (diff={diff}, tolerance={tolerance})" if diff is not None else "")
#         ),
#     )


# # ─────────────────────────────────────────────────────────────────────────
# # Schema Validation
# #   1) Manual mode: compare actual columns/types against a user-supplied
# #      expected schema.
# #   2) Baseline mode: compare actual columns/types against a stored
# #      snapshot (see quality/router.py for snapshot persistence); the
# #      caller passes in the previously stored snapshot as `baseline`.
# # Both modes share the same diff logic — detect missing, new, and
# # type-changed columns.
# # ─────────────────────────────────────────────────────────────────────────
# async def get_actual_schema(
#     executor: BaseSqlExecutor, table_name: str
# ) -> Dict[str, str]:
#     """Returns {column_name: data_type} for the live table."""
#     schema, bare_table = _split_schema_table(table_name)
#     where_schema = f"AND table_schema = '{_sql_literal(schema)}'" if schema else ""
#     result = await executor.execute(f"""
#         SELECT column_name, data_type
#         FROM information_schema.columns
#         WHERE table_name = '{_sql_literal(bare_table)}' {where_schema}
#     """, limit=500, timeout_seconds=30)
#     return {r[0]: str(r[1]) for r in result.rows}


# def diff_schema(
#     table_name: str,
#     actual: Dict[str, str],
#     expected: Dict[str, str],
#     check_name: str = "SCHEMA_VALIDATION",
# ) -> Dict[str, Any]:
#     actual_cols = {k.lower(): v.lower() for k, v in actual.items()}
#     expected_cols = {k.lower(): v.lower() for k, v in expected.items()}

#     missing = sorted(set(expected_cols) - set(actual_cols))   # in expected, gone from actual
#     new = sorted(set(actual_cols) - set(expected_cols))       # in actual, not in expected
#     changed = sorted(
#         col for col in (set(actual_cols) & set(expected_cols))
#         if expected_cols[col] not in actual_cols[col] and actual_cols[col] not in expected_cols[col]
#     )

#     status = "PASS" if not (missing or new or changed) else "FAIL"
#     parts = []
#     if missing:
#         parts.append(f"missing columns: {missing}")
#     if new:
#         parts.append(f"new columns: {new}")
#     if changed:
#         parts.append(f"type changed: {changed}")
#     message = "; ".join(parts) if parts else "Schema matches expected/baseline"

#     return _result(
#         table_name, check_name, status,
#         failed_rows=len(missing) + len(new) + len(changed),
#         message=message,
#     )

"""
Generic Data Quality Checks
───────────────────────────
Unlike the original standalone version (which hardcoded Postgres + Snowflake
credentials and a fixed 4-table list), these checks run against ANY
connection already saved in `saved_connections`, using the project's
existing `sql_executors` abstraction (sql_executors.get_executor).

Every check function takes a live BaseSqlExecutor instance and returns a
plain dict matching the `quality_results` table columns, so the router can
insert results directly without any extra mapping.
"""

import re
from typing import Any, Dict, List, Optional

from sql_executors.base import BaseSqlExecutor

# Only allow simple identifiers (letters, numbers, underscore, dot for
# schema.table). Table/column names always come from the platform's own
# schema-introspection endpoints or from values the user typed into a
# "table name" field — never from raw free-text — but we validate anyway
# since these values get interpolated into SQL text.
_IDENTIFIER_RE = re.compile(r"^[A-Za-z0-9_.]+$")


def _safe_identifier(name: str) -> str:
    if not _IDENTIFIER_RE.match(name):
        raise ValueError(f"Unsafe identifier rejected: {name!r}")
    return name


def _split_schema_table(table_name: str) -> tuple:
    """'public.customers' -> ('public', 'customers'); 'customers' -> (None, 'customers')."""
    table = _safe_identifier(table_name)
    if "." in table:
        schema, _, bare = table.rpartition(".")
        return schema, bare
    return None, table


def _sql_literal(value: str) -> str:
    """Escape a plain string for use as a SQL string literal (single-quote doubling)."""
    return str(value).replace("'", "''")


async def _scalar(executor: BaseSqlExecutor, query: str) -> Any:
    result = await executor.execute(query, limit=1, timeout_seconds=30)
    if not result.rows:
        return None
    return result.rows[0][0]


def _result(table_name, check_name, status, failed_rows=0,
            source_value=None, target_value=None, message=""):
    return {
        "table_name": table_name,
        "check_name": check_name,
        "status": status,
        "failed_rows": failed_rows,
        "source_value": source_value,
        "target_value": target_value,
        "message": message,
    }


# ─────────────────────────────────────────────────────────────────────────
# Row count
# ─────────────────────────────────────────────────────────────────────────
async def run_row_count_check(
    executor: BaseSqlExecutor,
    table_name: str,
    expected_min_rows: Optional[int] = None,
) -> Dict[str, Any]:
    table = _safe_identifier(table_name)
    count = await _scalar(executor, f"SELECT COUNT(*) FROM {table}")

    if expected_min_rows is None:
        # Informational only — no threshold given, so we can't fail it.
        return _result(table_name, "ROW_COUNT", "PASS",
                        source_value=count,
                        message=f"{table_name} has {count} rows")

    status = "PASS" if count >= expected_min_rows else "FAIL"
    return _result(
        table_name, "ROW_COUNT", status,
        failed_rows=0 if status == "PASS" else expected_min_rows - count,
        source_value=count, target_value=expected_min_rows,
        message=f"{table_name}: {count} rows (expected >= {expected_min_rows})",
    )


# ─────────────────────────────────────────────────────────────────────────
# Null check
# ─────────────────────────────────────────────────────────────────────────
async def run_null_check(
    executor: BaseSqlExecutor,
    table_name: str,
    columns: List[str],
) -> List[Dict[str, Any]]:
    table = _safe_identifier(table_name)
    results = []
    for col in columns:
        column = _safe_identifier(col)
        null_count = await _scalar(
            executor, f"SELECT COUNT(*) FROM {table} WHERE {column} IS NULL"
        )
        status = "PASS" if null_count == 0 else "FAIL"
        results.append(_result(
            table_name, f"NULL_CHECK[{col}]", status,
            failed_rows=null_count,
            message=f"{col}: {null_count} NULL value(s)",
        ))
    return results


# ─────────────────────────────────────────────────────────────────────────
# Duplicate check (based on primary key columns)
# ─────────────────────────────────────────────────────────────────────────
async def run_duplicate_check(
    executor: BaseSqlExecutor,
    table_name: str,
    key_columns_list: List[str],
    check_label: str = "DUPLICATE_CHECK",
) -> Dict[str, Any]:
    """Generic duplicate-group check. Used both for primary-key uniqueness
    (Uniqueness) and for arbitrary business-key duplicate detection
    (Duplicate Detection), which are conceptually different even though the
    SQL is the same — the check_label distinguishes them in results."""
    table = _safe_identifier(table_name)
    key_columns = ", ".join(_safe_identifier(c) for c in key_columns_list)

    dup_count = await _scalar(executor, f"""
        SELECT COUNT(*) FROM (
            SELECT {key_columns} FROM {table}
            GROUP BY {key_columns}
            HAVING COUNT(*) > 1
        ) dup
    """)
    status = "PASS" if dup_count == 0 else "FAIL"
    return _result(
        table_name, check_label, status,
        failed_rows=dup_count,
        message=f"{dup_count} duplicate group(s) on ({key_columns})",
    )


# ─────────────────────────────────────────────────────────────────────────
# Business rule check — a boolean SQL condition that SHOULD MATCH ZERO rows
# e.g. condition="price <= 0"  → any row matching this is a violation
# ─────────────────────────────────────────────────────────────────────────
async def run_business_rule_check(
    executor: BaseSqlExecutor,
    table_name: str,
    column: str,
    condition: str,
) -> Dict[str, Any]:
    table = _safe_identifier(table_name)
    # `condition` is a boolean SQL expression (e.g. "price <= 0"), not a bare
    # identifier, so we don't run it through _safe_identifier. It must come
    # from a trusted, admin-defined rule set (see router.py), never from
    # free-text user input, since it is interpolated directly into SQL.
    violations = await _scalar(
        executor, f"SELECT COUNT(*) FROM {table} WHERE {condition}"
    )
    status = "PASS" if violations == 0 else "FAIL"
    return _result(
        table_name, f"BUSINESS_RULE[{column}]", status,
        failed_rows=violations,
        message=f"Rule '{condition}': {violations} violation(s)",
    )


# ─────────────────────────────────────────────────────────────────────────
# Freshness check
# ─────────────────────────────────────────────────────────────────────────
async def run_freshness_check(
    executor: BaseSqlExecutor,
    table_name: str,
    timestamp_column: str,
    threshold_hours: float,
) -> Dict[str, Any]:
    table = _safe_identifier(table_name)
    column = _safe_identifier(timestamp_column)

    age_hours = await _scalar(executor, f"""
        SELECT EXTRACT(EPOCH FROM (now() - MAX({column}))) / 3600.0
        FROM {table}
    """)

    if age_hours is None:
        return _result(table_name, "FRESHNESS_CHECK", "FAIL",
                        message=f"No rows found in {table_name}")

    status = "PASS" if age_hours <= threshold_hours else "FAIL"
    return _result(
        table_name, "FRESHNESS_CHECK", status,
        source_value=round(float(age_hours), 2), target_value=threshold_hours,
        message=f"Last update {round(float(age_hours), 1)}h ago (threshold {threshold_hours}h)",
    )


# ─────────────────────────────────────────────────────────────────────────
# Referential integrity — child rows whose FK value has no matching parent
# ─────────────────────────────────────────────────────────────────────────
async def run_referential_integrity_check(
    executor: BaseSqlExecutor,
    child_table: str,
    child_column: str,
    parent_table: str,
    parent_column: str,
) -> Dict[str, Any]:
    child = _safe_identifier(child_table)
    child_col = _safe_identifier(child_column)
    parent = _safe_identifier(parent_table)
    parent_col = _safe_identifier(parent_column)

    orphans = await _scalar(executor, f"""
        SELECT COUNT(*) FROM {child} c
        WHERE c.{child_col} IS NOT NULL
          AND NOT EXISTS (
              SELECT 1 FROM {parent} p WHERE p.{parent_col} = c.{child_col}
          )
    """)
    status = "PASS" if orphans == 0 else "FAIL"
    return _result(
        child_table, f"REFERENTIAL_INTEGRITY[{child_column}->{parent_table}.{parent_column}]",
        status, failed_rows=orphans,
        message=f"{orphans} orphan row(s) in {child_table}.{child_column}",
    )


# ─────────────────────────────────────────────────────────────────────────
# Data Type Validation — actual column type (information_schema) vs expected
# e.g. expected_types = {"customer_id": "integer", "email": "varchar"}
# Matching is a case-insensitive substring match so "int" matches "integer"/
# "bigint" and "varchar" matches "character varying", across Postgres and
# Snowflake's differing type-name spellings.
# ─────────────────────────────────────────────────────────────────────────
async def run_data_type_check(
    executor: BaseSqlExecutor,
    table_name: str,
    expected_types: Dict[str, str],
) -> List[Dict[str, Any]]:
    schema, bare_table = _split_schema_table(table_name)
    where_schema = f"AND table_schema = '{_sql_literal(schema)}'" if schema else ""
    rows_result = await executor.execute(f"""
        SELECT column_name, data_type
        FROM information_schema.columns
        WHERE table_name = '{_sql_literal(bare_table)}' {where_schema}
    """, limit=500, timeout_seconds=30)

    actual_types = {r[0].lower(): str(r[1]).lower() for r in rows_result.rows}

    results = []
    for column, expected_type in expected_types.items():
        actual = actual_types.get(column.lower())
        if actual is None:
            results.append(_result(
                table_name, f"DATA_TYPE[{column}]", "FAIL",
                message=f"Column '{column}' not found in {table_name}",
            ))
            continue
        match = expected_type.lower() in actual or actual in expected_type.lower()
        status = "PASS" if match else "FAIL"
        results.append(_result(
            table_name, f"DATA_TYPE[{column}]", status,
            source_value=actual, target_value=expected_type.lower(),
            message=f"{column}: actual '{actual}' vs expected '{expected_type}'",
        ))
    return results


# ─────────────────────────────────────────────────────────────────────────
# Range Checks — values outside [min, max] for a numeric/date column
# e.g. ranges = {"age": {"min": 0, "max": 120}, "discount_pct": {"max": 100}}
# ─────────────────────────────────────────────────────────────────────────
async def run_range_check(
    executor: BaseSqlExecutor,
    table_name: str,
    ranges: Dict[str, Dict[str, float]],
) -> List[Dict[str, Any]]:
    table = _safe_identifier(table_name)
    results = []
    for col, bounds in ranges.items():
        column = _safe_identifier(col)
        numeric_col = f"CAST({column} AS NUMERIC)"
        conditions = []
        if bounds.get("min") is not None:
            conditions.append(f"{numeric_col} < {bounds['min']}")
        if bounds.get("max") is not None:
            conditions.append(f"{numeric_col} > {bounds['max']}")
        if not conditions:
            continue
        where_clause = " OR ".join(conditions)
        violations = await _scalar(
            executor, f"SELECT COUNT(*) FROM {table} WHERE {where_clause}"
        )
        status = "PASS" if violations == 0 else "FAIL"
        bounds_desc = f"[{bounds.get('min', '-inf')}, {bounds.get('max', '+inf')}]"
        results.append(_result(
            table_name, f"RANGE_CHECK[{col}]", status,
            failed_rows=violations,
            message=f"{col}: {violations} row(s) outside {bounds_desc}",
        ))
    return results


# ─────────────────────────────────────────────────────────────────────────
# Outlier Detection — IQR (Tukey's fences) method, works on Postgres and
# Snowflake since both support PERCENTILE_CONT ... WITHIN GROUP.
# ─────────────────────────────────────────────────────────────────────────
async def run_outlier_check(
    executor: BaseSqlExecutor,
    table_name: str,
    column: str,
    iqr_multiplier: float = 1.5,
) -> Dict[str, Any]:
    table = _safe_identifier(table_name)
    col = _safe_identifier(column)
    # Explicit CAST(... AS NUMERIC): PERCENTILE_CONT requires a numeric-family
    # input, but numeric-looking data is very often stored as TEXT/VARCHAR
    # (e.g. straight after CSV ingestion) — without this cast Postgres raises
    # "function percentile_cont(numeric, text) does not exist" instead of
    # actually running the check. If the column truly isn't numeric, the
    # CAST itself now fails with a much clearer "invalid input syntax for
    # type numeric" error instead of that confusing function-not-found one.
    numeric_col = f"CAST({col} AS NUMERIC)"

    row = await executor.execute(f"""
        WITH stats AS (
            SELECT
                percentile_cont(0.25) WITHIN GROUP (ORDER BY {numeric_col}) AS q1,
                percentile_cont(0.75) WITHIN GROUP (ORDER BY {numeric_col}) AS q3
            FROM {table}
            WHERE {col} IS NOT NULL
        )
        SELECT
            (SELECT COUNT(*) FROM {table}, stats
             WHERE {numeric_col} < stats.q1 - {iqr_multiplier} * (stats.q3 - stats.q1)
                OR {numeric_col} > stats.q3 + {iqr_multiplier} * (stats.q3 - stats.q1)) AS outliers,
            stats.q1, stats.q3
        FROM stats
    """, limit=1, timeout_seconds=30)

    if not row.rows:
        return _result(table_name, f"OUTLIER_CHECK[{column}]", "PASS",
                        message=f"No data to evaluate in {table_name}.{column}")

    outliers, q1, q3 = row.rows[0][0], row.rows[0][1], row.rows[0][2]
    status = "PASS" if outliers == 0 else "FAIL"
    return _result(
        table_name, f"OUTLIER_CHECK[{column}]", status,
        failed_rows=outliers,
        source_value=f"Q1={q1}, Q3={q3}",
        message=f"{column}: {outliers} outlier(s) beyond {iqr_multiplier}×IQR of [{q1}, {q3}]",
    )


# ─────────────────────────────────────────────────────────────────────────
# Consistency — compare an aggregate expression between two tables in the
# SAME connection (e.g. SUM(amount) in `orders` vs SUM(amount) in
# `order_summary`). Cross-connection consistency is intentionally out of
# scope for now (see Accuracy / Record-Count source-vs-target, deferred).
# ─────────────────────────────────────────────────────────────────────────
async def run_consistency_check(
    executor: BaseSqlExecutor,
    table_a: str,
    expr_a: str,
    table_b: str,
    expr_b: str,
    tolerance: float = 0,
) -> Dict[str, Any]:
    tbl_a = _safe_identifier(table_a)
    tbl_b = _safe_identifier(table_b)
    # expr_a / expr_b are trusted aggregate expressions (e.g. "SUM(amount)"),
    # analogous to business_rules.condition — never free-text user input.
    value_a = await _scalar(executor, f"SELECT {expr_a} FROM {tbl_a}")
    value_b = await _scalar(executor, f"SELECT {expr_b} FROM {tbl_b}")

    try:
        diff = abs(float(value_a) - float(value_b))
        status = "PASS" if diff <= tolerance else "FAIL"
    except (TypeError, ValueError):
        diff = None
        status = "PASS" if value_a == value_b else "FAIL"

    return _result(
        f"{table_a} vs {table_b}", "CONSISTENCY_CHECK", status,
        source_value=value_a, target_value=value_b,
        message=(
            f"{table_a}.[{expr_a}]={value_a} vs {table_b}.[{expr_b}]={value_b}"
            + (f" (diff={diff}, tolerance={tolerance})" if diff is not None else "")
        ),
    )


# ─────────────────────────────────────────────────────────────────────────
# Schema Validation
#   1) Manual mode: compare actual columns/types against a user-supplied
#      expected schema.
#   2) Baseline mode: compare actual columns/types against a stored
#      snapshot (see quality/router.py for snapshot persistence); the
#      caller passes in the previously stored snapshot as `baseline`.
# Both modes share the same diff logic — detect missing, new, and
# type-changed columns.
# ─────────────────────────────────────────────────────────────────────────
async def get_actual_schema(
    executor: BaseSqlExecutor, table_name: str
) -> Dict[str, str]:
    """Returns {column_name: data_type} for the live table."""
    schema, bare_table = _split_schema_table(table_name)
    where_schema = f"AND table_schema = '{_sql_literal(schema)}'" if schema else ""
    result = await executor.execute(f"""
        SELECT column_name, data_type
        FROM information_schema.columns
        WHERE table_name = '{_sql_literal(bare_table)}' {where_schema}
    """, limit=500, timeout_seconds=30)
    return {r[0]: str(r[1]) for r in result.rows}


def diff_schema(
    table_name: str,
    actual: Dict[str, str],
    expected: Dict[str, str],
    check_name: str = "SCHEMA_VALIDATION",
) -> Dict[str, Any]:
    actual_cols = {k.lower(): v.lower() for k, v in actual.items()}
    expected_cols = {k.lower(): v.lower() for k, v in expected.items()}

    missing = sorted(set(expected_cols) - set(actual_cols))   # in expected, gone from actual
    new = sorted(set(actual_cols) - set(expected_cols))       # in actual, not in expected
    changed = sorted(
        col for col in (set(actual_cols) & set(expected_cols))
        if expected_cols[col] not in actual_cols[col] and actual_cols[col] not in expected_cols[col]
    )

    status = "PASS" if not (missing or new or changed) else "FAIL"
    parts = []
    if missing:
        parts.append(f"missing columns: {missing}")
    if new:
        parts.append(f"new columns: {new}")
    if changed:
        parts.append(f"type changed: {changed}")
    message = "; ".join(parts) if parts else "Schema matches expected/baseline"

    return _result(
        table_name, check_name, status,
        failed_rows=len(missing) + len(new) + len(changed),
        message=message,
    )