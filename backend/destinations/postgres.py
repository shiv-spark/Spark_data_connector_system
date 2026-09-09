"""
Postgres destination adapter.

This is the ORIGINAL loaders/db_loader.py logic (create_table, schema
evolution, custom-schema retroactive ALTER, batched insert, incremental
support) lifted out unchanged and reshaped into the common adapter
interface every engine in destinations/ implements:

    connect(config) -> conn
    close(conn)
    table_exists(conn, table_name) -> bool
    check_schema_mismatch(conn, df, table_name) -> dict
    create_table(conn, df, table_name, custom_schema=None)
    evolve_schema(conn, df, table_name, custom_schema=None) -> [added_cols]
    alter_existing_columns_to_custom_schema(conn, table_name, custom_schema) -> (altered, warnings)
    insert_data(conn, df, table_name, batch_size=1000, custom_schema=None)
    drop_table(conn, table_name)
    get_last_incremental_value(conn, table_name, incremental_column)

`custom_schema` here is the CANONICAL dict produced by
utils/schema_applier.resolve_custom_schema(), e.g. {"amount": "float"} —
NOT a raw SQL type string. Each adapter maps canonical -> its own native
SQL type via CANONICAL_TO_NATIVE, so the same custom_schema works
unchanged no matter which destination the user picks.
"""

import datetime as _dt
import json

import psycopg2
from psycopg2 import sql
from psycopg2.extras import execute_values

from destinations.common import get_schema, sanitize_value, validate_table_name

MAX_IDENTIFIER_LEN = 63

CANONICAL_TO_NATIVE = {
    "integer":   "BIGINT",
    "float":     "DOUBLE PRECISION",
    "boolean":   "BOOLEAN",
    "date":      "DATE",
    "timestamp": "TIMESTAMP",
    "text":      "TEXT",
    "json":      "JSONB",
}

_NATIVE_TO_CANONICAL = {v: k for k, v in CANONICAL_TO_NATIVE.items()}


def _native_schema(custom_schema: dict | None) -> dict:
    """canonical custom_schema -> {col: native SQL type string}"""
    if not custom_schema:
        return {}
    return {col: CANONICAL_TO_NATIVE.get(t, "TEXT") for col, t in custom_schema.items()}


def validate_identifier(table_name: str):
    validate_table_name(table_name, max_len=MAX_IDENTIFIER_LEN)


def connect(config: dict):
    return psycopg2.connect(
        host=config.get("host"),
        database=config.get("database"),
        user=config.get("user"),
        password=config.get("password"),
        port=config.get("port") or 5432,
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
        return "DOUBLE PRECISION"
    elif "bool" in dtype:
        return "BOOLEAN"
    elif "datetime" in dtype or "timestamp" in dtype:
        return "TIMESTAMP"
    elif "date" in dtype:
        return "DATE"
    else:
        return "TEXT"


def table_exists(conn, table_name: str) -> bool:
    cur = conn.cursor()
    cur.execute(
        """
        SELECT EXISTS (
            SELECT FROM information_schema.tables
            WHERE table_name = %s
        );
        """,
        (table_name,),
    )
    return cur.fetchone()[0]


def check_schema_mismatch(conn, df, table_name: str) -> dict:
    cur = conn.cursor()
    cur.execute(
        """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_name = %s AND table_schema = 'public'
        """,
        (table_name,),
    )
    existing_cols = set(row[0] for row in cur.fetchall())
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


def create_table(conn, df, table_name: str, custom_schema: dict | None = None):
    schema = get_schema(df)
    native = _native_schema(custom_schema)

    cur = conn.cursor()
    col_definitions = []
    for col, dtype in schema.items():
        sql_type = native.get(col) or dtype_to_native(dtype)
        col_definitions.append(
            sql.SQL("{} {}").format(sql.Identifier(col), sql.SQL(sql_type))
        )

    create_query = sql.SQL(
        """
        CREATE TABLE IF NOT EXISTS {table} (
            {cols}
        )
        """
    ).format(table=sql.Identifier(table_name), cols=sql.SQL(", ").join(col_definitions))
    try:
        cur.execute(create_query)
        print(f"[postgres] Table '{table_name}' created successfully")
    except Exception as e:
        if "pg_type_typname_nsp_index" in str(e):
            print(f"[postgres] Table '{table_name}' created concurrently by another process — continuing.")
            return
        print(f"[postgres] Table create failed: {e}")
        raise


def evolve_schema(conn, df, table_name: str, custom_schema: dict | None = None):
    cur = conn.cursor()
    cur.execute(
        """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_name = %s AND table_schema = 'public'
        """,
        (table_name,),
    )
    existing_cols = {row[0] for row in cur.fetchall()}
    incoming_schema = get_schema(df)
    native = _native_schema(custom_schema)

    added = []
    for col, dtype in incoming_schema.items():
        if col not in existing_cols:
            sql_type = native.get(col) or dtype_to_native(dtype)
            alter_query = sql.SQL("ALTER TABLE {table} ADD COLUMN {col} {type}").format(
                table=sql.Identifier(table_name), col=sql.Identifier(col), type=sql.SQL(sql_type)
            )
            cur.execute(alter_query)
            added.append(col)
            print(f"[postgres] New column added: '{col}' ({sql_type})")

    return added


def _safe_cast_sql(col_ident: str, canonical_type: str) -> str:
    c = f"{col_ident}::text"
    if canonical_type == "integer":
        return f"CASE WHEN {c} ~ '^\\s*-?\\d+\\s*$' THEN {c}::bigint ELSE NULL END"
    if canonical_type == "float":
        return f"CASE WHEN {c} ~ '^\\s*-?\\d+(\\.\\d+)?\\s*$' THEN {c}::double precision ELSE NULL END"
    if canonical_type == "boolean":
        return (
            f"CASE WHEN lower(trim({c})) IN ('true','1','yes','y','t') THEN true "
            f"WHEN lower(trim({c})) IN ('false','0','no','n','f') THEN false "
            f"ELSE NULL END"
        )
    if canonical_type in ("date", "timestamp"):
        target = "date" if canonical_type == "date" else "timestamp"
        return f"CASE WHEN {c} ~ '^\\d{{4}}-\\d{{2}}-\\d{{2}}' THEN {c}::{target} ELSE NULL END"
    if canonical_type == "json":
        return f"CASE WHEN {c} IS NOT NULL THEN to_jsonb({c}) ELSE NULL END"
    return c


def alter_existing_columns_to_custom_schema(conn, table_name: str, custom_schema: dict | None):
    """For a table that ALREADY EXISTS, retroactively ALTER any of its
    existing columns that custom_schema asks for but whose live type
    doesn't match yet. Each column altered in its own SAVEPOINT so one
    unrepresentable column doesn't fail the whole ingest."""
    if not custom_schema:
        return [], []
    native = _native_schema(custom_schema)

    cur = conn.cursor()
    cur.execute(
        """
        SELECT column_name, data_type
        FROM information_schema.columns
        WHERE table_name = %s AND table_schema = 'public'
        """,
        (table_name,),
    )
    current_types = {row[0]: row[1] for row in cur.fetchall()}

    altered, warnings = [], []
    for col, desired_sql_type in native.items():
        if col not in current_types:
            continue

        canonical = _NATIVE_TO_CANONICAL.get(desired_sql_type, "text")
        using_expr = _safe_cast_sql(sql.Identifier(col).as_string(conn), canonical)

        cur.execute("SAVEPOINT custom_schema_alter")
        try:
            alter_query = sql.SQL(
                "ALTER TABLE {table} ALTER COLUMN {col} TYPE {sql_type} USING {using_expr}"
            ).format(
                table=sql.Identifier(table_name),
                col=sql.Identifier(col),
                sql_type=sql.SQL(desired_sql_type),
                using_expr=sql.SQL(using_expr),
            )
            cur.execute(alter_query)
            cur.execute("RELEASE SAVEPOINT custom_schema_alter")
            altered.append(col)
        except Exception as e:
            cur.execute("ROLLBACK TO SAVEPOINT custom_schema_alter")
            warnings.append(f"Could not change existing column '{col}' to {desired_sql_type}: {e}")

    return altered, warnings


def insert_data(conn, df, table_name: str, batch_size: int = 1000, custom_schema: dict | None = None):
    cur = conn.cursor()
    pdf = df  # already normalized to pandas by loaders/db_loader.py before calling adapters

    cols_sql = sql.SQL(", ").join(sql.Identifier(c) for c in pdf.columns)
    insert_query = sql.SQL("INSERT INTO {table} ({cols}) VALUES %s").format(
        table=sql.Identifier(table_name), cols=cols_sql
    )

    native = _native_schema(custom_schema)
    governed = {}
    if native:
        col_positions = {c: i for i, c in enumerate(pdf.columns)}
        for col, desired_sql_type in native.items():
            if col in col_positions:
                governed[col_positions[col]] = (col, _NATIVE_TO_CANONICAL.get(desired_sql_type, "text"))

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
            f"[postgres] custom_schema guard: row {row_idx}, column '{col}' expected '{canonical}' "
            f"but got {value!r} ({type(value).__name__}) — inserting NULL instead."
        )
        return None

    rows = [
        tuple(_guard(pos, sanitize_value(v), row_idx) for pos, v in enumerate(row))
        for row_idx, row in enumerate(pdf.itertuples(index=False, name=None))
    ]

    for i in range(0, len(rows), batch_size):
        batch = rows[i : i + batch_size]
        execute_values(cur, insert_query, batch, page_size=batch_size)

    print(f"[postgres] {len(rows)} rows inserted into '{table_name}'")


def drop_table(conn, table_name: str):
    cur = conn.cursor()
    cur.execute(sql.SQL("DROP TABLE {t}").format(t=sql.Identifier(table_name)))


def get_last_incremental_value(conn, table_name: str, incremental_column: str):
    cur = conn.cursor()
    try:
        query = sql.SQL("SELECT MAX({col}) FROM {table}").format(
            col=sql.Identifier(incremental_column), table=sql.Identifier(table_name)
        )
        cur.execute(query)
        return cur.fetchone()[0]
    except Exception as e:
        print(f"[postgres] Could not fetch last incremental value: {e}")
        return None
