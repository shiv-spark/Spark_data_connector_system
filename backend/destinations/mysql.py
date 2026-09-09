"""
MySQL destination adapter — same adapter interface as destinations/postgres.py.

Requires `pymysql` (pip install pymysql). Import is optional/guarded so the
backend still boots even if the package isn't installed; the destination
just isn't usable until it is (same pattern as testers/mysql.py and
reverse_etl/writers/mysql_writer.py already use).

Known limitations vs. the Postgres adapter (documented rather than hidden):
- `alter_existing_columns_to_custom_schema` uses a plain MODIFY COLUMN,
  not Postgres's row-level "cast succeeds or becomes NULL" SAVEPOINT
  trick — MySQL has no equivalent generic USING-cast. If the column's
  existing data can't be represented in the new type, the ALTER is
  skipped for that column with a warning (never fails the whole ingest).
"""

import datetime as _dt

try:
    import pymysql

    PYMYSQL_AVAILABLE = True
except ImportError:
    PYMYSQL_AVAILABLE = False

from destinations.common import get_schema, sanitize_value, validate_table_name

MAX_IDENTIFIER_LEN = 64

CANONICAL_TO_NATIVE = {
    "integer":   "BIGINT",
    "float":     "DOUBLE",
    "boolean":   "BOOLEAN",
    "date":      "DATE",
    "timestamp": "DATETIME",
    "text":      "TEXT",
    "json":      "JSON",
}


def _native_schema(custom_schema):
    if not custom_schema:
        return {}
    return {col: CANONICAL_TO_NATIVE.get(t, "TEXT") for col, t in custom_schema.items()}


def validate_identifier(table_name: str):
    validate_table_name(table_name, max_len=MAX_IDENTIFIER_LEN)


def _require_pymysql():
    if not PYMYSQL_AVAILABLE:
        raise ImportError("MySQL destination requires pymysql (pip install pymysql).")


def connect(config: dict):
    _require_pymysql()
    return pymysql.connect(
        host=config.get("host"),
        port=int(config.get("port") or 3306),
        user=config.get("user"),
        password=config.get("password"),
        database=config.get("database"),
        autocommit=False,
    )


def close(conn):
    try:
        conn.close()
    except Exception:
        pass


def dtype_to_native(dtype: str) -> str:
    dtype = dtype.lower()
    if "int" in dtype:
        return "BIGINT"
    elif "float" in dtype or "double" in dtype:
        return "DOUBLE"
    elif "bool" in dtype:
        return "BOOLEAN"
    elif "datetime" in dtype or "timestamp" in dtype:
        return "DATETIME"
    elif "date" in dtype:
        return "DATE"
    else:
        return "TEXT"


def table_exists(conn, table_name: str) -> bool:
    cur = conn.cursor()
    cur.execute(
        "SELECT COUNT(*) FROM information_schema.tables "
        "WHERE table_schema = DATABASE() AND table_name = %s",
        (table_name,),
    )
    return cur.fetchone()[0] > 0


def check_schema_mismatch(conn, df, table_name: str) -> dict:
    cur = conn.cursor()
    cur.execute(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_schema = DATABASE() AND table_name = %s",
        (table_name,),
    )
    existing_cols = {row[0] for row in cur.fetchall()}
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
        col_defs.append(f"`{col}` {sql_type}")

    cur.execute(f"CREATE TABLE IF NOT EXISTS `{table_name}` ({', '.join(col_defs)})")
    print(f"[mysql] Table '{table_name}' created successfully")


def evolve_schema(conn, df, table_name: str, custom_schema=None):
    cur = conn.cursor()
    cur.execute(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_schema = DATABASE() AND table_name = %s",
        (table_name,),
    )
    existing_cols = {row[0] for row in cur.fetchall()}
    incoming_schema = get_schema(df)
    native = _native_schema(custom_schema)

    added = []
    for col, dtype in incoming_schema.items():
        if col not in existing_cols:
            sql_type = native.get(col) or dtype_to_native(dtype)
            cur.execute(f"ALTER TABLE `{table_name}` ADD COLUMN `{col}` {sql_type}")
            added.append(col)
            print(f"[mysql] New column added: '{col}' ({sql_type})")

    return added


def alter_existing_columns_to_custom_schema(conn, table_name: str, custom_schema):
    """Best-effort MODIFY COLUMN — see module docstring for the limitation
    vs. Postgres's row-safe cast."""
    if not custom_schema:
        return [], []
    native = _native_schema(custom_schema)

    cur = conn.cursor()
    cur.execute(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_schema = DATABASE() AND table_name = %s",
        (table_name,),
    )
    current_cols = {row[0] for row in cur.fetchall()}

    altered, warnings = [], []
    for col, desired_sql_type in native.items():
        if col not in current_cols:
            continue
        try:
            cur.execute(f"ALTER TABLE `{table_name}` MODIFY COLUMN `{col}` {desired_sql_type}")
            altered.append(col)
        except Exception as e:
            warnings.append(f"Could not change existing column '{col}' to {desired_sql_type}: {e}")

    return altered, warnings


def insert_data(conn, df, table_name: str, batch_size: int = 1000, custom_schema=None):
    cur = conn.cursor()
    pdf = df

    cols = list(pdf.columns)
    col_list = ", ".join(f"`{c}`" for c in cols)
    placeholders = ", ".join(["%s"] * len(cols))
    insert_query = f"INSERT INTO `{table_name}` ({col_list}) VALUES ({placeholders})"

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
            f"[mysql] custom_schema guard: row {row_idx}, column '{col}' expected '{canonical}' "
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

    print(f"[mysql] {len(rows)} rows inserted into '{table_name}'")


def drop_table(conn, table_name: str):
    cur = conn.cursor()
    cur.execute(f"DROP TABLE `{table_name}`")


def get_last_incremental_value(conn, table_name: str, incremental_column: str):
    cur = conn.cursor()
    try:
        cur.execute(f"SELECT MAX(`{incremental_column}`) FROM `{table_name}`")
        return cur.fetchone()[0]
    except Exception as e:
        print(f"[mysql] Could not fetch last incremental value: {e}")
        return None
