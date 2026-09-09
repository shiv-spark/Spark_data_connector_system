"""
Oracle destination adapter — same adapter interface as destinations/postgres.py.

Uses python-oracledb in "thin" mode (no Oracle Instant Client needed),
same as testers/oracle.py and reverse_etl/writers/oracle_writer.py.

Oracle-specific notes (documented rather than hidden):
- Identifiers are used UNQUOTED, so Oracle folds them to UPPERCASE
  automatically (consistent with reverse_etl/writers/oracle_writer.py, so
  a saved Oracle connection behaves the same way whether it's used as a
  reverse-ETL destination or an ingest destination). Table/column names
  must start with a LETTER (not underscore) for this to be valid Oracle —
  enforced in validate_identifier() below, stricter than the shared
  common.validate_table_name().
- No native BOOLEAN type — mapped to NUMBER(1) (0/1).
- TEXT/JSON columns are mapped to CLOB (safe for any length) rather than
  VARCHAR2(4000), which would silently truncate longer values.
- `alter_existing_columns_to_custom_schema` uses MODIFY, best-effort like
  the MySQL adapter — Oracle also has no generic safe-cast-or-NULL USING
  clause.
"""

import datetime as _dt
import re

try:
    import oracledb

    ORACLEDB_AVAILABLE = True
except ImportError:
    ORACLEDB_AVAILABLE = False

from destinations.common import get_schema, sanitize_value

MAX_IDENTIFIER_LEN = 128

_ORACLE_IDENT_RE = re.compile(r"^[a-zA-Z][a-zA-Z0-9_]*$")

CANONICAL_TO_NATIVE = {
    "integer":   "NUMBER(38)",
    "float":     "BINARY_DOUBLE",
    "boolean":   "NUMBER(1)",
    "date":      "DATE",
    "timestamp": "TIMESTAMP",
    "text":      "CLOB",
    "json":      "CLOB",
}


def _native_schema(custom_schema):
    if not custom_schema:
        return {}
    return {col: CANONICAL_TO_NATIVE.get(t, "CLOB") for col, t in custom_schema.items()}


def validate_identifier(table_name: str):
    if not table_name or not _ORACLE_IDENT_RE.match(table_name):
        raise ValueError(
            f"Invalid table_name '{table_name}' — Oracle identifiers must start with a "
            f"letter and contain only letters, numbers, and underscores"
        )
    if len(table_name) > MAX_IDENTIFIER_LEN:
        raise ValueError(f"table_name cannot be longer than {MAX_IDENTIFIER_LEN} characters")


def _require_oracledb():
    if not ORACLEDB_AVAILABLE:
        raise ImportError("Oracle destination requires oracledb (pip install oracledb).")


def connect(config: dict):
    _require_oracledb()
    dsn = oracledb.makedsn(
        config.get("host"), int(config.get("port") or 1521), service_name=config.get("database")
    )
    return oracledb.connect(user=config.get("user"), password=config.get("password"), dsn=dsn)


def close(conn):
    try:
        conn.close()
    except Exception:
        pass


def dtype_to_native(dtype: str) -> str:
    dtype = dtype.lower()
    if "int" in dtype:
        return "NUMBER(38)"
    elif "float" in dtype or "double" in dtype:
        return "BINARY_DOUBLE"
    elif "bool" in dtype:
        return "NUMBER(1)"
    elif "datetime" in dtype or "timestamp" in dtype:
        return "TIMESTAMP"
    elif "date" in dtype:
        return "DATE"
    else:
        return "CLOB"


def table_exists(conn, table_name: str) -> bool:
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM USER_TABLES WHERE TABLE_NAME = :1", [table_name.upper()])
    return cur.fetchone()[0] > 0


def check_schema_mismatch(conn, df, table_name: str) -> dict:
    cur = conn.cursor()
    cur.execute("SELECT COLUMN_NAME FROM USER_TAB_COLUMNS WHERE TABLE_NAME = :1", [table_name.upper()])
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

    try:
        cur.execute(f'CREATE TABLE "{table_name.upper()}" ({", ".join(col_defs)})')
        print(f"[oracle] Table '{table_name}' created successfully")
    except Exception as e:
        if "ORA-00955" in str(e):  # name already used by an existing object
            print(f"[oracle] Table '{table_name}' already exists — continuing.")
            return
        raise


def evolve_schema(conn, df, table_name: str, custom_schema=None):
    cur = conn.cursor()
    cur.execute("SELECT COLUMN_NAME FROM USER_TAB_COLUMNS WHERE TABLE_NAME = :1", [table_name.upper()])
    existing_cols = {row[0].lower() for row in cur.fetchall()}
    incoming_schema = get_schema(df)
    native = _native_schema(custom_schema)

    added = []
    for col, dtype in incoming_schema.items():
        if col not in existing_cols:
            sql_type = native.get(col) or dtype_to_native(dtype)
            cur.execute(f'ALTER TABLE "{table_name.upper()}" ADD ("{col.upper()}" {sql_type})')
            added.append(col)
            print(f"[oracle] New column added: '{col}' ({sql_type})")

    return added


def alter_existing_columns_to_custom_schema(conn, table_name: str, custom_schema):
    if not custom_schema:
        return [], []
    native = _native_schema(custom_schema)

    cur = conn.cursor()
    cur.execute("SELECT COLUMN_NAME FROM USER_TAB_COLUMNS WHERE TABLE_NAME = :1", [table_name.upper()])
    current_cols = {row[0].lower() for row in cur.fetchall()}

    altered, warnings = [], []
    for col, desired_sql_type in native.items():
        if col not in current_cols:
            continue
        try:
            cur.execute(f'ALTER TABLE "{table_name.upper()}" MODIFY ("{col.upper()}" {desired_sql_type})')
            altered.append(col)
        except Exception as e:
            warnings.append(f"Could not change existing column '{col}' to {desired_sql_type}: {e}")

    return altered, warnings


def insert_data(conn, df, table_name: str, batch_size: int = 1000, custom_schema=None):
    cur = conn.cursor()
    pdf = df
    cols = list(pdf.columns)

    col_list = ", ".join(f'"{c.upper()}"' for c in cols)
    binds = ", ".join(f":{i+1}" for i in range(len(cols)))
    insert_query = f'INSERT INTO "{table_name.upper()}" ({col_list}) VALUES ({binds})'

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
            or (canonical == "boolean" and isinstance(value, (bool, int)))
            or (canonical in ("date", "timestamp") and isinstance(value, (_dt.date, _dt.datetime)))
            or (canonical in ("text", "json"))
        )
        if ok:
            return int(value) if canonical == "boolean" and isinstance(value, bool) else value
        print(
            f"[oracle] custom_schema guard: row {row_idx}, column '{col}' expected '{canonical}' "
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

    print(f"[oracle] {len(rows)} rows inserted into '{table_name}'")


def drop_table(conn, table_name: str):
    cur = conn.cursor()
    cur.execute(f'DROP TABLE "{table_name.upper()}"')


def get_last_incremental_value(conn, table_name: str, incremental_column: str):
    cur = conn.cursor()
    try:
        cur.execute(f'SELECT MAX("{incremental_column.upper()}") FROM "{table_name.upper()}"')
        return cur.fetchone()[0]
    except Exception as e:
        print(f"[oracle] Could not fetch last incremental value: {e}")
        return None
