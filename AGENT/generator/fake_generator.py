# import sys
# import os

# sys.path.append(
#     os.path.dirname(
#         os.path.dirname(os.path.abspath(__file__))
#     )
# )

# import json
# import re
# import pandas as pd
# from faker import Faker
# from groq import Groq
# from dotenv import load_dotenv
# from generator.faker_mapper import build_faker_mapping

# load_dotenv()

# client = Groq(api_key=os.getenv("GROQ_API_KEY"))


# def _llm_generate_value(column: str, hint: str, locale: str, fake: Faker) -> any:
#     """
#     Asks the LLM to generate a single realistic value for a column
#     that is not covered by the base faker_mapper.
#     """
#     response = client.chat.completions.create(
#         model="llama-3.3-70b-versatile",
#         messages=[
#             {
#                 "role": "system",
#                 "content": (
#                     "Return ONLY a single realistic value as plain text. "
#                     "No explanation, no quotes, no punctuation around it."
#                 )
#             },
#             {
#                 "role": "user",
#                 "content": f"Generate a value for column '{column}' ({hint}). Locale: {locale}."
#             }
#         ],
#         temperature=0.7
#     )
#     return response.choices[0].message.content.strip()


# def generate_data(config: dict) -> pd.DataFrame:
#     """
#     Generates fake data based on parsed config.
#     Uses faker_mapper for known columns.
#     Falls back to LLM for unknown columns using hints.

#     Args:
#         config: dict with keys table, rows, locale, columns, hints

#     Returns:
#         pandas DataFrame with generated data
#     """

#     rows_count = config["rows"]
#     columns    = config["columns"]
#     locale     = config.get("locale", "en_IN")
#     hints      = config.get("hints", {})

#     fake    = Faker(locale)
#     mapping = build_faker_mapping(locale)

#     # Categorise columns upfront
#     mapped_cols  = []   # handled by faker_mapper
#     llm_cols     = []   # need LLM fallback
#     id_cols      = []   # sequential integer IDs

#     for col in columns:
#         col_lower = col.lower()
#         if col_lower in ("id", "user_id", "order_id", "customer_id", "employee_id"):
#             id_cols.append(col)
#         elif col_lower in mapping:
#             mapped_cols.append(col)
#         else:
#             llm_cols.append(col)

#     # Pre-generate LLM values in bulk (one call per unknown column, reused across rows)
#     # to avoid N × M API calls
#     llm_cache = {}
#     for col in llm_cols:
#         hint = hints.get(col, f"realistic value for {col}")
#         print(f"[fake_generator] LLM fallback for column '{col}': {hint}")
#         llm_cache[col] = [
#             _llm_generate_value(col, hint, locale, fake)
#             for _ in range(rows_count)
#         ]

#     data = []
#     for i in range(rows_count):
#         row = {}

#         # Sequential IDs
#         for col in id_cols:
#             row[col] = i + 1

#         # Faker-mapped columns
#         for col in mapped_cols:
#             row[col] = mapping[col.lower()]()

#         # LLM-generated columns
#         for col in llm_cols:
#             row[col] = llm_cache[col][i]

#         data.append(row)

#     # Return columns in the original requested order
#     df = pd.DataFrame(data, columns=columns)
#     return df


# if __name__ == "__main__":
#     config = {
#         "table":   "USERS",
#         "rows":    10,
#         "locale":  "en_IN",
#         "columns": ["user_id", "name", "email", "phone", "city"],
#         "hints": {
#             "user_id": "unique sequential integer",
#             "name":    "realistic Indian full name",
#             "email":   "lowercase email",
#             "phone":   "Indian mobile number",
#             "city":    "major Indian city"
#         }
#     }

#     df = generate_data(config)
#     print(df.head())
#     print(f"\nTotal rows: {len(df)}")


import sys
import os

sys.path.append(
    os.path.dirname(
        os.path.dirname(os.path.abspath(__file__))
    )
)

import pandas as pd
from faker import Faker
from metadata.catalog_builder import build_catalog
from generator.faker_mapper import build_dynamic_faker_mapping


ID_SUFFIXES = ("_id", "_no", "_num", "_seq", "_key")


def _is_id_column(col: str) -> bool:
    """Detects primary key / sequential ID columns by name pattern."""
    col_lower = col.lower()
    return col_lower in ("id",) or any(col_lower.endswith(s) for s in ID_SUFFIXES)


def generate_data(config: dict) -> pd.DataFrame:
    """
    Generates fake data using the LLM-powered dynamic Faker mapper.

    Flow:
        1. Separate ID columns (sequential integers) from data columns
        2. Build column specs (name + data_type + hint) from catalog + config hints
        3. Call LLM once to get Faker expressions for all data columns
        4. Generate rows using those callables
        5. Return as a pandas DataFrame

    Args:
        config: dict with keys — table, rows, locale, columns, hints

    Returns:
        pandas DataFrame with generated data
    """

    rows_count = config["rows"]
    columns    = config["columns"]
    locale     = config.get("locale", "en_IN")
    hints      = config.get("hints", {})
    table      = config["table"]

    # Pull data types from schema catalog
    catalog     = build_catalog()
    table_meta  = catalog.get(table, {}).get("columns", {})

    # Separate ID columns from data columns
    id_cols   = [c for c in columns if _is_id_column(c)]
    data_cols = [c for c in columns if not _is_id_column(c)]

    print(f"[fake_generator] ID columns   : {id_cols}")
    print(f"[fake_generator] Data columns : {data_cols}")

    # Build column specs for the LLM
    col_specs = []
    for col in data_cols:
        col_upper = col.upper()
        data_type = table_meta.get(col_upper, {}).get("data_type", "TEXT")
        hint      = hints.get(col, hints.get(col_upper, f"realistic value for {col}"))
        col_specs.append({
            "column":    col,
            "data_type": data_type,
            "hint":      hint
        })
    # One LLM call → expressions for all data columns
    callable_map = build_dynamic_faker_mapping(col_specs, locale=locale)

    # Generate rows
    data = []
    for i in range(rows_count):
        row = {}

        # Sequential integers for ID columns
        for col in id_cols:
            row[col] = i + 1

        # LLM-mapped Faker values for data columns
        for col in data_cols:
            try:
                row[col] = callable_map[col]()
            except Exception as e:
                print(f"[fake_generator] WARNING: error generating '{col}': {e} → using None")
                row[col] = None

        data.append(row)

    df = pd.DataFrame(data, columns=columns)
    print(f"[fake_generator] Generated {len(df)} rows × {len(df.columns)} columns")
    return df


if __name__ == "__main__":
    config = {
        "table":   "USERS",
        "rows":    5,
        "locale":  "en_IN",
        "columns": ["USER_ID", "USER_NAME", "EMAIL", "COUNTRY"],
        "hints": {
            "USER_NAME": "realistic Indian full name",
            "EMAIL":     "email address matching the name",
            "COUNTRY":   "country name, mostly India"
        }
    }

    df = generate_data(config)
    print("\n── Sample output ──")
    print(df.to_string(index=False))
    