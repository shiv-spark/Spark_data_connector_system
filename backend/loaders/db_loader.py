import psycopg2
import re
import polars as pl
import pandas as pd
import numpy as np
from psycopg2 import sql
import time
from psycopg2.extras import execute_values
import os
from dotenv import load_dotenv

load_dotenv()

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

def create_table(cursor, df, table_name):
    schema = get_schema(df)

    col_definitions = []
    for col, dtype in schema.items():
        sql_type   = dtype_to_sql(dtype)
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
        # ── Conflict detail print karo ───────────────
        print(f"Table create failed: {e}")
        raise



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


def insert_data(cursor, df, table_name, batch_size=1000):
    if isinstance(df, pl.DataFrame):
        pdf = df.to_pandas()
    else:
        pdf = df

    # Safely quoted columns or table
    cols_sql = sql.SQL(", ").join(
        sql.Identifier(c) for c in pdf.columns
    )
    insert_query = sql.SQL(
        "INSERT INTO {table} ({cols}) VALUES %s"
    ).format(
        table = sql.Identifier(table_name),
        cols  = cols_sql
    )

    # Prepare a list of rows for execute_values
    rows = [
        tuple(
            None if (v is None or (isinstance(v, float) and np.isnan(v)))
            else bool(v) if isinstance(v, np.bool_)
            else v.item() if isinstance(v, (np.integer, np.floating))
            else v
            for v in row
        )
        for row in pdf.itertuples(index=False, name=None)
    ]

    # Insert execute values in batches for better performance and memory efficiency
    for i in range(0, len(rows), batch_size):
        batch = rows[i : i + batch_size]
        execute_values(cursor, insert_query, batch, page_size=batch_size)
        print(f"Inserted rows {i+1} to {min(i+batch_size, len(rows))}")

    print(f"{len(rows)} rows inserted into '{table_name}'")


# ─────────────────────────────────────────────
# Schema evolution 
# (for option=1 append, if new columns detected then alter table to add them before insert)
# ────────────────────────────────────────────
def evolve_schema(cursor, df, table_name):
    cursor.execute("""
        SELECT column_name
        FROM information_schema.columns
        WHERE table_name = %s AND table_schema = 'public'
    """, (table_name,))
    existing_cols   = {row[0] for row in cursor.fetchall()}
    incoming_schema = get_schema(df)

    added = []
    for col, dtype in incoming_schema.items():
        if col not in existing_cols:
            sql_type = dtype_to_sql(dtype)
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
               sync_mode="full", incremental_column=None):   # ← new params

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
                create_table(cursor, df, table_name)
            else:
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
                    evolved_cols = evolve_schema(cursor, df, table_name)
                    if evolved_cols:
                        print(f"Schema evolved ({match_pct}% match): {evolved_cols}")

                elif 50 <= match_pct < 80:
                    # Medium confidence — add new columns but log a caution
                    evolved_cols = evolve_schema(cursor, df, table_name)
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

            insert_data(cursor, df, table_name)

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
            create_table(cursor, df, table_name)
            insert_data(cursor, df, table_name)

        # ── OPTION 3 — CREATE ONLY ───────────────────────
        elif option == "3":
            if table_exists(cursor, table_name):
                raise ValueError(f"Table '{table_name}' already exists.")
            create_table(cursor, df, table_name)
            insert_data(cursor, df, table_name)

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
        raise

    finally:
        cursor.close()
        conn.close()
