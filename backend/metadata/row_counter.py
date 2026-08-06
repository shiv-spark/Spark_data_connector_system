import sys
import os

sys.path.append(
    os.path.dirname(
        os.path.dirname(os.path.abspath(__file__))
    )
)
from metadata.extractor import get_connection


def get_row_counts():

    conn = get_connection()

    cursor = conn.cursor()

    cursor.execute("""
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema = CURRENT_SCHEMA()
    """)

    tables = cursor.fetchall()

    row_counts = {}

    for table in tables:

        table_name = table[0]

        cursor.execute(
            f"SELECT COUNT(*) FROM {table_name}"
        )

        count = cursor.fetchone()[0]

        row_counts[table_name] = count

    cursor.close()
    conn.close()

    return row_counts

if __name__ == "__main__":
    counts = get_row_counts()
    print(counts)