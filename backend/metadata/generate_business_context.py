import sys
import os

sys.path.append(
    os.path.dirname(
        os.path.dirname(os.path.abspath(__file__))
    )
)

import json
import re
from groq import Groq
from dotenv import load_dotenv
from metadata.extractor import extract_schema_metadata
from metadata.foreign_keys import get_foreign_keys
from metadata.primary_keys import get_primary_keys
from metadata.sample_values import get_sample_values

load_dotenv()

client = Groq(api_key=os.getenv("GROQ_API_KEY"))

OUTPUT_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "business_context.json"
)

SYSTEM_PROMPT = """
You are a database documentation expert.
Given real database schema information (tables, columns, data types, sample values, PKs, FKs),
generate a business_context.json that describes:
  - What each table is for
  - What each column means in plain English
  - Realistic data generation hints per column
  - Table relationships in plain English

Return ONLY valid JSON in exactly this structure — no markdown, no explanation:
{
  "tables": {
    "TABLE_NAME": {
      "description": "what this table stores",
      "use_case": "when/why this table is queried",
      "columns": {
        "COLUMN_NAME": "plain English meaning + data hint"
      }
    }
  },
  "relationships": {
    "CHILD_TABLE.FK_COLUMN": "References PARENT_TABLE.PK_COLUMN — plain English meaning"
  },
  "global_context": {
    "domain": "inferred business domain",
    "default_locale": "en_IN",
    "currency": "INR",
    "date_format": "YYYY-MM-DD",
    "id_strategy": "All ID columns are sequential integers starting from 1"
  }
}
"""


def collect_schema_info() -> dict:
    """
    Collects everything the LLM needs to understand the database:
    - All tables and columns with data types
    - Primary keys
    - Foreign keys
    - Sample values per column (up to 5)
    """

    print("[1/4] Extracting schema metadata...")
    schema_df = extract_schema_metadata()

    print("[2/4] Extracting primary keys...")
    try:
        pk_df = get_primary_keys()
        pks = {}
        for _, row in pk_df.iterrows():
            table = row["TABLE_NAME"]
            if table not in pks:
                pks[table] = []
            pks[table].append(row["COLUMN_NAME"])
    except Exception as e:
        print(f"  WARNING: Could not get PKs: {e}")
        pks = {}

    print("[3/4] Extracting foreign keys...")
    try:
        fk_df = get_foreign_keys()
        fks = []
        for _, row in fk_df.iterrows():
            fks.append({
                "table":             row["TABLE_NAME"],
                "column":            row["COLUMN_NAME"],
                "referenced_table":  row["REFERENCED_TABLE"],
                "referenced_column": row["REFERENCED_COLUMN"]
            })
    except Exception as e:
        print(f"  WARNING: Could not get FKs: {e}")
        fks = []

    print("[4/4] Collecting sample values per column...")
    tables_info = {}
    for _, row in schema_df.iterrows():
        table  = row["TABLE_NAME"]
        column = row["COLUMN_NAME"]

        if table not in tables_info:
            tables_info[table] = {
                "columns":      {},
                "primary_keys": pks.get(table, [])
            }

        try:
            samples = get_sample_values(table, column, limit=5)
        except Exception:
            samples = []

        tables_info[table]["columns"][column] = {
            "data_type": row["DATA_TYPE"],
            "nullable":  row["IS_NULLABLE"],
            "samples":   samples
        }

    return {
        "tables":       tables_info,
        "foreign_keys": fks
    }


def generate_business_context(schema_info: dict) -> dict:
    """
    Sends the full schema info to the LLM and gets back
    a structured business_context.json
    """

    print("\n[LLM] Generating business context from schema...")

    payload = json.dumps(schema_info, indent=2, default=str)

    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user",   "content": f"Here is the full database schema:\n{payload}"}
        ],
        temperature=0
    )

    raw = response.choices[0].message.content.strip()
    raw = re.sub(r"^```json|^```|```$", "", raw, flags=re.MULTILINE).strip()

    try:
        return json.loads(raw)
    except json.JSONDecodeError as e:
        print(f"JSON Parse Error: {e}\nRaw:\n{raw}")
        raise


def save_business_context(context: dict) -> str:
    with open(OUTPUT_PATH, "w") as f:
        json.dump(context, f, indent=4)
    print(f"\n[saved] business_context.json → {OUTPUT_PATH}")
    return OUTPUT_PATH


if __name__ == "__main__":

    print("=" * 55)
    print("Auto-generating business_context.json from schema")
    print("=" * 55)

    # Step 1 — collect real schema info from Snowflake
    schema_info = collect_schema_info()

    print(f"\nFound {len(schema_info['tables'])} tables:")
    for table in schema_info["tables"]:
        cols = len(schema_info["tables"][table]["columns"])
        print(f"  {table} ({cols} columns)")

    # Step 2 — ask LLM to generate business context
    context = generate_business_context(schema_info)

    # Step 3 — save to file
    path = save_business_context(context)

    print("\n" + "=" * 55)
    print("Done! Review and edit if needed:")
    print(f"  {path}")
    print("=" * 55)

    print("\nGenerated context preview:")
    print(json.dumps(context, indent=2))