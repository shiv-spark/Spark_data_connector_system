import sys
import os

sys.path.append(
    os.path.dirname(
        os.path.dirname(os.path.abspath(__file__))
    )
)
import pandas as pd
import snowflake.connector

from config import SNOWFLAKE_CONFIG


def get_connection():
    return snowflake.connector.connect(
        user=SNOWFLAKE_CONFIG["user"],
        password=SNOWFLAKE_CONFIG["password"],
        account=SNOWFLAKE_CONFIG["account"],
        warehouse=SNOWFLAKE_CONFIG["warehouse"],
        database=SNOWFLAKE_CONFIG["database"],
        schema=SNOWFLAKE_CONFIG["schema"]
    )


def extract_schema_metadata():

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
    SELECT CURRENT_DATABASE(),
        CURRENT_SCHEMA()
    """)

    print(cursor.fetchone())

    query = """
        SELECT
            table_name,
            column_name,
            data_type,
            is_nullable
        FROM information_schema.columns
        WHERE table_schema = CURRENT_SCHEMA()
        ORDER BY table_name, ordinal_position
        """

    df = pd.read_sql(query, conn)

    conn.close()

    return df

if __name__ == "__main__":
    df = extract_schema_metadata()
    print(df)
    print(f"\nTotal Columns Found: {len(df)}")