import sys
import os

sys.path.append(
    os.path.dirname(
        os.path.dirname(os.path.abspath(__file__))
    )
)

import pandas as pd
from metadata.extractor import get_connection


def load_to_snowflake(filepath: str, config: dict) -> int:
    """
    Loads a generated CSV file into the target Snowflake table.
    Uses Snowflake native PUT + COPY INTO — no SQLAlchemy needed.

    Strategy:
        1. PUT  — uploads the local CSV to the table's internal stage (@%TABLE)
        2. COPY INTO — loads it from stage into the actual table
        3. Cleans up the stage file after loading

    Args:
        filepath : full path to the CSV file produced by csv_writer.py
        config   : parsed config dict (needs 'table' and 'columns')

    Returns:
        Number of rows loaded
    """

    table   = config["table"].upper()
    columns = [c.upper() for c in config["columns"]]

    conn   = get_connection()
    cursor = conn.cursor()

    try:
        # Normalise path separators for Snowflake (must use forward slashes)
        normalised_path = filepath.replace("\\", "/")
         
        if ":" in normalised_path:
            cursor.execute(f"PUT 'file:///{normalised_path}' @%{table} OVERWRITE=TRUE AUTO_COMPRESS=FALSE")
        else:
            cursor.execute(f"PUT 'file://{normalised_path}' @%{table} OVERWRITE=TRUE AUTO_COMPRESS=FALSE")

        print(f"[loader] Uploading {filepath} → stage @%{table}")

        # Step 1: PUT — upload file to internal table stage
        cursor.execute(f"PUT 'file://{normalised_path}' @%{table} OVERWRITE=TRUE AUTO_COMPRESS=FALSE")
        put_result = cursor.fetchone()
        print(f"[loader] PUT result: {put_result}")

        # Step 2: COPY INTO — load from stage into table
        # Column list ensures CSV columns map to the right table columns
        col_list = ", ".join(columns)
        filename  = os.path.basename(filepath)

        copy_sql = f"""
        COPY INTO {table} ({col_list})
        FROM @%{table}/{filename}
        FILE_FORMAT = (
            TYPE            = 'CSV'
            FIELD_DELIMITER = ','
            SKIP_HEADER     = 1
            FIELD_OPTIONALLY_ENCLOSED_BY = '"'
            NULL_IF         = ('', 'NULL', 'null', 'None')
            EMPTY_FIELD_AS_NULL = TRUE
        )
        ON_ERROR = 'ABORT_STATEMENT'
        """

        print(f"[loader] Running COPY INTO {table}...")
        cursor.execute(copy_sql)
        copy_result = cursor.fetchone()
        print(f"[loader] COPY result: {copy_result}")

        # Step 3: Get actual loaded row count
        cursor.execute(f"SELECT COUNT(*) FROM {table}")
        total_rows = cursor.fetchone()[0]

        # Step 4: Remove file from stage to keep it clean
        cursor.execute(f"REMOVE @%{table}/{filename}")
        print(f"[loader] Stage cleaned up")

        print(f"[loader] Successfully loaded into '{table}'. Total rows in table: {total_rows}")
        return total_rows

    except Exception as e:
        print(f"[loader] ERROR: {e}")
        raise

    finally:
        cursor.close()
        conn.close()


def verify_load(table: str, expected_rows: int) -> bool:
    """
    Quick sanity check — queries the table and confirms
    at least `expected_rows` rows exist.
    """

    conn   = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute(f"SELECT COUNT(*) FROM {table.upper()}")
        actual = cursor.fetchone()[0]
        print(f"[loader] Verify: {table} has {actual} rows (expected >= {expected_rows})")
        return actual >= expected_rows
    finally:
        cursor.close()
        conn.close()


if __name__ == "__main__":
    # Smoke test — point at a real generated CSV
    import glob

    generated_dir = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "generated"
    )

    csvs = sorted(glob.glob(os.path.join(generated_dir, "*.csv")))

    if not csvs:
        print("No CSV files found in generator/generated/. Run pipeline.py first.")
    else:
        latest = csvs[-1]
        print(f"Loading most recent file: {latest}")

        # Infer table name from filename (users_20240101_120000.csv → USERS)
        table = os.path.basename(latest).split("_")[0].upper()

        # Read CSV to get column names
        df      = pd.read_csv(latest)
        columns = list(df.columns)

        config = {"table": table, "columns": columns}
        load_to_snowflake(latest, config)
        verify_load(table, expected_rows=len(df))