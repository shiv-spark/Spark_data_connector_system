"""
Writes rows OUT to an external Postgres database. Mirror image of
connectors/postgres_connector.py (which reads FROM an external Postgres).

config keys (same shape saved_connections already stores for a postgres
source, so existing postgres connections can be reused as reverse-ETL
destinations too): host, database, user, password, port
"""

import re
import psycopg2
from psycopg2 import sql
from psycopg2.extras import execute_values

_IDENT_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _safe_ident(name: str) -> str:
    if not _IDENT_RE.match(name or ""):
        raise ValueError(f"Unsafe identifier: {name!r}")
    return name


def _pg_type(value) -> str:
    if isinstance(value, bool):
        return "BOOLEAN"
    if isinstance(value, int):
        return "BIGINT"
    if isinstance(value, float):
        return "DOUBLE PRECISION"
    return "TEXT"


def _ensure_table(cur, table_name: str, columns: list, sample_row: dict):
    cur.execute("SELECT to_regclass(%s)", (table_name,))
    if cur.fetchone()[0]:
        return
    col_defs = [
        sql.SQL("{} {}").format(sql.Identifier(c), sql.SQL(_pg_type(sample_row.get(c))))
        for c in columns
    ]
    cur.execute(sql.SQL("CREATE TABLE IF NOT EXISTS {} ({})").format(
        sql.Identifier(table_name), sql.SQL(", ").join(col_defs)
    ))


def _unique_constraint_exists(cur, table_name: str, key: str) -> bool:
    """True if `key` already has a UNIQUE or PRIMARY KEY constraint (or a
    unique index) on it — the actual requirement for ON CONFLICT to work,
    not just "some constraint with our generated name exists"."""
    cur.execute("""
        SELECT 1
        FROM pg_index i
        JOIN pg_attribute a ON a.attrelid = i.indrelid AND a.attnum = ANY(i.indkey)
        WHERE i.indrelid = %s::regclass
          AND i.indisunique
          AND a.attname = %s
          AND (
                SELECT COUNT(*) FROM unnest(i.indkey) k WHERE k <> 0
              ) = 1
        LIMIT 1
    """, (table_name, key))
    return cur.fetchone() is not None


def _dedupe_by_key(rows: list, columns: list, key: str) -> list:
    """Postgres' INSERT ... ON CONFLICT can't touch the same conflicting row
    twice within one statement ('ON CONFLICT DO UPDATE command cannot affect
    row a second time'). If the source has multiple rows sharing the same
    upsert_key (e.g. upserting an orders table by customer_id), collapse
    each batch down to one row per key — last occurrence wins — before
    sending it to Postgres."""
    key_idx = columns.index(key)
    deduped = {}
    for row in rows:
        deduped[row[key_idx]] = row
    return list(deduped.values())


def postgres_writer(records: list, config: dict, object_name: str,
                     upsert_key: str | None, write_mode: str, batch_size: int = 500) -> dict:
    if not records:
        return {"success": 0, "failed": 0, "errors": []}

    table_name = _safe_ident(object_name)
    columns = list(records[0].keys())
    for c in columns:
        _safe_ident(c)

    conn = psycopg2.connect(
        host=config.get("host"), database=config.get("database"),
        user=config.get("user"), password=config.get("password"),
        port=config.get("port", "5432"),
    )
    success, failed, errors = 0, 0, []
    try:
        cur = conn.cursor()
        _ensure_table(cur, table_name, columns, records[0])
        conn.commit()

        rows = [tuple(r.get(c) for c in columns) for r in records]
        do_upsert = write_mode == "upsert" and upsert_key

        if do_upsert:
            _safe_ident(upsert_key)

            if not _unique_constraint_exists(cur, table_name, upsert_key):
                try:
                    cur.execute(
                        sql.SQL("ALTER TABLE {table} ADD CONSTRAINT {cname} UNIQUE ({key})").format(
                            table=sql.Identifier(table_name),
                            key=sql.Identifier(upsert_key),
                            cname=sql.Identifier(f"{table_name}_{upsert_key}_uq"),
                        )
                    )
                    conn.commit()
                except psycopg2.errors.UniqueViolation:
                    # The destination already has duplicate values in this
                    # column (often from earlier runs before this column was
                    # meant to be unique) — a constraint genuinely can't be
                    # added, and every ON CONFLICT below will keep failing
                    # with a confusing Postgres error until the data or the
                    # chosen upsert_key is fixed. Fail loudly with a clear
                    # explanation instead of silently limping along.
                    conn.rollback()
                    return {
                        "success": 0, "failed": len(records),
                        "errors": [
                            f"Cannot upsert on '{upsert_key}': '{table_name}' already has "
                            f"duplicate values in that column, so a UNIQUE constraint can't "
                            f"be created. Either pick a column that's actually unique per row "
                            f"as the upsert_key, or clean up/deduplicate '{table_name}' first."
                        ],
                    }
                except Exception:
                    # Some other reason the ALTER didn't apply (e.g. a
                    # differently-named constraint/unique index already
                    # covers this column) — harmless, move on.
                    conn.rollback()

            update_cols = [c for c in columns if c != upsert_key]
            set_clause = sql.SQL(", ").join(
                sql.SQL("{c} = EXCLUDED.{c}").format(c=sql.Identifier(c)) for c in update_cols
            )
            query = sql.SQL(
                "INSERT INTO {table} ({cols}) VALUES %s "
                "ON CONFLICT ({key}) DO UPDATE SET {set_clause}"
            ).format(
                table=sql.Identifier(table_name),
                cols=sql.SQL(", ").join(sql.Identifier(c) for c in columns),
                key=sql.Identifier(upsert_key),
                set_clause=set_clause,
            )
        else:
            query = sql.SQL("INSERT INTO {table} ({cols}) VALUES %s").format(
                table=sql.Identifier(table_name),
                cols=sql.SQL(", ").join(sql.Identifier(c) for c in columns),
            )

        for i in range(0, len(rows), batch_size):
            batch = rows[i:i + batch_size]
            if do_upsert:
                # Dedupe AFTER slicing into batches so counts stay meaningful
                # per-batch, and because two duplicate keys landing in
                # different batches is fine — only same-batch duplicates
                # trip Postgres up.
                deduped_batch = _dedupe_by_key(batch, columns, upsert_key)
                dropped = len(batch) - len(deduped_batch)
            else:
                deduped_batch = batch
                dropped = 0
            try:
                execute_values(cur, query.as_string(cur), deduped_batch)
                conn.commit()
                success += len(deduped_batch)
                if dropped:
                    errors.append(
                        f"{dropped} row(s) in this batch shared a duplicate '{upsert_key}' "
                        f"with another row in the same batch — only the last one was kept."
                    )
            except Exception as e:
                conn.rollback()
                failed += len(batch)
                errors.append(str(e))
        cur.close()
    finally:
        conn.close()

    return {"success": success, "failed": failed, "errors": errors[:20]}
