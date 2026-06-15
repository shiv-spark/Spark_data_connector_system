
import sys
import os

sys.path.append(
    os.path.dirname(
        os.path.dirname(os.path.abspath(__file__))
    )
)

from metadata.extractor import get_connection, extract_schema_metadata


def get_sample_values(table_name, column_name, limit=5):

    conn = get_connection()
    cursor = conn.cursor()

    query = f"""
    SELECT DISTINCT {column_name}
    FROM {table_name}
    LIMIT {limit}
    """

    cursor.execute(query)
    rows = cursor.fetchall()
    values = [row[0] for row in rows]

    cursor.close()
    conn.close()

    return values


if __name__ == "__main__":

    # Discover real tables and columns from schema, then sample the first one
    df = extract_schema_metadata()

    if df.empty:
        print("No tables found in schema.")
    else:
        first = df.iloc[0]
        table  = first["TABLE_NAME"]
        column = first["COLUMN_NAME"]

        print(f"Sampling: {table}.{column}")
        print(get_sample_values(table, column))
        print(df)