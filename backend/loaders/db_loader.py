# import psycopg2
# import re
# import polars as pl
# import pandas as pd
# import numpy as np
# from psycopg2 import sql
# import time
# from psycopg2.extras import execute_values
# import os
# from pathlib import Path
# from dotenv import load_dotenv
# import json
# project_root = Path(__file__).parent.parent.parent
# load_dotenv(project_root / ".env")

# DB_CONFIG = {
#     "host":     os.getenv("DB_HOST",     "postgres"),
#     "database": os.getenv("DB_NAME",     "airflow"),
#     "user":     os.getenv("DB_USER",     "airflow"),
#     "password": os.getenv("DB_PASSWORD", "airflow"),
#     "port":     os.getenv("DB_PORT",     "5432"),
# }

# # ─────────────────────────────────────────────
# # CLEAN COLUMN NAMES
# # ─────────────────────────────────────────────

# def clean_column(name):
#     name = str(name).lower().strip()
#     name = re.sub(r"[^\w]+", "_", name)
#     name = re.sub(r"^_+|_+$", "", name)
#     if re.match(r"^\d", name):
#         name = f"col_{name}"
#     return name or "unnamed"

# # ─────────────────────────────────────────────
# # GET SCHEMA
# # ─────────────────────────────────────────────

# def get_schema(df) -> dict:
#     if isinstance(df, pl.DataFrame):
#         return {col: str(dtype) for col, dtype in df.schema.items()}
#     elif isinstance(df, pd.DataFrame):
#         return {col: str(dtype) for col, dtype in df.dtypes.items()}
#     else:
#         raise TypeError(f"Unsupported DataFrame type: {type(df)}")


# # ─────────────────────────────────────────────
# # DTYPE → PostgreSQL TYPE MAPPING
# # ─────────────────────────────────────────────

# def dtype_to_sql(dtype: str) -> str:
#     dtype = dtype.lower()
#     if "int" in dtype:
#         return "BIGINT"
#     elif "float" in dtype or "double" in dtype:
#         return "DOUBLE PRECISION"
#     elif "bool" in dtype:
#         return "BOOLEAN"
#     elif "datetime" in dtype or "timestamp" in dtype:
#         return "TIMESTAMP"
#     elif "date" in dtype:
#         return "DATE"
#     else:
#         return "TEXT"

# # ─────────────────────────────────────────────
# # GET ALL TABLES
# # ─────────────────────────────────────────────

# def get_all_tables(cursor):
#     cursor.execute("""
#         SELECT table_name
#         FROM information_schema.tables
#         WHERE table_schema = 'public'
#     """)
#     return [t[0] for t in cursor.fetchall()]


# # ─────────────────────────────────────────────
# # GET TABLE COLUMNS
# # ─────────────────────────────────────────────

# def get_table_columns(cursor, table_name):
#     cursor.execute("""
#         SELECT column_name
#         FROM information_schema.columns
#         WHERE table_name = %s
#         ORDER BY ordinal_position
#     """, (table_name,))
#     return [r[0] for r in cursor.fetchall()]



# # ─────────────────────────────────────────────
# # TABLE EXISTS CHECK
# # ─────────────────────────────────────────────

# def table_exists(cursor, table_name):
#     cursor.execute("""
#         SELECT EXISTS (
#             SELECT FROM information_schema.tables
#             WHERE table_name = %s
#         );
#     """, (table_name,))
#     return cursor.fetchone()[0]



# # ─────────────────────────────────────────────
# # CREATE TABLE
# # ─────────────────────────────────────────────

# def create_table(cursor, df, table_name):
#     schema = get_schema(df)

#     col_definitions = []
#     for col, dtype in schema.items():
#         sql_type   = dtype_to_sql(dtype)
#         # with sql.SQL and sql.Identifier, column names and table names are safely quoted to prevent SQL injection and handle special characters. For example, a column named "user name" will be quoted as "user name" in the SQL query, ensuring it is treated as a single identifier.
#         col_definitions.append(
#             sql.SQL("{} {}").format(
#                 sql.Identifier(col),
#                 sql.SQL(sql_type)
#             )
#         )

#     create_query = sql.SQL("""
#         CREATE TABLE IF NOT EXISTS {table} (
#             {cols}
#         )
#     """).format(
#         table = sql.Identifier(table_name),
#         cols  = sql.SQL(", ").join(col_definitions)
#     )
#     try:
#         cursor.execute(create_query)
#         print(f"Table '{table_name}' created successfully")
#     except Exception as e:
#         # Concurrent CREATE TABLE IF NOT EXISTS calls can race on Postgres's
#         # internal pg_type catalog even though IF NOT EXISTS is used — if
#         # that's what happened, the table now exists (created by the other
#         # transaction), so just continue instead of failing the whole run.
#         if "pg_type_typname_nsp_index" in str(e):
#             print(f"Table '{table_name}' was created concurrently by another process — continuing.")
#             return
#         print(f"Table create failed: {e}")
#         raise



# # ─────────────────────────────────────────────
# # CHECK SCHEMA MISMATCH
# # ─────────────────────────────────────────────
# def check_schema_mismatch(cursor, df, table_name):
#     cursor.execute("""
#         SELECT column_name
#         FROM information_schema.columns
#         WHERE table_name = %s AND table_schema = 'public'
#     """, (table_name,))
#     existing_cols = set(row[0] for row in cursor.fetchall())
#     incoming_cols = set(df.columns)

#     missing_in_file = existing_cols - incoming_cols
#     extra_in_file   = incoming_cols - existing_cols
#     matched         = existing_cols & incoming_cols

#     match_pct = round(len(matched) / len(existing_cols) * 100, 2) if existing_cols else 100.0

#     print(f"Matched   : {sorted(matched)}")
#     print(f"Missing   : {sorted(missing_in_file)}  → NULL will be inserted")
#     print(f"Extra     : {sorted(extra_in_file)}  → new columns will be added")
#     print(f"Match %   : {match_pct}%")

#     if match_pct < 80:
#         print(f"WARNING: Only {match_pct}% columns match — filling many NULLs and adding many new columns may indicate a wrong file or bad mapping. Please verify.")

#     return {
#         "matched":         sorted(matched),
#         "missing_in_file": sorted(missing_in_file),
#         "extra_in_file":   sorted(extra_in_file),
#         "match_pct":       match_pct
#     }

# # ─────────────────────────────────────────────
# # INSERT DATA
# # ─────────────────────────────────────────────
# import json   # ← top pe already ho sakta hai, confirm karo import hai

# def insert_data(cursor, df, table_name, batch_size=1000):
#     if isinstance(df, pl.DataFrame):
#         pdf = df.to_pandas()
#     else:
#         pdf = df

#     cols_sql = sql.SQL(", ").join(
#         sql.Identifier(c) for c in pdf.columns
#     )
#     insert_query = sql.SQL(
#         "INSERT INTO {table} ({cols}) VALUES %s"
#     ).format(
#         table = sql.Identifier(table_name),
#         cols  = cols_sql
#     )

#     def _sanitize_value(v):
#         if v is None:
#             return None
#         if isinstance(v, float) and np.isnan(v):
#             return None
#         if isinstance(v, np.bool_):
#             return bool(v)
#         if isinstance(v, (np.integer, np.floating)):
#             return v.item()
#         # ── NEW: lists, numpy arrays, dicts — Postgres/psycopg2 can't
#         # adapt these directly. Serialize to a JSON string so they land
#         # in the (TEXT-typed) column as readable JSON instead of failing
#         # the whole insert.
#         if isinstance(v, (np.ndarray, list, dict)):
#             try:
#                 return json.dumps(v.tolist() if isinstance(v, np.ndarray) else v, default=str)
#             except (TypeError, ValueError):
#                 return str(v)
#         return v

#     rows = [
#         tuple(_sanitize_value(v) for v in row)
#         for row in pdf.itertuples(index=False, name=None)
#     ]

#     for i in range(0, len(rows), batch_size):
#         batch = rows[i : i + batch_size]
#         execute_values(cursor, insert_query, batch, page_size=batch_size)
#         print(f"Inserted rows {i+1} to {min(i+batch_size, len(rows))}")

#     print(f"{len(rows)} rows inserted into '{table_name}'")

# # ─────────────────────────────────────────────
# # Schema evolution 
# # (for option=1 append, if new columns detected then alter table to add them before insert)
# # ────────────────────────────────────────────
# def evolve_schema(cursor, df, table_name):
#     cursor.execute("""
#         SELECT column_name
#         FROM information_schema.columns
#         WHERE table_name = %s AND table_schema = 'public'
#     """, (table_name,))
#     existing_cols   = {row[0] for row in cursor.fetchall()}
#     incoming_schema = get_schema(df)

#     added = []
#     for col, dtype in incoming_schema.items():
#         if col not in existing_cols:
#             sql_type = dtype_to_sql(dtype)
#             # ALTER TABLE bhi safely banao
#             alter_query = sql.SQL(
#                 "ALTER TABLE {table} ADD COLUMN {col} {type}"
#             ).format(
#                 table = sql.Identifier(table_name),
#                 col   = sql.Identifier(col),
#                 type  = sql.SQL(sql_type)
#             )
#             cursor.execute(alter_query)
#             added.append(col)
#             print(f"New column added: '{col}' ({sql_type})")

#     if added:
#         print(f"Schema evolved — {len(added)} column(s) added: {added}")
#     else:
#         print("Schema unchanged.")

#     return added

# # ────────────────────────────────────────────  
# # Observability: Log pipeline metrics to a separate table
# # ────────────────────────────────────────────
# def log_pipeline_metrics(
#                         pipeline_id,
#                         table_name,
#                         rows_inserted=0,
#                         rows_skipped=0,
#                         rows_failed=0,
#                         duration_sec=0.0,
#                         evolved_columns=None,
#                         match_pct=100.0,
#                         file_name=None,
#                         connector_type=None,
#                         option=None,
#                         status="SUCCESS",
#                         error_message=None
#                     ):
#     try:
#         conn = psycopg2.connect(**DB_CONFIG)
#         cursor = conn.cursor()
#         cursor.execute("""
#             INSERT INTO pipeline_metrics (
#                 pipeline_id, table_name, rows_inserted, rows_skipped,
#                 rows_failed, duration_sec, evolved_columns, match_pct,
#                 file_name, connector_type, option, status, error_message
#             ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
#         """, (
#             pipeline_id,
#             table_name,
#             rows_inserted,
#             rows_skipped,
#             rows_failed,
#             round(duration_sec, 2),
#             evolved_columns or [],
#             match_pct,
#             file_name,
#             connector_type,
#             option,
#             status,
#             error_message
#         ))
#         conn.commit()
#         cursor.close()
#         conn.close()
#         print(f"Metrics logged — {rows_inserted} rows | {duration_sec:.2f}s | {status}")
#     except Exception as e:
#         print(f"Metrics log failed: {e}")  # if metrics logging will fail, it should not break the main pipeline


# # ─────────────────────────────────────────────
# # VALIDATE TABLE NAME
# # ─────────────────────────────────────────────
# def validate_table_name(table_name: str):
#     """
#     Only allow alphanumeric and underscore.
#     Reject any special character.
#     """
#     if not table_name:
#         raise ValueError("table_name will be required for all connector types in future, so please provide a valid table_name in your config. It should contain only letters, numbers, and underscores, and must start with a letter or underscore.")

#     if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', table_name):
#         raise ValueError(
#             f"Invalid table_name '{table_name}' — "
#             f"only letters, numbers, and underscores are allowed"
#         )

#     if len(table_name) > 63:   # PostgreSQL limit
#         raise ValueError(f"table_name cannot be longer than 63 characters")
    
# # ─────────────────────────────────────────────
# # incremental load support (for future enhancement, not implemented in current version)
# # ─────────────────────────────────────────────

# # ─────────────────────────────────────────────
# # GET LAST INCREMENTAL VALUE
# # ─────────────────────────────────────────────

# def get_last_incremental_value(cursor, table_name: str, incremental_column: str):
#     """
#     Fetch the MAX value of the incremental_column from the target table.
#     This will be used as the last sync point for incremental loading.
#     """
#     try:
#         query = sql.SQL(
#             "SELECT MAX({col}) FROM {table}"
#         ).format(
#             col   = sql.Identifier(incremental_column),
#             table = sql.Identifier(table_name)
#         )
#         cursor.execute(query)
#         result = cursor.fetchone()[0]
#         print(f"Last incremental value — {incremental_column}: {result}")
#         return result
#     except Exception as e:
#         print(f"Could not fetch last value: {e}")
#         return None


# # ─────────────────────────────────────────────
# # FILTER DATAFRAME — INCREMENTAL
# # ─────────────────────────────────────────────

# def filter_incremental(df, incremental_column: str, last_value):
#     """
#     Only contain new rows in the DataFrame — 
#     where incremental_column > last_value
#     """
#     if last_value is None:
#         print("No last value found — full load will be performed")
#         return df

#     if isinstance(df, pl.DataFrame):
#         original_count = df.shape[0]
#         df = df.filter(pl.col(incremental_column) > last_value)
#         print(f"Incremental filter — {original_count} → {df.shape[0]} rows (new only)")

#     elif isinstance(df, pd.DataFrame):
#         original_count = df.shape[0]
#         df = df[df[incremental_column] > last_value]
#         print(f"Incremental filter — {original_count} → {df.shape[0]} rows (new only)")

#     return df

# # ─────────────────────────────────────────────
# # MAIN LOAD FUNCTION
# # ─────────────────────────────────────────────
# def load_to_db(df, option=None, table_name=None,
#                pipeline_id=None, connector_type=None, file_name=None,
#                sync_mode="full", incremental_column=None):   # ← new params

#     validate_table_name(table_name)

#     conn   = psycopg2.connect(**DB_CONFIG)
#     cursor = conn.cursor()

#     if isinstance(df, pl.DataFrame):
#         df = df.rename({col: clean_column(col) for col in df.columns})
#     else:
#         df.columns = [clean_column(c) for c in df.columns]

#     print(f"Columns: {list(df.columns)}")
#     print(f"Sync mode: {sync_mode}")

#     evolved_cols = []
#     match_pct    = 100.0
#     start_time   = time.time()

#     try:
#         conn.autocommit = False

#         # ── INCREMENTAL FILTER ───────────────────────────
#         if sync_mode == "incremental" and incremental_column:

#             # column existing in df?
#             if incremental_column not in df.columns:
#                 raise ValueError(
#                     f"incremental_column '{incremental_column}' "
#                     f"not found in data. Available: {list(df.columns)}"
#                 )

#             if table_exists(cursor, table_name):
#                 last_value = get_last_incremental_value(
#                     cursor, table_name, incremental_column
#                 )
#                 df = filter_incremental(df, incremental_column, last_value)

#                 if df.shape[0] == 0:
#                     print("No new rows found — skipping insert")
#                     conn.close()
#                     log_pipeline_metrics(
#                         pipeline_id    = pipeline_id or f"pipeline_{table_name}",
#                         table_name     = table_name,
#                         rows_inserted  = 0,
#                         rows_skipped   = 0,
#                         duration_sec   = time.time() - start_time,
#                         connector_type = connector_type,
#                         file_name      = file_name,
#                         option         = option,
#                         status         = "SKIPPED"
#                     )
#                     return
#             else:
#                 print("Table not found for incremental load — full load will be performed")
#         # ────────────────────────────────────────────────

#         # ── OPTION 1 — APPEND ────────────────────────────
        
#         if option == "1":
#             if not table_exists(cursor, table_name):
#                 create_table(cursor, df, table_name)
#             else:
#                 report    = check_schema_mismatch(cursor, df, table_name)
#                 match_pct = report["match_pct"]

#                 # ── THRESHOLD 1: 0% match — hard stop ──────────────
#                 if match_pct == 0:
#                     raise ValueError(
#                         f"0% column match — Seems like a different file. "
#                         f"DB columns: {report['matched']} | "
#                         f"File columns: {list(df.columns)}"
#                     )

#                 # ── THRESHOLD 2: < 50% match — warn but allow ──────
#                 if match_pct < 50:
#                     print(
#                         f"WARNING: Only {match_pct}% columns match . "
#                         f"Missing: {report['missing_in_file']} | "
#                         f"Extra: {report['extra_in_file']}"
#                     )
#                     #If the user explicitly wants to proceed even with a low match,
#                     #then still continue the process — but clearly log a warning message.

#                 # ── THRESHOLD 3: New columns add Only 80%+ match ──
#                 if match_pct >= 80:
#                     # High confidence — add new columns automatically
#                     evolved_cols = evolve_schema(cursor, df, table_name)
#                     if evolved_cols:
#                         print(f"Schema evolved ({match_pct}% match): {evolved_cols}")

#                 elif 50 <= match_pct < 80:
#                     # Medium confidence — add new columns but log a caution
#                     evolved_cols = evolve_schema(cursor, df, table_name)
#                     print(
#                         f"CAUTION: Schema evolved at only {match_pct}% match. "
#                         f"New columns added: {evolved_cols}. "
#                         f"Verify the file."
#                     )

#                 else:
#                     # < 50% match — Not add new columns, just insert matching columns with a warning, because it's likely a wrong file or bad mapping.
#                     evolved_cols = []
#                     print(
#                         f"Schema evolution SKIPPED: {match_pct}% match too low. "
#                         f"Only matching columns will be inserted."
#                     )
#                     # Trim df to only matched columns, to avoid inserting wrong data into the table. This is a safety measure when the match percentage is low, indicating a potential mismatch between the file and the table schema. By only inserting the matched columns, we can minimize the risk of corrupting the existing data with incorrect or unexpected columns from the file.
#                     matched_cols = list(report["matched"])
#                     if isinstance(df, pl.DataFrame):
#                         df = df.select(matched_cols)
#                     else:
#                         df = df[matched_cols]

#             insert_data(cursor, df, table_name)

#         # if option == "1":
#         #     if not table_exists(cursor, table_name):
#         #         create_table(cursor, df, table_name)
#         #     else:
#         #         report    = check_schema_mismatch(cursor, df, table_name)
#         #         match_pct = report["match_pct"]
#         #         if report["match_pct"] == 0:
#         #             raise ValueError("0% column match — verify karo.")
#         #         evolved_cols = evolve_schema(cursor, df, table_name)
#         #     insert_data(cursor, df, table_name)

#         # ── OPTION 2 — OVERWRITE ─────────────────────────
#         elif option == "2":
#             if sync_mode == "incremental":
#                 raise ValueError(
#                     "option=2 (overwrite) not with incremental. "
#                     "option=1 use karo."
#                 )
#             if table_exists(cursor, table_name):
#                 cursor.execute(
#                     sql.SQL("DROP TABLE {t}").format(t=sql.Identifier(table_name))
#                 )
#             create_table(cursor, df, table_name)
#             insert_data(cursor, df, table_name)

#         # ── OPTION 3 — CREATE ONLY ───────────────────────
#         elif option == "3":
#             if table_exists(cursor, table_name):
#                 raise ValueError(f"Table '{table_name}' already exists.")
#             create_table(cursor, df, table_name)
#             insert_data(cursor, df, table_name)

#         else:
#             raise ValueError(f"Invalid option '{option}'")

#         conn.commit()
#         duration = time.time() - start_time
#         print(f"Committed — {df.shape[0]} rows | {duration:.2f}s")

#         log_pipeline_metrics(
#             pipeline_id    = pipeline_id or f"pipeline_{table_name}",
#             table_name     = table_name,
#             rows_inserted  = df.shape[0],
#             duration_sec   = duration,
#             evolved_columns= evolved_cols,
#             match_pct      = match_pct,
#             file_name      = file_name,
#             connector_type = connector_type,
#             option         = option,
#             status         = "SUCCESS"
#         )
#         print("\nPipeline completed successfully!")

#     except Exception as e:
#         conn.rollback()
#         duration = time.time() - start_time
#         print(f"ROLLBACK: {e}")
#         log_pipeline_metrics(
#             pipeline_id    = pipeline_id or f"pipeline_{table_name}",
#             table_name     = table_name,
#             rows_inserted  = 0,
#             duration_sec   = duration,
#             connector_type = connector_type,
#             file_name      = file_name,
#             option         = option,
#             status         = "FAILED",
#             error_message  = str(e)
#         )
#         raise

#     finally:
#         cursor.close()
#         conn.close()



import psycopg2
import re
import polars as pl
import pandas as pd
import numpy as np
from psycopg2 import sql
import time
from psycopg2.extras import execute_values
import os
from pathlib import Path
from dotenv import load_dotenv
import json
project_root = Path(__file__).parent.parent.parent
load_dotenv(project_root / ".env")

DB_CONFIG = {
    "host":     os.getenv("DB_HOST",     "postgres"),
    "database": os.getenv("DB_NAME",     "airflow"),
    "user":     os.getenv("DB_USER",     "airflow"),
    "password": os.getenv("DB_PASSWORD", "airflow"),
    "port":     os.getenv("DB_PORT",     "5432"),
}

# ─────────────────────────────────────────────
# CLEAN COLUMN NAMES
# ─────────────────────────────────────────────

def clean_column(name):
    name = str(name).lower().strip()
    name = re.sub(r"[^\w]+", "_", name)
    name = re.sub(r"^_+|_+$", "", name)
    if re.match(r"^\d", name):
        name = f"col_{name}"
    return name or "unnamed"

# ─────────────────────────────────────────────
# GET SCHEMA
# ─────────────────────────────────────────────

def get_schema(df) -> dict:
    if isinstance(df, pl.DataFrame):
        return {col: str(dtype) for col, dtype in df.schema.items()}
    elif isinstance(df, pd.DataFrame):
        return {col: str(dtype) for col, dtype in df.dtypes.items()}
    else:
        raise TypeError(f"Unsupported DataFrame type: {type(df)}")


# ─────────────────────────────────────────────
# DTYPE → PostgreSQL TYPE MAPPING
# ─────────────────────────────────────────────

def dtype_to_sql(dtype: str) -> str:
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

# ─────────────────────────────────────────────
# GET ALL TABLES
# ─────────────────────────────────────────────

def get_all_tables(cursor):
    cursor.execute("""
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema = 'public'
    """)
    return [t[0] for t in cursor.fetchall()]


# ─────────────────────────────────────────────
# GET TABLE COLUMNS
# ─────────────────────────────────────────────

def get_table_columns(cursor, table_name):
    cursor.execute("""
        SELECT column_name
        FROM information_schema.columns
        WHERE table_name = %s
        ORDER BY ordinal_position
    """, (table_name,))
    return [r[0] for r in cursor.fetchall()]



# ─────────────────────────────────────────────
# TABLE EXISTS CHECK
# ─────────────────────────────────────────────

def table_exists(cursor, table_name):
    cursor.execute("""
        SELECT EXISTS (
            SELECT FROM information_schema.tables
            WHERE table_name = %s
        );
    """, (table_name,))
    return cursor.fetchone()[0]



# ─────────────────────────────────────────────
# CREATE TABLE
# ─────────────────────────────────────────────

def create_table(cursor, df, table_name, custom_schema_sql=None):
    """custom_schema_sql: optional {cleaned_col_name: SQL_TYPE} — when a
    column is listed here, its user-requested SQL type wins over the
    auto-detected dtype. See utils/schema_applier.py."""
    schema = get_schema(df)
    custom_schema_sql = custom_schema_sql or {}

    col_definitions = []
    for col, dtype in schema.items():
        sql_type = custom_schema_sql.get(col) or dtype_to_sql(dtype)
        # with sql.SQL and sql.Identifier, column names and table names are safely quoted to prevent SQL injection and handle special characters. For example, a column named "user name" will be quoted as "user name" in the SQL query, ensuring it is treated as a single identifier.
        col_definitions.append(
            sql.SQL("{} {}").format(
                sql.Identifier(col),
                sql.SQL(sql_type)
            )
        )

    create_query = sql.SQL("""
        CREATE TABLE IF NOT EXISTS {table} (
            {cols}
        )
    """).format(
        table = sql.Identifier(table_name),
        cols  = sql.SQL(", ").join(col_definitions)
    )
    try:
        cursor.execute(create_query)
        print(f"Table '{table_name}' created successfully")
    except Exception as e:
        # Concurrent CREATE TABLE IF NOT EXISTS calls can race on Postgres's
        # internal pg_type catalog even though IF NOT EXISTS is used — if
        # that's what happened, the table now exists (created by the other
        # transaction), so just continue instead of failing the whole run.
        if "pg_type_typname_nsp_index" in str(e):
            print(f"Table '{table_name}' was created concurrently by another process — continuing.")
            return
        print(f"Table create failed: {e}")
        raise



# ─────────────────────────────────────────────
# RETROACTIVE TYPE ALTER FOR EXISTING TABLES
# ─────────────────────────────────────────────
# create_table() / evolve_schema() only apply a custom_schema type to a
# BRAND-NEW table or a BRAND-NEW column — a column that already existed
# before custom_schema was set (or was created on an earlier run without
# one) keeps its old Postgres type forever otherwise. This is what makes
# an existing "Append" target look like custom_schema "isn't working":
# the data gets cast correctly in Python, but then lands in a column
# that's still TEXT, so it reads back as text again.
#
# Canonical type -> a Postgres expression that casts a TEXT column value
# safely: if a given row's value doesn't actually match the target type,
# it becomes NULL instead of aborting the whole ALTER TABLE (Postgres has
# no TRY_CAST, and a plain `col::type` fails the entire statement the
# moment ONE existing row doesn't fit).
_SQL_TO_CANONICAL = {
    "BIGINT":           "integer",
    "DOUBLE PRECISION": "float",
    "BOOLEAN":          "boolean",
    "DATE":             "date",
    "TIMESTAMP":        "timestamp",
    "JSONB":            "json",
    "TEXT":             "text",
}


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
        # No safe generic date-format matcher in plain SQL — only convert
        # values that already look ISO-ish (YYYY-MM-DD...), everything
        # else becomes NULL rather than blowing up the ALTER.
        return f"CASE WHEN {c} ~ '^\\d{{4}}-\\d{{2}}-\\d{{2}}' THEN {c}::{target} ELSE NULL END"
    if canonical_type == "json":
        return f"CASE WHEN {c} IS NOT NULL THEN to_jsonb({c}) ELSE NULL END"
    return c  # text — a plain ::text cast always succeeds


def alter_existing_columns_to_custom_schema(cursor, table_name, custom_schema_sql):
    """For a table that ALREADY EXISTS, retroactively ALTER any of its
    existing columns that are listed in custom_schema_sql but whose live
    Postgres type doesn't match yet. Each column is altered in its own
    SAVEPOINT — if one column's existing data genuinely can't be
    represented in the new type (extremely rare given the permissive
    safe-cast above, but possible), that column is skipped with a warning
    instead of failing the whole ingest.

    Returns (altered: [col, ...], warnings: [str, ...]).
    """
    if not custom_schema_sql:
        return [], []

    cursor.execute("""
        SELECT column_name, data_type
        FROM information_schema.columns
        WHERE table_name = %s AND table_schema = 'public'
    """, (table_name,))
    current_types = {row[0]: row[1] for row in cursor.fetchall()}

    altered, warnings = [], []
    for col, desired_sql_type in custom_schema_sql.items():
        if col not in current_types:
            continue  # brand-new column — evolve_schema() handles that case

        canonical = _SQL_TO_CANONICAL.get(desired_sql_type, "text")
        using_expr = _safe_cast_sql(sql.Identifier(col).as_string(cursor.connection), canonical)

        cursor.execute("SAVEPOINT custom_schema_alter")
        try:
            alter_query = sql.SQL(
                'ALTER TABLE {table} ALTER COLUMN {col} TYPE {sql_type} USING {using_expr}'
            ).format(
                table      = sql.Identifier(table_name),
                col        = sql.Identifier(col),
                sql_type   = sql.SQL(desired_sql_type),
                using_expr = sql.SQL(using_expr),
            )
            cursor.execute(alter_query)
            cursor.execute("RELEASE SAVEPOINT custom_schema_alter")
            altered.append(col)
        except Exception as e:
            cursor.execute("ROLLBACK TO SAVEPOINT custom_schema_alter")
            warnings.append(f"Could not change existing column '{col}' to {desired_sql_type}: {e}")

    if altered:
        print(f"Custom schema — existing columns retyped: {altered}")
    for w in warnings:
        print(f"Custom schema — {w}")

    return altered, warnings



# ─────────────────────────────────────────────
# CHECK SCHEMA MISMATCH
# ─────────────────────────────────────────────
def check_schema_mismatch(cursor, df, table_name):
    cursor.execute("""
        SELECT column_name
        FROM information_schema.columns
        WHERE table_name = %s AND table_schema = 'public'
    """, (table_name,))
    existing_cols = set(row[0] for row in cursor.fetchall())
    incoming_cols = set(df.columns)

    missing_in_file = existing_cols - incoming_cols
    extra_in_file   = incoming_cols - existing_cols
    matched         = existing_cols & incoming_cols

    match_pct = round(len(matched) / len(existing_cols) * 100, 2) if existing_cols else 100.0

    print(f"Matched   : {sorted(matched)}")
    print(f"Missing   : {sorted(missing_in_file)}  → NULL will be inserted")
    print(f"Extra     : {sorted(extra_in_file)}  → new columns will be added")
    print(f"Match %   : {match_pct}%")

    if match_pct < 80:
        print(f"WARNING: Only {match_pct}% columns match — filling many NULLs and adding many new columns may indicate a wrong file or bad mapping. Please verify.")

    return {
        "matched":         sorted(matched),
        "missing_in_file": sorted(missing_in_file),
        "extra_in_file":   sorted(extra_in_file),
        "match_pct":       match_pct
    }

# ─────────────────────────────────────────────
# INSERT DATA
# ─────────────────────────────────────────────
import json   # ← top pe already ho sakta hai, confirm karo import hai

def insert_data(cursor, df, table_name, batch_size=1000, custom_schema_sql=None):
    """custom_schema_sql: optional {cleaned_col_name: SQL_TYPE} — the SAME
    mapping passed to create_table()/evolve_schema()/the retroactive ALTER.
    Used here as a final, last-mile guard: right before each value is sent
    to Postgres, double-check it actually matches the type Postgres expects
    for that column. Every earlier step (apply_custom_schema in
    utils/schema_applier.py, the retroactive ALTER) already tries to
    guarantee this, but if anything upstream ever slips through, THIS is
    what stops an "invalid input syntax for type X" crash — the offending
    value becomes NULL (with a clear log line naming the row/column/value)
    instead of failing the whole batch."""
    if isinstance(df, pl.DataFrame):
        pdf = df.to_pandas()
    else:
        pdf = df

    cols_sql = sql.SQL(", ").join(
        sql.Identifier(c) for c in pdf.columns
    )
    insert_query = sql.SQL(
        "INSERT INTO {table} ({cols}) VALUES %s"
    ).format(
        table = sql.Identifier(table_name),
        cols  = cols_sql
    )

    def _sanitize_value(v):
        if v is None:
            return None
        # Lists / numpy arrays / dicts aren't scalars, so they're handled
        # before the pd.isna() check below — pd.isna() on an array returns
        # an array, not a single bool, so it can't be used in a plain `if`.
        if isinstance(v, (np.ndarray, list, dict)):
            try:
                return json.dumps(v.tolist() if isinstance(v, np.ndarray) else v, default=str)
            except (TypeError, ValueError):
                return str(v)
        # pd.isna() catches every "missing" scalar in one shot — plain float
        # NaN, pandas NaT (a missing date/timestamp), and pd.NA — whereas the
        # old `isinstance(v, float) and np.isnan(v)` check only caught NaN.
        # NaT isn't a float, so it slipped through, got stringified to "NaT"
        # by the driver, and Postgres rejected it with "invalid input syntax
        # for type timestamp: NaT". This is what caused run 287 to fail.
        if pd.isna(v):
            return None
        if isinstance(v, np.bool_):
            return bool(v)
        if isinstance(v, (np.integer, np.floating)):
            return v.item()
        # Normalize pandas Timestamps to plain python datetimes so psycopg2's
        # standard datetime adapter handles them, rather than relying on
        # pandas-specific behavior.
        if isinstance(v, pd.Timestamp):
            return v.to_pydatetime()
        return v

    # ── Final-mile custom-schema guard ──────────────────────────────────
    import datetime as _dt
    _governed = {}  # column position -> canonical type, only for custom_schema columns
    if custom_schema_sql:
        col_positions = {c: i for i, c in enumerate(pdf.columns)}
        for col, desired_sql_type in custom_schema_sql.items():
            if col in col_positions:
                _governed[col_positions[col]] = (col, _SQL_TO_CANONICAL.get(desired_sql_type, "text"))

    def _guard(pos, value, row_idx):
        if pos not in _governed or value is None:
            return value
        col, canonical = _governed[pos]
        ok = (
            (canonical == "integer" and isinstance(value, int) and not isinstance(value, bool))
            or (canonical == "float" and isinstance(value, (int, float)) and not isinstance(value, bool))
            or (canonical == "boolean" and isinstance(value, bool))
            or (canonical in ("date", "timestamp") and isinstance(value, (_dt.date, _dt.datetime)))
            or (canonical in ("text", "json"))  # any scalar is fine as text/json — psycopg2 stringifies
        )
        if ok:
            return value
        print(
            f"custom_schema guard: row {row_idx}, column '{col}' expected '{canonical}' "
            f"but got {value!r} ({type(value).__name__}) — inserting NULL instead."
        )
        return None

    rows = [
        tuple(_guard(pos, _sanitize_value(v), row_idx) for pos, v in enumerate(row))
        for row_idx, row in enumerate(pdf.itertuples(index=False, name=None))
    ]

    for i in range(0, len(rows), batch_size):
        batch = rows[i : i + batch_size]
        execute_values(cursor, insert_query, batch, page_size=batch_size)
        print(f"Inserted rows {i+1} to {min(i+batch_size, len(rows))}")

    print(f"{len(rows)} rows inserted into '{table_name}'")

# ─────────────────────────────────────────────
# Schema evolution 
# (for option=1 append, if new columns detected then alter table to add them before insert)
# ────────────────────────────────────────────
def evolve_schema(cursor, df, table_name, custom_schema_sql=None):
    """custom_schema_sql: optional {cleaned_col_name: SQL_TYPE} — new columns
    listed here get added with the user-requested SQL type instead of the
    auto-detected one. See utils/schema_applier.py."""
    cursor.execute("""
        SELECT column_name
        FROM information_schema.columns
        WHERE table_name = %s AND table_schema = 'public'
    """, (table_name,))
    existing_cols   = {row[0] for row in cursor.fetchall()}
    incoming_schema = get_schema(df)
    custom_schema_sql = custom_schema_sql or {}

    added = []
    for col, dtype in incoming_schema.items():
        if col not in existing_cols:
            sql_type = custom_schema_sql.get(col) or dtype_to_sql(dtype)
            # ALTER TABLE bhi safely banao
            alter_query = sql.SQL(
                "ALTER TABLE {table} ADD COLUMN {col} {type}"
            ).format(
                table = sql.Identifier(table_name),
                col   = sql.Identifier(col),
                type  = sql.SQL(sql_type)
            )
            cursor.execute(alter_query)
            added.append(col)
            print(f"New column added: '{col}' ({sql_type})")

    if added:
        print(f"Schema evolved — {len(added)} column(s) added: {added}")
    else:
        print("Schema unchanged.")

    return added

# ────────────────────────────────────────────  
# Observability: Log pipeline metrics to a separate table
# ────────────────────────────────────────────
def log_pipeline_metrics(
                        pipeline_id,
                        table_name,
                        rows_inserted=0,
                        rows_skipped=0,
                        rows_failed=0,
                        duration_sec=0.0,
                        evolved_columns=None,
                        match_pct=100.0,
                        file_name=None,
                        connector_type=None,
                        option=None,
                        status="SUCCESS",
                        error_message=None
                    ):
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO pipeline_metrics (
                pipeline_id, table_name, rows_inserted, rows_skipped,
                rows_failed, duration_sec, evolved_columns, match_pct,
                file_name, connector_type, option, status, error_message
            ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """, (
            pipeline_id,
            table_name,
            rows_inserted,
            rows_skipped,
            rows_failed,
            round(duration_sec, 2),
            evolved_columns or [],
            match_pct,
            file_name,
            connector_type,
            option,
            status,
            error_message
        ))
        conn.commit()
        cursor.close()
        conn.close()
        print(f"Metrics logged — {rows_inserted} rows | {duration_sec:.2f}s | {status}")
    except Exception as e:
        print(f"Metrics log failed: {e}")  # if metrics logging will fail, it should not break the main pipeline


# ─────────────────────────────────────────────
# VALIDATE TABLE NAME
# ─────────────────────────────────────────────
def validate_table_name(table_name: str):
    """
    Only allow alphanumeric and underscore.
    Reject any special character.
    """
    if not table_name:
        raise ValueError("table_name will be required for all connector types in future, so please provide a valid table_name in your config. It should contain only letters, numbers, and underscores, and must start with a letter or underscore.")

    if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', table_name):
        raise ValueError(
            f"Invalid table_name '{table_name}' — "
            f"only letters, numbers, and underscores are allowed"
        )

    if len(table_name) > 63:   # PostgreSQL limit
        raise ValueError(f"table_name cannot be longer than 63 characters")
    
# ─────────────────────────────────────────────
# incremental load support (for future enhancement, not implemented in current version)
# ─────────────────────────────────────────────

# ─────────────────────────────────────────────
# GET LAST INCREMENTAL VALUE
# ─────────────────────────────────────────────

def get_last_incremental_value(cursor, table_name: str, incremental_column: str):
    """
    Fetch the MAX value of the incremental_column from the target table.
    This will be used as the last sync point for incremental loading.
    """
    try:
        query = sql.SQL(
            "SELECT MAX({col}) FROM {table}"
        ).format(
            col   = sql.Identifier(incremental_column),
            table = sql.Identifier(table_name)
        )
        cursor.execute(query)
        result = cursor.fetchone()[0]
        print(f"Last incremental value — {incremental_column}: {result}")
        return result
    except Exception as e:
        print(f"Could not fetch last value: {e}")
        return None


# ─────────────────────────────────────────────
# FILTER DATAFRAME — INCREMENTAL
# ─────────────────────────────────────────────

def filter_incremental(df, incremental_column: str, last_value):
    """
    Only contain new rows in the DataFrame — 
    where incremental_column > last_value
    """
    if last_value is None:
        print("No last value found — full load will be performed")
        return df

    if isinstance(df, pl.DataFrame):
        original_count = df.shape[0]
        df = df.filter(pl.col(incremental_column) > last_value)
        print(f"Incremental filter — {original_count} → {df.shape[0]} rows (new only)")

    elif isinstance(df, pd.DataFrame):
        original_count = df.shape[0]
        df = df[df[incremental_column] > last_value]
        print(f"Incremental filter — {original_count} → {df.shape[0]} rows (new only)")

    return df

# ─────────────────────────────────────────────
# MAIN LOAD FUNCTION
# ─────────────────────────────────────────────
def load_to_db(df, option=None, table_name=None,
               pipeline_id=None, connector_type=None, file_name=None,
               sync_mode="full", incremental_column=None,
               custom_schema_sql=None):   # ← {cleaned_col: SQL_TYPE}, see utils/schema_applier.py

    validate_table_name(table_name)

    conn   = psycopg2.connect(**DB_CONFIG)
    cursor = conn.cursor()

    if isinstance(df, pl.DataFrame):
        df = df.rename({col: clean_column(col) for col in df.columns})
    else:
        df.columns = [clean_column(c) for c in df.columns]

    print(f"Columns: {list(df.columns)}")
    print(f"Sync mode: {sync_mode}")

    evolved_cols = []
    match_pct    = 100.0
    start_time   = time.time()

    try:
        conn.autocommit = False

        # ── INCREMENTAL FILTER ───────────────────────────
        if sync_mode == "incremental" and incremental_column:

            # column existing in df?
            if incremental_column not in df.columns:
                raise ValueError(
                    f"incremental_column '{incremental_column}' "
                    f"not found in data. Available: {list(df.columns)}"
                )

            if table_exists(cursor, table_name):
                last_value = get_last_incremental_value(
                    cursor, table_name, incremental_column
                )
                df = filter_incremental(df, incremental_column, last_value)

                if df.shape[0] == 0:
                    print("No new rows found — skipping insert")
                    conn.close()
                    log_pipeline_metrics(
                        pipeline_id    = pipeline_id or f"pipeline_{table_name}",
                        table_name     = table_name,
                        rows_inserted  = 0,
                        rows_skipped   = 0,
                        duration_sec   = time.time() - start_time,
                        connector_type = connector_type,
                        file_name      = file_name,
                        option         = option,
                        status         = "SKIPPED"
                    )
                    return
            else:
                print("Table not found for incremental load — full load will be performed")
        # ────────────────────────────────────────────────

        # ── OPTION 1 — APPEND ────────────────────────────
        
        if option == "1":
            if not table_exists(cursor, table_name):
                create_table(cursor, df, table_name, custom_schema_sql=custom_schema_sql)
            else:
                # Table already existed BEFORE this custom_schema was set (or
                # from a run without one) — retroactively retype any of its
                # existing columns that custom_schema asks for, since
                # create_table()/evolve_schema() only apply the requested
                # type to brand-new tables/columns, not ones that already
                # exist. Without this, data still casts fine in Python but
                # lands back in an old TEXT column and reads as text again.
                if custom_schema_sql:
                    alter_existing_columns_to_custom_schema(cursor, table_name, custom_schema_sql)

                report    = check_schema_mismatch(cursor, df, table_name)
                match_pct = report["match_pct"]

                # ── THRESHOLD 1: 0% match — hard stop ──────────────
                if match_pct == 0:
                    raise ValueError(
                        f"0% column match — Seems like a different file. "
                        f"DB columns: {report['matched']} | "
                        f"File columns: {list(df.columns)}"
                    )

                # ── THRESHOLD 2: < 50% match — warn but allow ──────
                if match_pct < 50:
                    print(
                        f"WARNING: Only {match_pct}% columns match . "
                        f"Missing: {report['missing_in_file']} | "
                        f"Extra: {report['extra_in_file']}"
                    )
                    #If the user explicitly wants to proceed even with a low match,
                    #then still continue the process — but clearly log a warning message.

                # ── THRESHOLD 3: New columns add Only 80%+ match ──
                if match_pct >= 80:
                    # High confidence — add new columns automatically
                    evolved_cols = evolve_schema(cursor, df, table_name, custom_schema_sql=custom_schema_sql)
                    if evolved_cols:
                        print(f"Schema evolved ({match_pct}% match): {evolved_cols}")

                elif 50 <= match_pct < 80:
                    # Medium confidence — add new columns but log a caution
                    evolved_cols = evolve_schema(cursor, df, table_name, custom_schema_sql=custom_schema_sql)
                    print(
                        f"CAUTION: Schema evolved at only {match_pct}% match. "
                        f"New columns added: {evolved_cols}. "
                        f"Verify the file."
                    )

                else:
                    # < 50% match — Not add new columns, just insert matching columns with a warning, because it's likely a wrong file or bad mapping.
                    evolved_cols = []
                    print(
                        f"Schema evolution SKIPPED: {match_pct}% match too low. "
                        f"Only matching columns will be inserted."
                    )
                    # Trim df to only matched columns, to avoid inserting wrong data into the table. This is a safety measure when the match percentage is low, indicating a potential mismatch between the file and the table schema. By only inserting the matched columns, we can minimize the risk of corrupting the existing data with incorrect or unexpected columns from the file.
                    matched_cols = list(report["matched"])
                    if isinstance(df, pl.DataFrame):
                        df = df.select(matched_cols)
                    else:
                        df = df[matched_cols]

            insert_data(cursor, df, table_name, custom_schema_sql=custom_schema_sql)

        # if option == "1":
        #     if not table_exists(cursor, table_name):
        #         create_table(cursor, df, table_name)
        #     else:
        #         report    = check_schema_mismatch(cursor, df, table_name)
        #         match_pct = report["match_pct"]
        #         if report["match_pct"] == 0:
        #             raise ValueError("0% column match — verify karo.")
        #         evolved_cols = evolve_schema(cursor, df, table_name)
        #     insert_data(cursor, df, table_name)

        # ── OPTION 2 — OVERWRITE ─────────────────────────
        elif option == "2":
            if sync_mode == "incremental":
                raise ValueError(
                    "option=2 (overwrite) not with incremental. "
                    "option=1 use karo."
                )
            if table_exists(cursor, table_name):
                cursor.execute(
                    sql.SQL("DROP TABLE {t}").format(t=sql.Identifier(table_name))
                )
            create_table(cursor, df, table_name, custom_schema_sql=custom_schema_sql)
            insert_data(cursor, df, table_name, custom_schema_sql=custom_schema_sql)

        # ── OPTION 3 — CREATE ONLY ───────────────────────
        elif option == "3":
            if table_exists(cursor, table_name):
                raise ValueError(f"Table '{table_name}' already exists.")
            create_table(cursor, df, table_name, custom_schema_sql=custom_schema_sql)
            insert_data(cursor, df, table_name, custom_schema_sql=custom_schema_sql)

        else:
            raise ValueError(f"Invalid option '{option}'")

        conn.commit()
        duration = time.time() - start_time
        print(f"Committed — {df.shape[0]} rows | {duration:.2f}s")

        log_pipeline_metrics(
            pipeline_id    = pipeline_id or f"pipeline_{table_name}",
            table_name     = table_name,
            rows_inserted  = df.shape[0],
            duration_sec   = duration,
            evolved_columns= evolved_cols,
            match_pct      = match_pct,
            file_name      = file_name,
            connector_type = connector_type,
            option         = option,
            status         = "SUCCESS"
        )

        # ── Lineage capture — one hook point covers every connector ──────
        # (csv, salesforce, hubspot, zoho, ...) since they all funnel
        # through this same load_to_db() success path.
        try:
            from lineage.router import record_lineage
            record_lineage(
                connector_type = connector_type,
                source_name    = file_name,
                table_name     = table_name,
                pipeline_id    = pipeline_id or f"pipeline_{table_name}",
                columns        = list(df.columns),
                rows_loaded    = df.shape[0],
                status         = "SUCCESS",
            )
        except Exception as lineage_err:
            print(f"[lineage] skipped for this run (non-fatal): {lineage_err}")

        print("\nPipeline completed successfully!")

    except Exception as e:
        conn.rollback()
        duration = time.time() - start_time
        print(f"ROLLBACK: {e}")
        log_pipeline_metrics(
            pipeline_id    = pipeline_id or f"pipeline_{table_name}",
            table_name     = table_name,
            rows_inserted  = 0,
            duration_sec   = duration,
            connector_type = connector_type,
            file_name      = file_name,
            option         = option,
            status         = "FAILED",
            error_message  = str(e)
        )

        try:
            from lineage.router import record_lineage
            record_lineage(
                connector_type = connector_type,
                source_name    = file_name,
                table_name     = table_name,
                pipeline_id    = pipeline_id or f"pipeline_{table_name}",
                columns        = None,
                rows_loaded    = 0,
                status         = "FAILED",
            )
        except Exception as lineage_err:
            print(f"[lineage] skipped for this run (non-fatal): {lineage_err}")

        raise

    finally:
        cursor.close()
        conn.close()