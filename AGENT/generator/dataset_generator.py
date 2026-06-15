import sys
import os

sys.path.append(
    os.path.dirname(
        os.path.dirname(os.path.abspath(__file__))
    )
)

import json
import re
import random
import pandas as pd
from groq import Groq
from dotenv import load_dotenv
from metadata.catalog_builder import build_catalog
from generator.fake_generator  import generate_data
from generator.validator       import validate_dataframe
from generator.csv_writer      import save_csv
from generator.loader          import load_to_snowflake, verify_load
from generator.prompt_parser   import MAX_ROWS

load_dotenv()

client = Groq(api_key=os.getenv("GROQ_API_KEY"))


# ── Step 1: Parse multi-table request ───────────────────────────────────────

DATASET_SYSTEM_PROMPT = """
You are a data generation assistant with full knowledge of the database schema provided.
The user wants to generate a DATASET — data across multiple related tables.

Parse the request and return ONLY a valid JSON array where each element is a table spec:
[
  {{
    "table"   : "TABLE_NAME",
    "rows"    : <integer, max {max_rows}>,
    "locale"  : "en_IN",
    "columns" : ["COL1", "COL2", ...],
    "hints"   : {{ "COL1": "hint", ... }},
    "depends_on": "PARENT_TABLE or null"
  }},
  ...
]

Rules:
  - Order tables so parent tables come BEFORE child tables
    e.g. DEPARTMENTS before EMPLOYEES (because EMPLOYEES.DEPT_ID → DEPARTMENTS.DEPT_ID)
  - For FK columns, set hint to: "pick a random value from generated <PARENT_TABLE>.<PK_COLUMN>"
  - depends_on = parent table name if this table has a FK to it, else null
  - Never exceed {max_rows} rows per table
  - Return ONLY the JSON array, no explanation, no markdown, no code fences

Schema:
{schema}
"""


def parse_dataset_prompt(user_prompt: str) -> list[dict]:
    """
    Parses a multi-table plain-English request into an ordered list of table specs.
    Parent tables always come before child tables.
    """

    catalog       = build_catalog()
    tables        = {k: v for k, v in catalog.items() if not k.startswith("_")}
    relationships = catalog.get("_relationships", {})

    schema_lines = []
    for table, meta in tables.items():
        schema_lines.append(f"\nTable: {table}")
        if meta.get("description"):
            schema_lines.append(f"  {meta['description']}")
        for col, col_meta in meta["columns"].items():
            fk  = meta.get("foreign_keys", {}).get(col, "")
            ctx = meta.get("column_context", {}).get(col, "")
            fk_note  = f" → FK to {fk}" if fk else ""
            ctx_note = f" | {ctx}" if ctx else ""
            schema_lines.append(f"    {col:28} {col_meta['data_type']:8}{fk_note}{ctx_note}")

    if relationships:
        schema_lines.append("\nRelationships:")
        for fk, ref in relationships.items():
            schema_lines.append(f"  {fk} → {ref}")

    schema_summary = "\n".join(schema_lines)
    system_prompt  = DATASET_SYSTEM_PROMPT.format(
        max_rows=MAX_ROWS,
        schema=schema_summary
    )

    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user",   "content": user_prompt}
        ],
        temperature=0
    )

    raw = response.choices[0].message.content.strip()
    raw = re.sub(r"^```json|^```|```$", "", raw, flags=re.MULTILINE).strip()

    try:
        specs = json.loads(raw)
    except json.JSONDecodeError as e:
        print(f"[dataset_generator] JSON parse error: {e}\nRaw:\n{raw}")
        raise

    # Enforce row cap on every table
    for spec in specs:
        if spec.get("rows", 0) > MAX_ROWS:
            print(f"[dataset_generator] Row cap: {spec['table']} {spec['rows']} → {MAX_ROWS}")
            spec["rows"] = MAX_ROWS

    return specs


# ── Step 2: Resolve FK values from already-generated parent data ─────────────

def _inject_fk_values(df: pd.DataFrame, spec: dict, generated: dict) -> pd.DataFrame:
    """
    For every FK column in this table, replaces values with random picks
    from the corresponding already-generated parent DataFrame.

    generated: { "TABLE_NAME": DataFrame }
    """

    catalog = build_catalog()
    table   = spec["table"]
    fks     = catalog.get(table, {}).get("foreign_keys", {})

    for col, ref in fks.items():
        if col not in df.columns:
            continue

        ref_table, ref_col = ref.split(".")

        if ref_table not in generated:
            print(f"[dataset_generator] WARNING: parent '{ref_table}' not yet generated — "
                  f"FK column '{col}' will keep generated values")
            continue

        parent_df    = generated[ref_table]
        parent_values = parent_df[ref_col].tolist()

        if not parent_values:
            print(f"[dataset_generator] WARNING: parent '{ref_table}.{ref_col}' is empty")
            continue

        # Replace all FK column values with random picks from parent
        df[col] = [random.choice(parent_values) for _ in range(len(df))]
        print(f"[dataset_generator] FK resolved: {table}.{col} → "
              f"{ref_table}.{ref_col} ({len(parent_values)} parent values)")

    return df


# ── Step 3: Main dataset generation function ─────────────────────────────────

def generate_dataset(
    user_prompt: str,
    load_to_db: bool = True
) -> dict:
    """
    Generates a linked multi-table dataset from a plain-English request.

    Flow:
        1. Parse request → ordered list of table specs (parents first)
        2. For each table in order:
            a. generate_data()  → DataFrame
            b. inject FK values from already-generated parent tables
            c. validate_dataframe()
            d. save_csv()
            e. load_to_snowflake() (if load_to_db=True)
        3. Return summary of all generated tables

    Args:
        user_prompt : plain-English dataset request
        load_to_db  : set False to stop after CSV

    Returns:
        dict of { TABLE_NAME: { df, filepath, total_rows } }
    """

    print(f"\n{'='*55}")
    print(f"Dataset prompt : {user_prompt}")
    print(f"Load DB        : {load_to_db}")
    print(f"{'='*55}\n")

    # ── Step 1: Parse ────────────────────────────────────────
    print("[1] Parsing multi-table request with LLM...")
    specs = parse_dataset_prompt(user_prompt)

    print(f"\n  Generation order:")
    for i, spec in enumerate(specs, 1):
        dep = f"  (depends on {spec['depends_on']})" if spec.get("depends_on") else ""
        print(f"  {i}. {spec['table']} — {spec['rows']} rows{dep}")
    print()

    # ── Step 2: Generate each table in order ─────────────────
    generated  = {}   # { TABLE_NAME: DataFrame }
    results    = {}   # final output

    for i, spec in enumerate(specs, 1):
        table = spec["table"]
        print(f"[{i+1}] Generating {table}...")

        # Generate base data
        df = generate_data(spec)

        # Resolve FK columns using parent DataFrames
        if spec.get("depends_on") and spec["depends_on"] in generated:
            df = _inject_fk_values(df, spec, generated)

        # Validate
        validate_dataframe(df, spec)

        # Save CSV
        filepath = save_csv(df, spec)

        # Load to Snowflake
        total_rows = None
        if load_to_db:
            total_rows = load_to_snowflake(filepath, spec)
            verify_load(table, expected_rows=spec["rows"])

        # Store for FK resolution of subsequent tables
        generated[table] = df

        results[table] = {
            "df":         df,
            "filepath":   filepath,
            "total_rows": total_rows,
            "rows":       len(df)
        }

        print(f"  ✓ {table}: {len(df)} rows generated\n")

    # ── Summary ──────────────────────────────────────────────
    print(f"{'='*55}")
    print("Dataset generation complete!")
    for table, result in results.items():
        print(f"  {table:20} {result['rows']:>5} rows → {result['filepath']}")
    print(f"{'='*55}\n")

    return results


if __name__ == "__main__":

    results = generate_dataset(
        "Generate 5 departments and 20 employees linked to those departments",
        load_to_db=True
    )

    for table, result in results.items():
        print(f"\n── {table} (first 3 rows) ──")
        print(result["df"].head(3).to_string(index=False))