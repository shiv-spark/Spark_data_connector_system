# """
# Data Quality Router
# ────────────────────
# API surface for the quality layer. Follows the same shape as
# text_sql/router.py and data_generator/router.py:

#   - reads connections from the existing `saved_connections` table
#   - uses sql_executors.get_executor() instead of a hand-rolled connector
#   - stores its own audit trail in Postgres (quality_runs / quality_results —
#     see quality_init.sql), NOT in whichever warehouse is being checked

# Endpoints
# ---------
# GET  /quality/connections                 list connections quality checks can run against
# POST /quality/run                          run a set of checks, store + return results
# GET  /quality/runs                         list past runs (paginated)
# GET  /quality/runs/{run_id}                get one run + its individual check results
# """

# import os
# import json
# import time
# from datetime import datetime
# from typing import Any, Dict, List, Optional

# import psycopg2
# import psycopg2.extras
# from fastapi import APIRouter, HTTPException
# from pydantic import BaseModel

# from sql_executors import get_executor
# from quality import checks

# router = APIRouter(prefix="/quality", tags=["Data Quality"])


# # ── Safe check execution ───────────────────────────────────────────────
# # A single malformed check (e.g. a business-rule condition that isn't
# # valid SQL, a column that doesn't exist, a type mismatch) used to crash
# # the ENTIRE run with a bare 500 and no indication of which check or why.
# # Every check call below is routed through this helper instead: exceptions
# # are caught and turned into a visible ERROR result carrying the real
# # database/validation message, so one bad check never hides the results of
# # every other check in the same run.
# async def _safe_check(awaitable, table_name: str, check_name: str, as_list: bool = False):
#     try:
#         return await awaitable
#     except HTTPException:
#         raise
#     except Exception as e:
#         error_result = {
#             "table_name": table_name,
#             "check_name": check_name,
#             "status": "ERROR",
#             "failed_rows": None,
#             "source_value": None,
#             "target_value": None,
#             "message": f"Check could not run: {e}",
#         }
#         return [error_result] if as_list else error_result


# async def _safe_value(awaitable, table_name: str, check_name: str):
#     """Like _safe_check, but for calls that return a plain value (not a
#     result dict) consumed by a later step — e.g. get_actual_schema() feeds
#     diff_schema(). Returns (value, error_result); exactly one is None."""
#     try:
#         return await awaitable, None
#     except HTTPException:
#         raise
#     except Exception as e:
#         return None, {
#             "table_name": table_name,
#             "check_name": check_name,
#             "status": "ERROR",
#             "failed_rows": None,
#             "source_value": None,
#             "target_value": None,
#             "message": f"Check could not run: {e}",
#         }

# # ── Postgres connection for the quality module's OWN audit tables ─────────
# # Deliberately independent of whichever connection is being *checked* —
# # audit history always lives in this app's Postgres, same as pipeline_runs /
# # pipeline_metrics elsewhere in the project.
# DB_CONFIG = {
#     "host":     os.getenv("DB_HOST", "postgres"),
#     "database": os.getenv("DB_NAME", "airflow"),
#     "user":     os.getenv("DB_USER", "airflow"),
#     "password": os.getenv("DB_PASSWORD", "airflow"),
#     "port":     os.getenv("DB_PORT", "5432"),
# }


# def _get_conn():
#     return psycopg2.connect(**DB_CONFIG)


# def _ensure_tables():
#     """Idempotent — matches the CREATE TABLE IF NOT EXISTS pattern used
#     everywhere else in this project (see main.py ensure_connections_table)."""
#     conn = _get_conn()
#     cur = conn.cursor()
#     cur.execute("""
#         CREATE TABLE IF NOT EXISTS quality_runs (
#             run_id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
#             connection_id    INTEGER NOT NULL REFERENCES saved_connections(id) ON DELETE CASCADE,
#             started_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
#             completed_at     TIMESTAMPTZ,
#             duration_seconds NUMERIC,
#             total_checks     INTEGER NOT NULL DEFAULT 0,
#             passed_checks    INTEGER NOT NULL DEFAULT 0,
#             failed_checks    INTEGER NOT NULL DEFAULT 0,
#             status           VARCHAR(20) NOT NULL DEFAULT 'RUNNING'
#         )
#     """)
#     cur.execute("""
#         CREATE TABLE IF NOT EXISTS quality_results (
#             id            SERIAL PRIMARY KEY,
#             run_id        UUID NOT NULL REFERENCES quality_runs(run_id) ON DELETE CASCADE,
#             table_name    VARCHAR(160) NOT NULL,
#             check_name    VARCHAR(80)  NOT NULL,
#             status        VARCHAR(10)  NOT NULL,
#             failed_rows   INTEGER,
#             source_value  TEXT,
#             target_value  TEXT,
#             message       TEXT,
#             checked_at    TIMESTAMPTZ NOT NULL DEFAULT now()
#         )
#     """)
#     # Baseline snapshot for Schema Validation (drift mode): one row per
#     # column, captured the first time a table's schema check runs with
#     # schema_baseline=true. Left untouched on later runs unless explicitly
#     # reset via POST /quality/schema-baseline/reset, so drift keeps
#     # comparing against the ORIGINAL baseline, not the previous run.
#     cur.execute("""
#         CREATE TABLE IF NOT EXISTS quality_schema_snapshots (
#             connection_id INTEGER NOT NULL REFERENCES saved_connections(id) ON DELETE CASCADE,
#             table_name    VARCHAR(160) NOT NULL,
#             column_name   VARCHAR(160) NOT NULL,
#             data_type     VARCHAR(80)  NOT NULL,
#             captured_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
#             PRIMARY KEY (connection_id, table_name, column_name)
#         )
#     """)
#     conn.commit()
#     cur.close()
#     conn.close()


# # ─────────────────────────────────────────────────────────────────────────
# # Request/response models
# # ─────────────────────────────────────────────────────────────────────────
# class ForeignKeySpec(BaseModel):
#     column: str
#     parent_table: str
#     parent_column: str


# class TableCheckSpec(BaseModel):
#     table_name: str
#     primary_key: Optional[List[str]] = None             # Uniqueness: duplicate check on PK
#     null_columns: Optional[List[str]] = None             # Completeness: null check
#     expected_min_rows: Optional[int] = None              # Record Count: single-table threshold
#     freshness_column: Optional[str] = None
#     freshness_threshold_hours: Optional[float] = None
#     business_rules: Optional[List[Dict[str, str]]] = None   # Validity: [{"column","condition"}]
#     foreign_keys: Optional[List[ForeignKeySpec]] = None      # Referential Integrity
#     business_keys: Optional[List[str]] = None                 # Duplicate Detection (non-PK key set)
#     data_types: Optional[Dict[str, str]] = None                # Data Type Validation: {col: expected_type}
#     range_checks: Optional[Dict[str, Dict[str, float]]] = None # Range Checks: {col: {"min","max"}}
#     outlier_columns: Optional[List[str]] = None                 # Outlier Detection (IQR)
#     expected_columns: Optional[Dict[str, str]] = None            # Schema Validation (manual): {col: type}
#     schema_baseline: bool = False                                  # Schema Validation (baseline/drift mode)


# class ConsistencyCheckSpec(BaseModel):
#     table_a: str
#     expr_a: str  # trusted aggregate expression, e.g. "SUM(amount)"
#     table_b: str
#     expr_b: str
#     tolerance: float = 0


# class SchemaBaselineResetRequest(BaseModel):
#     connection_id: int
#     table_name: str


# class RunQualityRequest(BaseModel):
#     connection_id: int
#     tables: List[TableCheckSpec]
#     consistency_checks: Optional[List[ConsistencyCheckSpec]] = None  # cross-table, same connection


# # ─────────────────────────────────────────────────────────────────────────
# # Helpers
# # ─────────────────────────────────────────────────────────────────────────
# def _load_connection(connection_id: int) -> Dict[str, Any]:
#     conn = _get_conn()
#     cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
#     cur.execute(
#         "SELECT id, name, source_type, config FROM saved_connections WHERE id = %s",
#         (connection_id,),
#     )
#     row = cur.fetchone()
#     cur.close()
#     conn.close()
#     if not row:
#         raise HTTPException(status_code=404, detail="Connection not found")
#     return dict(row)


# def _run_schema_baseline_check(
#     connection_id: int, table_name: str, actual_schema: Dict[str, str]
# ) -> Dict[str, Any]:
#     """Schema Validation (drift mode). First run for a given
#     (connection_id, table_name) captures the baseline and passes
#     informationally; subsequent runs diff against that stored baseline
#     without overwriting it (use /quality/schema-baseline/reset to rebaseline
#     after an intentional schema change)."""
#     conn = _get_conn()
#     cur = conn.cursor()
#     cur.execute(
#         "SELECT column_name, data_type FROM quality_schema_snapshots "
#         "WHERE connection_id = %s AND table_name = %s",
#         (connection_id, table_name),
#     )
#     baseline_rows = cur.fetchall()

#     if not baseline_rows:
#         for column_name, data_type in actual_schema.items():
#             cur.execute("""
#                 INSERT INTO quality_schema_snapshots (connection_id, table_name, column_name, data_type)
#                 VALUES (%s,%s,%s,%s)
#                 ON CONFLICT (connection_id, table_name, column_name) DO NOTHING
#             """, (connection_id, table_name, column_name, data_type))
#         conn.commit()
#         cur.close()
#         conn.close()
#         return {
#             "table_name": table_name,
#             "check_name": "SCHEMA_VALIDATION[BASELINE]",
#             "status": "PASS",
#             "failed_rows": 0,
#             "source_value": None,
#             "target_value": None,
#             "message": f"Baseline captured ({len(actual_schema)} columns). Future runs will diff against this.",
#         }

#     cur.close()
#     conn.close()
#     baseline = {r[0]: r[1] for r in baseline_rows}
#     return checks.diff_schema(
#         table_name, actual_schema, baseline, check_name="SCHEMA_VALIDATION[BASELINE]"
#     )


# # ─────────────────────────────────────────────────────────────────────────
# # Endpoints
# # ─────────────────────────────────────────────────────────────────────────
# @router.get("/connections")
# def list_quality_connections():
#     """Connections that quality checks can be run against — reuses the
#     same saved_connections table the rest of the app already uses."""
#     conn = _get_conn()
#     cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
#     cur.execute("SELECT id, name, source_type FROM saved_connections ORDER BY name")
#     rows = [dict(r) for r in cur.fetchall()]
#     cur.close()
#     conn.close()
#     return {"connections": rows}


# @router.post("/run")
# async def run_quality_checks(request: RunQualityRequest):
#     _ensure_tables()
#     connection = _load_connection(request.connection_id)
#     executor = get_executor(connection["source_type"], connection["config"])

#     started_at = datetime.utcnow()
#     results: List[Dict[str, Any]] = []

#     try:
#         for table_spec in request.tables:
#             table_name = table_spec.table_name

#             if table_spec.expected_min_rows is not None or True:
#                 # row count is always informative even without a threshold
#                 results.append(await _safe_check(
#                     checks.run_row_count_check(executor, table_name, table_spec.expected_min_rows),
#                     table_name, "ROW_COUNT_CHECK",
#                 ))

#             if table_spec.null_columns:
#                 results.extend(await _safe_check(
#                     checks.run_null_check(executor, table_name, table_spec.null_columns),
#                     table_name, "NULL_CHECK", as_list=True,
#                 ))

#             # Uniqueness — duplicate rows on the primary key
#             if table_spec.primary_key:
#                 results.append(await _safe_check(
#                     checks.run_duplicate_check(
#                         executor, table_name, table_spec.primary_key, check_label="DUPLICATE_CHECK"
#                     ),
#                     table_name, "DUPLICATE_CHECK",
#                 ))

#             # Duplicate Detection — duplicate rows on an arbitrary business key
#             # (kept distinct from primary_key: a table can have a clean PK but
#             # still contain duplicate business records, e.g. same email twice)
#             if table_spec.business_keys:
#                 results.append(await _safe_check(
#                     checks.run_duplicate_check(
#                         executor, table_name, table_spec.business_keys,
#                         check_label="DUPLICATE_CHECK[BUSINESS_KEY]",
#                     ),
#                     table_name, "DUPLICATE_CHECK[BUSINESS_KEY]",
#                 ))

#             if table_spec.freshness_column and table_spec.freshness_threshold_hours:
#                 results.append(await _safe_check(
#                     checks.run_freshness_check(
#                         executor, table_name, table_spec.freshness_column,
#                         table_spec.freshness_threshold_hours,
#                     ),
#                     table_name, "FRESHNESS_CHECK",
#                 ))

#             for rule in (table_spec.business_rules or []):
#                 results.append(await _safe_check(
#                     checks.run_business_rule_check(
#                         executor, table_name, rule["column"], rule["condition"]
#                     ),
#                     table_name, f"BUSINESS_RULE[{rule.get('column')}]",
#                 ))

#             # Referential Integrity
#             for fk in (table_spec.foreign_keys or []):
#                 results.append(await _safe_check(
#                     checks.run_referential_integrity_check(
#                         executor, table_name, fk.column, fk.parent_table, fk.parent_column
#                     ),
#                     table_name, f"REFERENTIAL_INTEGRITY[{fk.column}->{fk.parent_table}.{fk.parent_column}]",
#                 ))

#             # Data Type Validation
#             if table_spec.data_types:
#                 results.extend(await _safe_check(
#                     checks.run_data_type_check(executor, table_name, table_spec.data_types),
#                     table_name, "DATA_TYPE", as_list=True,
#                 ))

#             # Range Checks
#             if table_spec.range_checks:
#                 results.extend(await _safe_check(
#                     checks.run_range_check(executor, table_name, table_spec.range_checks),
#                     table_name, "RANGE_CHECK", as_list=True,
#                 ))

#             # Outlier Detection
#             for col in (table_spec.outlier_columns or []):
#                 results.append(await _safe_check(
#                     checks.run_outlier_check(executor, table_name, col),
#                     table_name, f"OUTLIER_CHECK[{col}]",
#                 ))

#             # Schema Validation — manual (expected_columns) and/or baseline (drift)
#             if table_spec.expected_columns or table_spec.schema_baseline:
#                 actual_schema, schema_error = await _safe_value(
#                     checks.get_actual_schema(executor, table_name),
#                     table_name, "SCHEMA_VALIDATION",
#                 )
#                 if schema_error:
#                     results.append(schema_error)
#                 else:
#                     if table_spec.expected_columns:
#                         results.append(checks.diff_schema(
#                             table_name, actual_schema, table_spec.expected_columns,
#                             check_name="SCHEMA_VALIDATION[MANUAL]",
#                         ))

#                     if table_spec.schema_baseline:
#                         results.append(_run_schema_baseline_check(
#                             request.connection_id, table_name, actual_schema
#                         ))

#         # Consistency — cross-table, same connection
#         for c in (request.consistency_checks or []):
#             results.append(await _safe_check(
#                 checks.run_consistency_check(
#                     executor, c.table_a, c.expr_a, c.table_b, c.expr_b, c.tolerance
#                 ),
#                 f"{c.table_a} vs {c.table_b}", "CONSISTENCY_CHECK",
#             ))
#     finally:
#         await executor.close()

#     completed_at = datetime.utcnow()
#     passed = sum(1 for r in results if r["status"] == "PASS")
#     failed = sum(1 for r in results if r["status"] in ("FAIL", "ERROR"))
#     overall_status = "PASS" if failed == 0 else "FAIL"

#     # ── persist run + results ──────────────────────────────────────────
#     conn = _get_conn()
#     cur = conn.cursor()
#     cur.execute("""
#         INSERT INTO quality_runs
#             (connection_id, started_at, completed_at, duration_seconds,
#              total_checks, passed_checks, failed_checks, status)
#         VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
#         RETURNING run_id
#     """, (
#         request.connection_id, started_at, completed_at,
#         (completed_at - started_at).total_seconds(),
#         len(results), passed, failed, overall_status,
#     ))
#     run_id = cur.fetchone()[0]

#     for r in results:
#         cur.execute("""
#             INSERT INTO quality_results
#                 (run_id, table_name, check_name, status, failed_rows,
#                  source_value, target_value, message)
#             VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
#         """, (
#             run_id, r["table_name"], r["check_name"], r["status"],
#             r.get("failed_rows"),
#             str(r["source_value"]) if r.get("source_value") is not None else None,
#             str(r["target_value"]) if r.get("target_value") is not None else None,
#             r.get("message", ""),
#         ))
#     conn.commit()
#     cur.close()
#     conn.close()

#     return {
#         "run_id": str(run_id),
#         "status": overall_status,
#         "total_checks": len(results),
#         "passed": passed,
#         "failed": failed,
#         "results": results,
#     }


# @router.post("/schema-baseline/reset")
# def reset_schema_baseline(request: SchemaBaselineResetRequest):
#     """Delete the stored baseline for a table so the next quality run with
#     schema_baseline=true recaptures it fresh (use after an intentional
#     schema change)."""
#     _ensure_tables()
#     conn = _get_conn()
#     cur = conn.cursor()
#     cur.execute(
#         "DELETE FROM quality_schema_snapshots WHERE connection_id = %s AND table_name = %s",
#         (request.connection_id, request.table_name),
#     )
#     deleted = cur.rowcount
#     conn.commit()
#     cur.close()
#     conn.close()
#     return {"reset": True, "columns_cleared": deleted}


# @router.get("/runs")
# def list_quality_runs(limit: int = 20, connection_id: Optional[int] = None):
#     _ensure_tables()
#     conn = _get_conn()
#     cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
#     if connection_id is not None:
#         cur.execute("""
#             SELECT r.*, c.name AS connection_name
#             FROM quality_runs r JOIN saved_connections c ON c.id = r.connection_id
#             WHERE r.connection_id = %s
#             ORDER BY r.started_at DESC LIMIT %s
#         """, (connection_id, limit))
#     else:
#         cur.execute("""
#             SELECT r.*, c.name AS connection_name
#             FROM quality_runs r JOIN saved_connections c ON c.id = r.connection_id
#             ORDER BY r.started_at DESC LIMIT %s
#         """, (limit,))
#     rows = [dict(r) for r in cur.fetchall()]
#     cur.close()
#     conn.close()
#     return {"runs": rows}


# @router.get("/runs/{run_id}")
# def get_quality_run(run_id: str):
#     _ensure_tables()
#     conn = _get_conn()
#     cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
#     cur.execute("SELECT * FROM quality_runs WHERE run_id = %s", (run_id,))
#     run = cur.fetchone()
#     if not run:
#         cur.close()
#         conn.close()
#         raise HTTPException(status_code=404, detail="Run not found")

#     cur.execute(
#         "SELECT * FROM quality_results WHERE run_id = %s ORDER BY id", (run_id,)
#     )
#     results = [dict(r) for r in cur.fetchall()]
#     cur.close()
#     conn.close()
#     return {"run": dict(run), "results": results}


"""
Data Quality Router
────────────────────
API surface for the quality layer. Follows the same shape as
text_sql/router.py and data_generator/router.py:

  - reads connections from the existing `saved_connections` table
  - uses sql_executors.get_executor() instead of a hand-rolled connector
  - stores its own audit trail in Postgres (quality_runs / quality_results —
    see quality_init.sql), NOT in whichever warehouse is being checked

Endpoints
---------
GET  /quality/connections                 list connections quality checks can run against
POST /quality/run                          run a set of checks, store + return results
GET  /quality/runs                         list past runs (paginated)
GET  /quality/runs/{run_id}                get one run + its individual check results
"""

import os
import json
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

import psycopg2
import psycopg2.extras
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from sql_executors import get_executor
from quality import checks

router = APIRouter(prefix="/quality", tags=["Data Quality"])


# ── Safe check execution ───────────────────────────────────────────────
# A single malformed check (e.g. a business-rule condition that isn't
# valid SQL, a column that doesn't exist, a type mismatch) used to crash
# the ENTIRE run with a bare 500 and no indication of which check or why.
# Every check call below is routed through this helper instead: exceptions
# are caught and turned into a visible ERROR result carrying the real
# database/validation message, so one bad check never hides the results of
# every other check in the same run.
async def _safe_check(awaitable, table_name: str, check_name: str, as_list: bool = False):
    try:
        return await awaitable
    except HTTPException:
        raise
    except Exception as e:
        error_result = {
            "table_name": table_name,
            "check_name": check_name,
            "status": "ERROR",
            "failed_rows": None,
            "source_value": None,
            "target_value": None,
            "message": f"Check could not run: {e}",
        }
        return [error_result] if as_list else error_result


async def _safe_value(awaitable, table_name: str, check_name: str):
    """Like _safe_check, but for calls that return a plain value (not a
    result dict) consumed by a later step — e.g. get_actual_schema() feeds
    diff_schema(). Returns (value, error_result); exactly one is None."""
    try:
        return await awaitable, None
    except HTTPException:
        raise
    except Exception as e:
        return None, {
            "table_name": table_name,
            "check_name": check_name,
            "status": "ERROR",
            "failed_rows": None,
            "source_value": None,
            "target_value": None,
            "message": f"Check could not run: {e}",
        }

# ── Postgres connection for the quality module's OWN audit tables ─────────
# Deliberately independent of whichever connection is being *checked* —
# audit history always lives in this app's Postgres, same as pipeline_runs /
# pipeline_metrics elsewhere in the project.
DB_CONFIG = {
    "host":     os.getenv("DB_HOST", "postgres"),
    "database": os.getenv("DB_NAME", "airflow"),
    "user":     os.getenv("DB_USER", "airflow"),
    "password": os.getenv("DB_PASSWORD", "airflow"),
    "port":     os.getenv("DB_PORT", "5432"),
}


def _get_conn():
    return psycopg2.connect(**DB_CONFIG)


def _ensure_tables():
    """Idempotent — matches the CREATE TABLE IF NOT EXISTS pattern used
    everywhere else in this project (see main.py ensure_connections_table)."""
    conn = _get_conn()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS quality_runs (
            run_id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            connection_id    INTEGER NOT NULL REFERENCES saved_connections(id) ON DELETE CASCADE,
            started_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
            completed_at     TIMESTAMPTZ,
            duration_seconds NUMERIC,
            total_checks     INTEGER NOT NULL DEFAULT 0,
            passed_checks    INTEGER NOT NULL DEFAULT 0,
            failed_checks    INTEGER NOT NULL DEFAULT 0,
            status           VARCHAR(20) NOT NULL DEFAULT 'RUNNING'
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS quality_results (
            id            SERIAL PRIMARY KEY,
            run_id        UUID NOT NULL REFERENCES quality_runs(run_id) ON DELETE CASCADE,
            table_name    VARCHAR(160) NOT NULL,
            check_name    VARCHAR(80)  NOT NULL,
            status        VARCHAR(10)  NOT NULL,
            failed_rows   INTEGER,
            source_value  TEXT,
            target_value  TEXT,
            message       TEXT,
            checked_at    TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    # Baseline snapshot for Schema Validation (drift mode): one row per
    # column, captured the first time a table's schema check runs with
    # schema_baseline=true. Left untouched on later runs unless explicitly
    # reset via POST /quality/schema-baseline/reset, so drift keeps
    # comparing against the ORIGINAL baseline, not the previous run.
    cur.execute("""
        CREATE TABLE IF NOT EXISTS quality_schema_snapshots (
            connection_id INTEGER NOT NULL REFERENCES saved_connections(id) ON DELETE CASCADE,
            table_name    VARCHAR(160) NOT NULL,
            column_name   VARCHAR(160) NOT NULL,
            data_type     VARCHAR(80)  NOT NULL,
            captured_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
            PRIMARY KEY (connection_id, table_name, column_name)
        )
    """)
    conn.commit()
    cur.close()
    conn.close()


# ─────────────────────────────────────────────────────────────────────────
# Request/response models
# ─────────────────────────────────────────────────────────────────────────
class ForeignKeySpec(BaseModel):
    column: str
    parent_table: str
    parent_column: str


class TableCheckSpec(BaseModel):
    table_name: str
    primary_key: Optional[List[str]] = None             # Uniqueness: duplicate check on PK
    null_columns: Optional[List[str]] = None             # Completeness: null check
    expected_min_rows: Optional[int] = None              # Record Count: single-table threshold
    freshness_column: Optional[str] = None
    freshness_threshold_hours: Optional[float] = None
    business_rules: Optional[List[Dict[str, str]]] = None   # Validity: [{"column","condition"}]
    foreign_keys: Optional[List[ForeignKeySpec]] = None      # Referential Integrity
    business_keys: Optional[List[str]] = None                 # Duplicate Detection (non-PK key set)
    data_types: Optional[Dict[str, str]] = None                # Data Type Validation: {col: expected_type}
    range_checks: Optional[Dict[str, Dict[str, float]]] = None # Range Checks: {col: {"min","max"}}
    outlier_columns: Optional[List[str]] = None                 # Outlier Detection (IQR)
    expected_columns: Optional[Dict[str, str]] = None            # Schema Validation (manual): {col: type}
    schema_baseline: bool = False                                  # Schema Validation (baseline/drift mode)


class ConsistencyCheckSpec(BaseModel):
    table_a: str
    expr_a: str  # trusted aggregate expression, e.g. "SUM(amount)"
    table_b: str
    expr_b: str
    tolerance: float = 0


class SchemaBaselineResetRequest(BaseModel):
    connection_id: int
    table_name: str


class RunQualityRequest(BaseModel):
    connection_id: int
    tables: List[TableCheckSpec]
    consistency_checks: Optional[List[ConsistencyCheckSpec]] = None  # cross-table, same connection


# ─────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────
def _load_connection(connection_id: int) -> Dict[str, Any]:
    conn = _get_conn()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute(
        "SELECT id, name, source_type, config FROM saved_connections WHERE id = %s",
        (connection_id,),
    )
    row = cur.fetchone()
    cur.close()
    conn.close()
    if not row:
        raise HTTPException(status_code=404, detail="Connection not found")
    return dict(row)


def _run_schema_baseline_check(
    connection_id: int, table_name: str, actual_schema: Dict[str, str]
) -> Dict[str, Any]:
    """Schema Validation (drift mode). First run for a given
    (connection_id, table_name) captures the baseline and passes
    informationally; subsequent runs diff against that stored baseline
    without overwriting it (use /quality/schema-baseline/reset to rebaseline
    after an intentional schema change)."""
    conn = _get_conn()
    cur = conn.cursor()
    cur.execute(
        "SELECT column_name, data_type FROM quality_schema_snapshots "
        "WHERE connection_id = %s AND table_name = %s",
        (connection_id, table_name),
    )
    baseline_rows = cur.fetchall()

    if not baseline_rows:
        for column_name, data_type in actual_schema.items():
            cur.execute("""
                INSERT INTO quality_schema_snapshots (connection_id, table_name, column_name, data_type)
                VALUES (%s,%s,%s,%s)
                ON CONFLICT (connection_id, table_name, column_name) DO NOTHING
            """, (connection_id, table_name, column_name, data_type))
        conn.commit()
        cur.close()
        conn.close()
        return {
            "table_name": table_name,
            "check_name": "SCHEMA_VALIDATION[BASELINE]",
            "status": "PASS",
            "failed_rows": 0,
            "source_value": None,
            "target_value": None,
            "message": f"Baseline captured ({len(actual_schema)} columns). Future runs will diff against this.",
        }

    cur.close()
    conn.close()
    baseline = {r[0]: r[1] for r in baseline_rows}
    return checks.diff_schema(
        table_name, actual_schema, baseline, check_name="SCHEMA_VALIDATION[BASELINE]"
    )


# ─────────────────────────────────────────────────────────────────────────
# Endpoints
# ─────────────────────────────────────────────────────────────────────────
@router.get("/connections")
def list_quality_connections():
    """Connections that quality checks can be run against — reuses the
    same saved_connections table the rest of the app already uses."""
    conn = _get_conn()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT id, name, source_type FROM saved_connections ORDER BY name")
    rows = [dict(r) for r in cur.fetchall()]
    cur.close()
    conn.close()
    return {"connections": rows}


@router.get("/tables")
async def list_quality_tables(connection_id: int):
    """List every table a saved connection can see, so the frontend can
    offer a table dropdown instead of asking the user to type/remember a
    table name. Works for any dialect with an information_schema (Postgres,
    Snowflake — the two dialects quality checks support)."""
    connection = _load_connection(connection_id)
    executor = get_executor(connection["source_type"], connection["config"])
    try:
        result = await executor.execute("""
            SELECT table_name FROM information_schema.tables
            WHERE table_schema NOT IN ('pg_catalog', 'information_schema')
            ORDER BY table_name
        """, limit=2000, timeout_seconds=30)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Couldn't list tables: {e}")
    return {"tables": [r[0] for r in result.rows]}


@router.get("/table-columns")
async def list_quality_table_columns(connection_id: int, table_name: str):
    """List a table's columns (name + type), so every column-picking field
    in the quality-check builder can be a dropdown fed by the live schema
    instead of a free-text box the user has to fill in from memory."""
    connection = _load_connection(connection_id)
    executor = get_executor(connection["source_type"], connection["config"])
    try:
        schema = await checks.get_actual_schema(executor, table_name)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Couldn't read columns for '{table_name}': {e}")
    if not schema:
        raise HTTPException(status_code=404, detail=f"Table '{table_name}' not found or has no columns.")
    return {"columns": [{"name": name, "type": dtype} for name, dtype in schema.items()]}


@router.post("/run")
async def run_quality_checks(request: RunQualityRequest):
    _ensure_tables()
    connection = _load_connection(request.connection_id)
    executor = get_executor(connection["source_type"], connection["config"])

    started_at = datetime.utcnow()
    results: List[Dict[str, Any]] = []

    try:
        for table_spec in request.tables:
            table_name = table_spec.table_name

            if table_spec.expected_min_rows is not None or True:
                # row count is always informative even without a threshold
                results.append(await _safe_check(
                    checks.run_row_count_check(executor, table_name, table_spec.expected_min_rows),
                    table_name, "ROW_COUNT_CHECK",
                ))

            if table_spec.null_columns:
                results.extend(await _safe_check(
                    checks.run_null_check(executor, table_name, table_spec.null_columns),
                    table_name, "NULL_CHECK", as_list=True,
                ))

            # Uniqueness — duplicate rows on the primary key
            if table_spec.primary_key:
                results.append(await _safe_check(
                    checks.run_duplicate_check(
                        executor, table_name, table_spec.primary_key, check_label="DUPLICATE_CHECK"
                    ),
                    table_name, "DUPLICATE_CHECK",
                ))

            # Duplicate Detection — duplicate rows on an arbitrary business key
            # (kept distinct from primary_key: a table can have a clean PK but
            # still contain duplicate business records, e.g. same email twice)
            if table_spec.business_keys:
                results.append(await _safe_check(
                    checks.run_duplicate_check(
                        executor, table_name, table_spec.business_keys,
                        check_label="DUPLICATE_CHECK[BUSINESS_KEY]",
                    ),
                    table_name, "DUPLICATE_CHECK[BUSINESS_KEY]",
                ))

            if table_spec.freshness_column and table_spec.freshness_threshold_hours:
                results.append(await _safe_check(
                    checks.run_freshness_check(
                        executor, table_name, table_spec.freshness_column,
                        table_spec.freshness_threshold_hours,
                    ),
                    table_name, "FRESHNESS_CHECK",
                ))

            for rule in (table_spec.business_rules or []):
                results.append(await _safe_check(
                    checks.run_business_rule_check(
                        executor, table_name, rule["column"], rule["condition"]
                    ),
                    table_name, f"BUSINESS_RULE[{rule.get('column')}]",
                ))

            # Referential Integrity
            for fk in (table_spec.foreign_keys or []):
                results.append(await _safe_check(
                    checks.run_referential_integrity_check(
                        executor, table_name, fk.column, fk.parent_table, fk.parent_column
                    ),
                    table_name, f"REFERENTIAL_INTEGRITY[{fk.column}->{fk.parent_table}.{fk.parent_column}]",
                ))

            # Data Type Validation
            if table_spec.data_types:
                results.extend(await _safe_check(
                    checks.run_data_type_check(executor, table_name, table_spec.data_types),
                    table_name, "DATA_TYPE", as_list=True,
                ))

            # Range Checks
            if table_spec.range_checks:
                results.extend(await _safe_check(
                    checks.run_range_check(executor, table_name, table_spec.range_checks),
                    table_name, "RANGE_CHECK", as_list=True,
                ))

            # Outlier Detection
            for col in (table_spec.outlier_columns or []):
                results.append(await _safe_check(
                    checks.run_outlier_check(executor, table_name, col),
                    table_name, f"OUTLIER_CHECK[{col}]",
                ))

            # Schema Validation — manual (expected_columns) and/or baseline (drift)
            if table_spec.expected_columns or table_spec.schema_baseline:
                actual_schema, schema_error = await _safe_value(
                    checks.get_actual_schema(executor, table_name),
                    table_name, "SCHEMA_VALIDATION",
                )
                if schema_error:
                    results.append(schema_error)
                else:
                    if table_spec.expected_columns:
                        results.append(checks.diff_schema(
                            table_name, actual_schema, table_spec.expected_columns,
                            check_name="SCHEMA_VALIDATION[MANUAL]",
                        ))

                    if table_spec.schema_baseline:
                        results.append(_run_schema_baseline_check(
                            request.connection_id, table_name, actual_schema
                        ))

        # Consistency — cross-table, same connection
        for c in (request.consistency_checks or []):
            results.append(await _safe_check(
                checks.run_consistency_check(
                    executor, c.table_a, c.expr_a, c.table_b, c.expr_b, c.tolerance
                ),
                f"{c.table_a} vs {c.table_b}", "CONSISTENCY_CHECK",
            ))
    finally:
        await executor.close()

    completed_at = datetime.utcnow()
    passed = sum(1 for r in results if r["status"] == "PASS")
    failed = sum(1 for r in results if r["status"] in ("FAIL", "ERROR"))
    overall_status = "PASS" if failed == 0 else "FAIL"

    # ── persist run + results ──────────────────────────────────────────
    conn = _get_conn()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO quality_runs
            (connection_id, started_at, completed_at, duration_seconds,
             total_checks, passed_checks, failed_checks, status)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
        RETURNING run_id
    """, (
        request.connection_id, started_at, completed_at,
        (completed_at - started_at).total_seconds(),
        len(results), passed, failed, overall_status,
    ))
    run_id = cur.fetchone()[0]

    for r in results:
        cur.execute("""
            INSERT INTO quality_results
                (run_id, table_name, check_name, status, failed_rows,
                 source_value, target_value, message)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
        """, (
            run_id, r["table_name"], r["check_name"], r["status"],
            r.get("failed_rows"),
            str(r["source_value"]) if r.get("source_value") is not None else None,
            str(r["target_value"]) if r.get("target_value") is not None else None,
            r.get("message", ""),
        ))
    conn.commit()
    cur.close()
    conn.close()

    return {
        "run_id": str(run_id),
        "status": overall_status,
        "total_checks": len(results),
        "passed": passed,
        "failed": failed,
        "results": results,
    }


@router.post("/schema-baseline/reset")
def reset_schema_baseline(request: SchemaBaselineResetRequest):
    """Delete the stored baseline for a table so the next quality run with
    schema_baseline=true recaptures it fresh (use after an intentional
    schema change)."""
    _ensure_tables()
    conn = _get_conn()
    cur = conn.cursor()
    cur.execute(
        "DELETE FROM quality_schema_snapshots WHERE connection_id = %s AND table_name = %s",
        (request.connection_id, request.table_name),
    )
    deleted = cur.rowcount
    conn.commit()
    cur.close()
    conn.close()
    return {"reset": True, "columns_cleared": deleted}


@router.get("/runs")
def list_quality_runs(limit: int = 20, connection_id: Optional[int] = None):
    _ensure_tables()
    conn = _get_conn()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    if connection_id is not None:
        cur.execute("""
            SELECT r.*, c.name AS connection_name
            FROM quality_runs r JOIN saved_connections c ON c.id = r.connection_id
            WHERE r.connection_id = %s
            ORDER BY r.started_at DESC LIMIT %s
        """, (connection_id, limit))
    else:
        cur.execute("""
            SELECT r.*, c.name AS connection_name
            FROM quality_runs r JOIN saved_connections c ON c.id = r.connection_id
            ORDER BY r.started_at DESC LIMIT %s
        """, (limit,))
    rows = [dict(r) for r in cur.fetchall()]
    cur.close()
    conn.close()
    return {"runs": rows}


@router.get("/runs/{run_id}")
def get_quality_run(run_id: str):
    _ensure_tables()
    conn = _get_conn()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT * FROM quality_runs WHERE run_id = %s", (run_id,))
    run = cur.fetchone()
    if not run:
        cur.close()
        conn.close()
        raise HTTPException(status_code=404, detail="Run not found")

    cur.execute(
        "SELECT * FROM quality_results WHERE run_id = %s ORDER BY id", (run_id,)
    )
    results = [dict(r) for r in cur.fetchall()]
    cur.close()
    conn.close()
    return {"run": dict(run), "results": results}