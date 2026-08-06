import sys
import os

sys.path.append(
    os.path.dirname(
        os.path.dirname(os.path.abspath(__file__))
    )
)

import json
from metadata.extractor import extract_schema_metadata
from metadata.foreign_keys import get_foreign_keys

BUSINESS_CONTEXT_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "business_context.json"
)


def load_business_context() -> dict:
    """Loads business_context.json if it exists, returns empty dict otherwise."""
    if not os.path.exists(BUSINESS_CONTEXT_PATH):
        print("[catalog_builder] WARNING: business_context.json not found. "
              "Run metadata/generate_business_context.py first.")
        return {}
    with open(BUSINESS_CONTEXT_PATH, "r") as f:
        return json.load(f)


def build_catalog() -> dict:
    """
    Builds the full schema catalog injected into every LLM prompt.

    Contains per table:
      - columns        : name, data_type, nullable
      - description    : business meaning of the table (from business_context.json)
      - use_case       : when this table is queried
      - column_context : plain-English meaning of each column
      - foreign_keys   : FK relationships { column: "TABLE.COLUMN" }
      - primary_keys   : list of PK columns

    Also contains a top-level:
      - relationships  : all FK pairs across the schema
      - global_context : domain, locale, currency, date format
    """

    df      = extract_schema_metadata()
    context = load_business_context()

    tables_context     = context.get("tables", {})
    global_context     = context.get("global_context", {})
    context_relations  = context.get("relationships", {})

    # ── Build FK lookup: { "TABLE.COLUMN": "REF_TABLE.REF_COLUMN" } ──
    fk_lookup = {}
    try:
        fk_df = get_foreign_keys()
        for _, row in fk_df.iterrows():
            key = f"{row['TABLE_NAME']}.{row['COLUMN_NAME']}"
            val = f"{row['REFERENCED_TABLE']}.{row['REFERENCED_COLUMN']}"
            fk_lookup[key] = val
    except Exception as e:
        print(f"[catalog_builder] WARNING: Could not load FK data: {e}")

    # ── Build catalog ──
    catalog = {}

    for _, row in df.iterrows():
        table  = row["TABLE_NAME"]
        column = row["COLUMN_NAME"]

        if table not in catalog:
            # Pull table-level context
            tbl_ctx = tables_context.get(table, {})
            catalog[table] = {
                "description":    tbl_ctx.get("description", ""),
                "use_case":       tbl_ctx.get("use_case", ""),
                "columns":        {},
                "column_context": {},
                "foreign_keys":   {},
                "primary_keys":   []
            }

        # Column schema
        catalog[table]["columns"][column] = {
            "data_type": row["DATA_TYPE"],
            "nullable":  row["IS_NULLABLE"]
        }

        # Column business context
        col_ctx = tables_context.get(table, {}).get("columns", {})
        if column in col_ctx:
            catalog[table]["column_context"][column] = col_ctx[column]

        # FK reference for this column
        fk_key = f"{table}.{column}"
        if fk_key in fk_lookup:
            catalog[table]["foreign_keys"][column] = fk_lookup[fk_key]

    # ── Top-level metadata ──
    catalog["_relationships"]  = context_relations
    catalog["_global_context"] = global_context

    return catalog


if __name__ == "__main__":
    catalog = build_catalog()

    output_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "schema_catalog.json"
    )
    with open(output_path, "w") as f:
        json.dump(catalog, f, indent=4)

    print(f"Catalog generated → {output_path}")
    print(f"Tables: {[k for k in catalog if not k.startswith('_')]}")
    print(f"FK relationships: {catalog.get('_relationships', {})}")
