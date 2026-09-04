"""
Writes rows OUT to Snowflake. Mirror image of connectors/snowflake_connector.py
(which reads FROM Snowflake) — same config keys, so an existing Snowflake
saved connection can be reused as a reverse-ETL destination unchanged.

config keys: account, user, password, warehouse, database, schema (default
"PUBLIC"), role (optional)
"""

import os
import re
import uuid

try:
    import snowflake.connector
    SNOWFLAKE_AVAILABLE = True
except ImportError:
    SNOWFLAKE_AVAILABLE = False

_IDENT_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _safe_ident(name: str) -> str:
    if not _IDENT_RE.match(name or ""):
        raise ValueError(f"Unsafe identifier: {name!r}")
    return name


def _sf_type(value) -> str:
    if isinstance(value, bool):
        return "BOOLEAN"
    if isinstance(value, int):
        return "NUMBER"
    if isinstance(value, float):
        return "FLOAT"
    return "VARCHAR"


def _connect(config: dict):
    if not SNOWFLAKE_AVAILABLE:
        raise ImportError("Snowflake support requires snowflake-connector-python.")
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
    return snowflake.connector.connect(**conn_params)


def _ensure_table(cur, table_name: str, columns: list, sample_row: dict):
    cur.execute(
        "SELECT COUNT(*) FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_NAME = %s",
        (table_name.upper(),),
    )
    if cur.fetchone()[0]:
        return
    col_defs = ", ".join(f'"{c}" {_sf_type(sample_row.get(c))}' for c in columns)
    cur.execute(f'CREATE TABLE IF NOT EXISTS "{table_name}" ({col_defs})')


def snowflake_writer(records: list, config: dict, object_name: str,
                      upsert_key: str | None, write_mode: str, batch_size: int = 1000) -> dict:
    if not records:
        return {"success": 0, "failed": 0, "errors": []}

    table_name = _safe_ident(object_name)
    columns = list(records[0].keys())
    for c in columns:
        _safe_ident(c)

    conn = _connect(config)
    success, failed, errors = 0, 0, []
    try:
        cur = conn.cursor()
        _ensure_table(cur, table_name, columns, records[0])

        col_list = ", ".join(f'"{c}"' for c in columns)
        placeholders = ", ".join(["%s"] * len(columns))

        if write_mode == "upsert" and upsert_key:
            _safe_ident(upsert_key)
            # Snowflake has no native upsert-on-insert; stage rows into a
            # temp table then MERGE, same pattern as postgres ON CONFLICT.
            staging = f"{table_name}_stage_{os.getpid()}_{uuid.uuid4().hex[:6]}"
            cur.execute(f'CREATE TEMPORARY TABLE "{staging}" LIKE "{table_name}"')
            insert_stage = f'INSERT INTO "{staging}" ({col_list}) VALUES ({placeholders})'
            update_cols = [c for c in columns if c != upsert_key]
            set_clause = ", ".join(f'tgt."{c}" = src."{c}"' for c in update_cols)
            merge_sql = f'''
                MERGE INTO "{table_name}" tgt
                USING "{staging}" src
                ON tgt."{upsert_key}" = src."{upsert_key}"
                WHEN MATCHED THEN UPDATE SET {set_clause}
                WHEN NOT MATCHED THEN INSERT ({col_list}) VALUES ({", ".join(f'src."{c}"' for c in columns)})
            '''
            rows = [tuple(r.get(c) for c in columns) for r in records]
            for i in range(0, len(rows), batch_size):
                batch = rows[i:i + batch_size]
                try:
                    cur.executemany(insert_stage, batch)
                    cur.execute(merge_sql)
                    cur.execute(f'TRUNCATE TABLE "{staging}"')
                    success += len(batch)
                except Exception as e:
                    failed += len(batch)
                    errors.append(str(e))
            cur.execute(f'DROP TABLE IF EXISTS "{staging}"')
        else:
            query = f'INSERT INTO "{table_name}" ({col_list}) VALUES ({placeholders})'
            rows = [tuple(r.get(c) for c in columns) for r in records]
            for i in range(0, len(rows), batch_size):
                batch = rows[i:i + batch_size]
                try:
                    cur.executemany(query, batch)
                    success += len(batch)
                except Exception as e:
                    failed += len(batch)
                    errors.append(str(e))
        cur.close()
    finally:
        conn.close()

    return {"success": success, "failed": failed, "errors": errors[:20]}
