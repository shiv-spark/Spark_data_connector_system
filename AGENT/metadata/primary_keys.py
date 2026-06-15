
import sys
import os

sys.path.append(
    os.path.dirname(
        os.path.dirname(os.path.abspath(__file__))
    )
)

import pandas as pd
from metadata.extractor import get_connection


def get_primary_keys():

    conn = get_connection()
    cursor = conn.cursor()

    query = """
    SELECT
        c.table_name,
        c.column_name
    FROM information_schema.columns c
    JOIN information_schema.table_constraints tc
      ON  tc.table_name   = c.table_name
      AND tc.table_schema = c.table_schema
      AND tc.constraint_type = 'PRIMARY KEY'
    JOIN information_schema.constraint_column_usage ccu
      ON  ccu.constraint_name = tc.constraint_name
      AND ccu.column_name     = c.column_name
    WHERE c.table_schema = CURRENT_SCHEMA()
    ORDER BY c.table_name
    """

    try:
        cursor.execute(query)
        rows = cursor.fetchall()
        df = pd.DataFrame(rows, columns=["TABLE_NAME", "COLUMN_NAME"])
    except Exception:
        # Fallback: Snowflake SHOW PRIMARY KEYS is always available
        cursor.execute("SHOW PRIMARY KEYS IN SCHEMA")
        rows = cursor.fetchall()
        # SHOW PRIMARY KEYS columns: created_on, database_name, schema_name,
        # table_name, column_name, key_sequence, constraint_name, rely, comment
        df = pd.DataFrame(rows, columns=[
            "created_on", "database_name", "schema_name",
            "TABLE_NAME", "COLUMN_NAME", "key_sequence",
            "constraint_name", "rely", "comment"
        ])[["TABLE_NAME", "COLUMN_NAME"]]
    finally:
        cursor.close()
        conn.close()

    return df


if __name__ == "__main__":
    df = get_primary_keys()
    print(df)
    print(f"\nTotal PKs found: {len(df)}")