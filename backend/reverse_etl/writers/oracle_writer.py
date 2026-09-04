"""
Writes rows OUT to Oracle. Mirror image of connectors/oracle_connector.py
(which reads FROM Oracle) — same config keys (host, database=service_name,
user, password, port), using python-oracledb thin mode.

config keys: host, database (service name), user, password, port (default 1521)
"""

import re

try:
    import oracledb
    ORACLEDB_AVAILABLE = True
except ImportError:
    ORACLEDB_AVAILABLE = False

_IDENT_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _safe_ident(name: str) -> str:
    if not _IDENT_RE.match(name or ""):
        raise ValueError(f"Unsafe identifier: {name!r}")
    return name


def _ora_type(value) -> str:
    if isinstance(value, bool):
        return "NUMBER(1)"
    if isinstance(value, int):
        return "NUMBER(38)"
    if isinstance(value, float):
        return "BINARY_DOUBLE"
    return "VARCHAR2(4000)"


def _connect(config: dict):
    if not ORACLEDB_AVAILABLE:
        raise ImportError("Oracle support requires oracledb (pip install oracledb).")
    dsn = oracledb.makedsn(
        config.get("host"), int(config.get("port") or 1521),
        service_name=config.get("database"),
    )
    return oracledb.connect(user=config.get("user"), password=config.get("password"), dsn=dsn)


def _table_exists(cur, table_name: str) -> bool:
    cur.execute(
        "SELECT COUNT(*) FROM USER_TABLES WHERE TABLE_NAME = :1",
        [table_name.upper()],
    )
    return cur.fetchone()[0] > 0


def _ensure_table(cur, table_name: str, columns: list, sample_row: dict):
    if _table_exists(cur, table_name):
        return
    col_defs = ", ".join(f'"{c}" {_ora_type(sample_row.get(c))}' for c in columns)
    cur.execute(f'CREATE TABLE "{table_name}" ({col_defs})')


def oracle_writer(records: list, config: dict, object_name: str,
                   upsert_key: str | None, write_mode: str, batch_size: int = 500) -> dict:
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
        conn.commit()

        bind_names = [f":{i+1}" for i in range(len(columns))]
        col_list = ", ".join(f'"{c}"' for c in columns)

        if write_mode == "upsert" and upsert_key:
            _safe_ident(upsert_key)
            update_cols = [c for c in columns if c != upsert_key]
            key_idx = columns.index(upsert_key) + 1
            set_clause = ", ".join(f'"{c}" = :{columns.index(c) + 1}' for c in update_cols)
            insert_cols = ", ".join(f'"{c}"' for c in columns)
            insert_vals = ", ".join(bind_names)
            # No native single-statement upsert across all oracledb setups —
            # try UPDATE first, INSERT if it affected zero rows.
            update_sql = f'UPDATE "{table_name}" SET {set_clause} WHERE "{upsert_key}" = :{key_idx}'
            insert_sql = f'INSERT INTO "{table_name}" ({insert_cols}) VALUES ({insert_vals})'

            rows = [tuple(r.get(c) for c in columns) for r in records]
            for i in range(0, len(rows), batch_size):
                batch = rows[i:i + batch_size]
                for row in batch:
                    try:
                        cur.execute(update_sql, row)
                        if cur.rowcount == 0:
                            cur.execute(insert_sql, row)
                        success += 1
                    except Exception as e:
                        failed += 1
                        errors.append(str(e))
                conn.commit()
        else:
            insert_sql = f'INSERT INTO "{table_name}" ({col_list}) VALUES ({", ".join(bind_names)})'
            rows = [tuple(r.get(c) for c in columns) for r in records]
            for i in range(0, len(rows), batch_size):
                batch = rows[i:i + batch_size]
                try:
                    cur.executemany(insert_sql, batch)
                    conn.commit()
                    success += len(batch)
                except Exception as e:
                    conn.rollback()
                    failed += len(batch)
                    errors.append(str(e))
        cur.close()
    finally:
        conn.close()

    return {"success": success, "failed": failed, "errors": errors[:20]}
