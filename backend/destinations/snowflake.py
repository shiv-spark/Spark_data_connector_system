"""
Snowflake destination adapter — same adapter interface as destinations/postgres.py.

Requires `snowflake-connector-python`. Config keys match testers/snowflake.py
and reverse_etl/writers/snowflake_writer.py exactly: account, user,
password, warehouse, database, schema (default "PUBLIC"), role (optional).

Notes:
- Identifiers are used UNQUOTED, so Snowflake folds them to UPPERCASE —
  same convention as the Oracle adapter and reverse_etl's snowflake_writer.
- `json` canonical type is stored as VARCHAR (a JSON string), not VARIANT.
  True VARIANT columns need `PARSE_JSON(%s)` on every insert rather than a
  plain bind parameter, which would make the batched INSERT statement
  column-type-dependent; VARCHAR keeps the insert path identical to every
  other column and the value is still valid, parseable JSON.
- `alter_existing_columns_to_custom_schema` uses `ALTER COLUMN ... SET
  DATA TYPE`, which Snowflake only allows between compatible types
  (e.g. NUMBER -> FLOAT, VARCHAR widening) — best-effort like the
  MySQL/Oracle adapters, skips with a warning on incompatible changes.
"""

import datetime as _dt
import re

try:
    import snowflake.connector

    SNOWFLAKE_AVAILABLE = True
except ImportError:
    SNOWFLAKE_AVAILABLE = False

from destinations.common import get_schema, sanitize_value

MAX_IDENTIFIER_LEN = 255
_IDENT_RE = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")

CANONICAL_TO_NATIVE = {
    "integer":   "NUMBER",
    "float":     "FLOAT",
    "boolean":   "BOOLEAN",
    "date":      "DATE",
    "timestamp": "TIMESTAMP_NTZ",
    "text":      "VARCHAR",
    "json":      "VARCHAR",
}


def _native_schema(custom_schema):
    if not custom_schema:
        return {}
    return {col: CANONICAL_TO_NATIVE.get(t, "VARCHAR") for col, t in custom_schema.items()}


def validate_identifier(table_name: str):
    if not table_name or not _IDENT_RE.match(table_name):
        raise ValueError(
            f"Invalid table_name '{table_name}' — only letters, numbers, and underscores are allowed"
        )
    if len(table_name) > MAX_IDENTIFIER_LEN:
        raise ValueError(f"table_name cannot be longer than {MAX_IDENTIFIER_LEN} characters")


def _require_snowflake():
    if not SNOWFLAKE_AVAILABLE:
        raise ImportError("Snowflake destination requires snowflake-connector-python.")


def connect(config: dict):
    _require_snowflake()
    conn_params = {
        "account": config.get("account"),
        "user": config.get("user"),
        "password": config.get("password"),
        "warehouse": config.get("warehouse"),
        "database": config.get("database"),
        "schema": config.get("schema", "PUBLIC"),
    }
    if config.get("role"):
        conn_params["role"] = config["role"]
    conn = snowflake.connector.connect(**conn_params)
    conn.autocommit(False)
    return conn


def close(conn):
    try:
        conn.close()
    except Exception:
        pass


def dtype_to_native(dtype: str) -> str:
    dtype = dtype.lower()
    if "int" in dtype:
        return "NUMBER"
    elif "float" in dtype or "double" in dtype:
        return "FLOAT"
    elif "bool" in dtype:
        return "BOOLEAN"
    elif "datetime" in dtype or "timestamp" in dtype:
        return "TIMESTAMP_NTZ"
    elif "date" in dtype:
        return "DATE"
    else:
        return "VARCHAR"


def table_exists(conn, table_name: str) -> bool:
    cur = conn.cursor()
    cur.execute(
        "SELECT COUNT(*) FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_NAME = %s",
        (table_name.upper(),),
    )
    return cur.fetchone()[0] > 0


def check_schema_mismatch(conn, df, table_name: str) -> dict:
    cur = conn.cursor()
    cur.execute(
        "SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = %s",
        (table_name.upper(),),
    )
    existing_cols = {row[0].lower() for row in cur.fetchall()}
    incoming_cols = set(df.columns)

    missing_in_file = existing_cols - incoming_cols
    extra_in_file = incoming_cols - existing_cols
    matched = existing_cols & incoming_cols
    match_pct = round(len(matched) / len(existing_cols) * 100, 2) if existing_cols else 100.0

    return {
        "matched": sorted(matched),
        "missing_in_file": sorted(missing_in_file),
        "extra_in_file": sorted(extra_in_file),
        "match_pct": match_pct,
    }


def create_table(conn, df, table_name: str, custom_schema=None):
    schema = get_schema(df)
    native = _native_schema(custom_schema)
    cur = conn.cursor()

    col_defs = []
    for col, dtype in schema.items():
        sql_type = native.get(col) or dtype_to_native(dtype)
        col_defs.append(f'"{col.upper()}" {sql_type}')

    cur.execute(f'CREATE TABLE IF NOT EXISTS "{table_name.upper()}" ({", ".join(col_defs)})')
    print(f"[snowflake] Table '{table_name}' created successfully")


def evolve_schema(conn, df, table_name: str, custom_schema=None):
    cur = conn.cursor()
    cur.execute(
        "SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = %s",
        (table_name.upper(),),
    )
    existing_cols = {row[0].lower() for row in cur.fetchall()}
    incoming_schema = get_schema(df)
    native = _native_schema(custom_schema)

    added = []
    for col, dtype in incoming_schema.items():
        if col not in existing_cols:
            sql_type = native.get(col) or dtype_to_native(dtype)
            cur.execute(f'ALTER TABLE "{table_name.upper()}" ADD COLUMN "{col.upper()}" {sql_type}')
            added.append(col)
            print(f"[snowflake] New column added: '{col}' ({sql_type})")

    return added


def alter_existing_columns_to_custom_schema(conn, table_name: str, custom_schema):
    if not custom_schema:
        return [], []
    native = _native_schema(custom_schema)

    cur = conn.cursor()
    cur.execute(
        "SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = %s",
        (table_name.upper(),),
    )
    current_cols = {row[0].lower() for row in cur.fetchall()}

    altered, warnings = [], []
    for col, desired_sql_type in native.items():
        if col not in current_cols:
            continue
        try:
            cur.execute(
                f'ALTER TABLE "{table_name.upper()}" ALTER COLUMN "{col.upper()}" SET DATA TYPE {desired_sql_type}'
            )
            altered.append(col)
        except Exception as e:
            warnings.append(f"Could not change existing column '{col}' to {desired_sql_type}: {e}")

    return altered, warnings


def insert_data(conn, df, table_name: str, batch_size: int = 1000, custom_schema=None):
    cur = conn.cursor()
    pdf = df
    cols = list(pdf.columns)

    col_list = ", ".join(f'"{c.upper()}"' for c in cols)
    placeholders = ", ".join(["%s"] * len(cols))
    insert_query = f'INSERT INTO "{table_name.upper()}" ({col_list}) VALUES ({placeholders})'

    native = _native_schema(custom_schema)
    governed = {}
    if native:
        col_positions = {c: i for i, c in enumerate(cols)}
        canon_by_native = {v: k for k, v in CANONICAL_TO_NATIVE.items()}
        for col, desired_sql_type in native.items():
            if col in col_positions:
                governed[col_positions[col]] = (col, canon_by_native.get(desired_sql_type, "text"))

    def _guard(pos, value, row_idx):
        if pos not in governed or value is None:
            return value
        col, canonical = governed[pos]
        ok = (
            (canonical == "integer" and isinstance(value, int) and not isinstance(value, bool))
            or (canonical == "float" and isinstance(value, (int, float)) and not isinstance(value, bool))
            or (canonical == "boolean" and isinstance(value, bool))
            or (canonical in ("date", "timestamp") and isinstance(value, (_dt.date, _dt.datetime)))
            or (canonical in ("text", "json"))
        )
        if ok:
            return value
        print(
            f"[snowflake] custom_schema guard: row {row_idx}, column '{col}' expected '{canonical}' "
            f"but got {value!r} ({type(value).__name__}) — inserting NULL instead."
        )
        return None

    rows = [
        tuple(_guard(pos, sanitize_value(v), row_idx) for pos, v in enumerate(row))
        for row_idx, row in enumerate(pdf.itertuples(index=False, name=None))
    ]

    for i in range(0, len(rows), batch_size):
        batch = rows[i : i + batch_size]
        cur.executemany(insert_query, batch)

    print(f"[snowflake] {len(rows)} rows inserted into '{table_name}'")


def drop_table(conn, table_name: str):
    cur = conn.cursor()
    cur.execute(f'DROP TABLE "{table_name.upper()}"')


def get_last_incremental_value(conn, table_name: str, incremental_column: str):
    cur = conn.cursor()
    try:
        cur.execute(f'SELECT MAX("{incremental_column.upper()}") FROM "{table_name.upper()}"')
        return cur.fetchone()[0]
    except Exception as e:
        print(f"[snowflake] Could not fetch last incremental value: {e}")
        return None
