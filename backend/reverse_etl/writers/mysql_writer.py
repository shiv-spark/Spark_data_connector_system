"""
Writes rows OUT to an external MySQL database. Mirror image of
connectors/mysql_connector.py.

config keys: host, database, user, password, port
"""

import re
import pymysql

_IDENT_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _safe_ident(name: str) -> str:
    if not _IDENT_RE.match(name or ""):
        raise ValueError(f"Unsafe identifier: {name!r}")
    return name


def _mysql_type(value) -> str:
    if isinstance(value, bool):
        return "BOOLEAN"
    if isinstance(value, int):
        return "BIGINT"
    if isinstance(value, float):
        return "DOUBLE"
    return "TEXT"


def mysql_writer(records: list, config: dict, object_name: str,
                  upsert_key: str | None, write_mode: str, batch_size: int = 500) -> dict:
    if not records:
        return {"success": 0, "failed": 0, "errors": []}

    table_name = _safe_ident(object_name)
    columns = list(records[0].keys())
    for c in columns:
        _safe_ident(c)

    conn = pymysql.connect(
        host=config.get("host"), db=config.get("database"),
        user=config.get("user"), password=config.get("password"),
        port=int(config.get("port", 3306)), autocommit=False,
    )
    success, failed, errors = 0, 0, []
    try:
        with conn.cursor() as cur:
            cur.execute(f"SHOW TABLES LIKE %s", (table_name,))
            if not cur.fetchone():
                col_defs = ", ".join(f"`{c}` {_mysql_type(records[0].get(c))}" for c in columns)
                pk_clause = f", PRIMARY KEY (`{upsert_key}`(191))" if (write_mode == "upsert" and upsert_key) else ""
                cur.execute(f"CREATE TABLE `{table_name}` ({col_defs}{pk_clause})")
                conn.commit()

            placeholders = ", ".join(["%s"] * len(columns))
            col_list = ", ".join(f"`{c}`" for c in columns)

            if write_mode == "upsert" and upsert_key:
                update_cols = [f"`{c}`=VALUES(`{c}`)" for c in columns if c != upsert_key]
                update_clause = ", ".join(update_cols) if update_cols else f"`{upsert_key}`=VALUES(`{upsert_key}`)"
                query = f"INSERT INTO `{table_name}` ({col_list}) VALUES ({placeholders}) ON DUPLICATE KEY UPDATE {update_clause}"
            else:
                query = f"INSERT INTO `{table_name}` ({col_list}) VALUES ({placeholders})"

            rows = [tuple(r.get(c) for c in columns) for r in records]
            for i in range(0, len(rows), batch_size):
                batch = rows[i:i + batch_size]
                try:
                    cur.executemany(query, batch)
                    conn.commit()
                    success += len(batch)
                except Exception as e:
                    conn.rollback()
                    failed += len(batch)
                    errors.append(str(e))
    finally:
        conn.close()

    return {"success": success, "failed": failed, "errors": errors[:20]}
