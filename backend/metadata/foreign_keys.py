# import sys
# import os

# sys.path.append(
#     os.path.dirname(
#         os.path.dirname(os.path.abspath(__file__))
#     )
# )
# import pandas as pd
# from extractor import get_connection


# def get_foreign_keys():

#     conn = get_connection()

#     query = """
#     SELECT
#         kcu.table_name,
#         kcu.column_name,
#         ccu.table_name AS referenced_table,
#         ccu.column_name AS referenced_column
#     FROM information_schema.referential_constraints rc
#     JOIN information_schema.key_column_usage kcu
#       ON rc.constraint_name = kcu.constraint_name
#     JOIN information_schema.constraint_column_usage ccu
#       ON rc.unique_constraint_name = ccu.constraint_name
#     """

#     df = pd.read_sql(query, conn)

#     conn.close()

#     return df

# if __name__ == "__main__":
#     print(get_foreign_keys())

import sys
import os

sys.path.append(
    os.path.dirname(
        os.path.dirname(os.path.abspath(__file__))
    )
)

import pandas as pd
from metadata.extractor import get_connection


def get_foreign_keys():

    conn = get_connection()
    cursor = conn.cursor()

    # SHOW IMPORTED KEYS is the most reliable way in Snowflake
    # cursor.description gives us the real column names dynamically
    cursor.execute("SHOW IMPORTED KEYS IN SCHEMA")
    rows = cursor.fetchall()
    col_names = [desc[0] for desc in cursor.description]

    df = pd.DataFrame(rows, columns=col_names)

    cursor.close()
    conn.close()

    # Rename to consistent output columns
    df = df.rename(columns={
        "fk_table_name":  "TABLE_NAME",
        "fk_column_name": "COLUMN_NAME",
        "pk_table_name":  "REFERENCED_TABLE",
        "pk_column_name": "REFERENCED_COLUMN"
    })[["TABLE_NAME", "COLUMN_NAME", "REFERENCED_TABLE", "REFERENCED_COLUMN"]]

    return df


if __name__ == "__main__":
    df = get_foreign_keys()
    print(df)
    print(f"\nTotal FKs found: {len(df)}")