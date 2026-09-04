"""
Pulls rows OUT of the central warehouse Postgres — the mirror image of
connectors/postgres_connector.py, which pulls rows IN from an external
Postgres. Reverse ETL always reads from this same warehouse; it's the
destination side that varies (postgres/mysql/salesforce/hubspot/sheets/webhook).
"""

import re
import pandas as pd
import polars as pl
import psycopg2

from reverse_etl.db import DB_CONFIG

_IDENT_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _validate_identifier(name: str, label: str):
    if not name or not _IDENT_RE.match(name):
        raise ValueError(f"Invalid {label}: {name!r}")


def build_select_query(source_table: str | None, source_query: str | None,
                        filter_sql: str | None, incremental_column: str | None,
                        last_value) -> str:
    if source_query:
        q = source_query.strip().rstrip(";")
        if not q.lower().startswith("select"):
            raise ValueError("source_query must be a SELECT statement")
        return q

    _validate_identifier(source_table, "source_table")
    query = f'SELECT * FROM "{source_table}"'
    clauses = []
    if filter_sql:
        clauses.append(f"({filter_sql})")
    if incremental_column and last_value is not None:
        _validate_identifier(incremental_column, "incremental_column")
        clauses.append(f'"{incremental_column}"::text > %(last_value)s::text')
    # if incremental_column and last_value is not None:
    #     _validate_identifier(incremental_column, "incremental_column")
    #     clauses.append(f'"{incremental_column}" > %(last_value)s')
    if clauses:
        query += " WHERE " + " AND ".join(clauses)
    if incremental_column:
        _validate_identifier(incremental_column, "incremental_column")
        query += f' ORDER BY "{incremental_column}" ASC'
    return query


def extract_from_warehouse(source_table: str | None = None, source_query: str | None = None,
                            filter_sql: str | None = None, incremental_column: str | None = None,
                            last_value=None) -> pl.DataFrame:
    query = build_select_query(source_table, source_query, filter_sql, incremental_column, last_value)
    params = {"last_value": last_value} if (incremental_column and last_value is not None and not source_query) else None

    conn = psycopg2.connect(**DB_CONFIG)
    try:
        df = pd.read_sql(query, conn, params=params)
    finally:
        conn.close()
    return pl.from_pandas(df)


def latest_incremental_value(df: pl.DataFrame, incremental_column: str):
    if incremental_column not in df.columns or df.shape[0] == 0:
        return None
    return df[incremental_column].max()
