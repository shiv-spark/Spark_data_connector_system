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
from metadata.catalog_builder import build_catalog

load_dotenv()

client = Groq(api_key=os.getenv("GROQ_API_KEY"))

MAX_ROWS = 1000


def _build_system_prompt(catalog: dict) -> str:
    """
    Builds the LLM system prompt with:
      - full schema catalog (columns, types, business context)
      - FK relationships surfaced explicitly
      - global context (domain, locale, currency)
      - hard 1000 row limit instruction
    """

    # Separate real tables from metadata keys
    tables = {k: v for k, v in catalog.items() if not k.startswith("_")}
    relationships  = catalog.get("_relationships", {})
    global_context = catalog.get("_global_context", {})

    # Build a compact schema summary per table
    schema_lines = []
    for table, meta in tables.items():
        schema_lines.append(f"\nTable: {table}")
        if meta.get("description"):
            schema_lines.append(f"  Description : {meta['description']}")
        if meta.get("use_case"):
            schema_lines.append(f"  Use case    : {meta['use_case']}")
        schema_lines.append("  Columns:")
        for col, col_meta in meta["columns"].items():
            col_ctx = meta.get("column_context", {}).get(col, "")
            fk      = meta.get("foreign_keys", {}).get(col, "")
            fk_note = f" → FK to {fk}" if fk else ""
            ctx_note = f" | {col_ctx}" if col_ctx else ""
            schema_lines.append(
                f"    {col:30} {col_meta['data_type']:10} "
                f"nullable={col_meta['nullable']}{fk_note}{ctx_note}"
            )

    # FK relationships summary
    rel_lines = []
    if relationships:
        rel_lines.append("\nForeign key relationships:")
        for fk, ref in relationships.items():
            rel_lines.append(f"  {fk} → {ref}")

    # Global context
    ctx_lines = []
    if global_context:
        ctx_lines.append("\nGlobal context:")
        for k, v in global_context.items():
            ctx_lines.append(f"  {k}: {v}")

    schema_summary = "\n".join(schema_lines + rel_lines + ctx_lines)

    return f"""
You are a data generation assistant with full knowledge of the database schema below.
Parse the user's plain-English request and return ONLY a valid JSON object with:
  - "table"   : target table name (must match schema exactly, case-sensitive)
  - "rows"    : number of rows to generate (integer, max {MAX_ROWS})
  - "locale"  : Faker locale e.g. "en_IN", "en_US" (infer from request or use default)
  - "columns" : list of column names to populate (must exist in that table)
  - "hints"   : dict of column -> plain English hint for data generation

Rules:
  - NEVER exceed {MAX_ROWS} rows — cap at {MAX_ROWS} if user asks for more
  - Table and column names must match the schema exactly
  - For FK columns, note in hints that the value must reference the parent table
  - Return ONLY valid JSON, no explanation, no markdown, no code fences

Schema:
{schema_summary}

Example output:
{{
  "table": "ORDERS",
  "rows": 100,
  "locale": "en_IN",
  "columns": ["ORDER_ID", "USER_ID", "PRODUCT_NAME", "AMOUNT", "ORDER_DATE"],
  "hints": {{
    "ORDER_ID":     "unique sequential integer starting from 1",
    "USER_ID":      "integer referencing USERS.USER_ID, pick values between 1 and 100",
    "PRODUCT_NAME": "realistic product name e.g. Laptop, Phone, Headphones",
    "AMOUNT":       "order total in INR between 500 and 50000",
    "ORDER_DATE":   "recent date within the last 2 years"
  }}
}}
"""


def parse_prompt(user_prompt: str) -> dict:
    """
    Uses the LLM to parse a plain-English request into a structured spec.
    Injects the full enriched catalog (business context + FKs) into the prompt.
    Enforces the 1000 row cap.

    Returns: { table, rows, locale, columns, hints }
    """

    catalog       = build_catalog()
    system_prompt = _build_system_prompt(catalog)

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
        config = json.loads(raw)
    except json.JSONDecodeError as e:
        print(f"[prompt_parser] JSON parse error: {e}\nRaw:\n{raw}")
        raise

    # Hard cap — even if LLM ignores the instruction
    if config.get("rows", 0) > MAX_ROWS:
        print(f"[prompt_parser] WARNING: rows capped from {config['rows']} to {MAX_ROWS}")
        config["rows"] = MAX_ROWS

    return config


if __name__ == "__main__":
    result = parse_prompt(
        "Generate 50 realistic Indian users with name, email, phone and country"
    )
    print(json.dumps(result, indent=2))

    # Test row cap
    capped = parse_prompt("Generate 5000 orders")
    print(f"\nRow cap test: requested 5000, got {capped['rows']}")