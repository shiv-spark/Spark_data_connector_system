
import sys
import os

sys.path.append(
    os.path.dirname(
        os.path.dirname(os.path.abspath(__file__))
    )
)

import pandas as pd
from metadata.catalog_builder import build_catalog


def validate_dataframe(df: pd.DataFrame, config: dict) -> bool:
    """
    Validates a generated DataFrame against:
      1. Expected row count
      2. No completely empty DataFrame
      3. Column names match schema catalog exactly
      4. No nulls in NOT NULL columns (per schema)

    Args:
        df:     Generated DataFrame
        config: Parsed config dict (table, rows, columns, hints)

    Returns:
        True if all checks pass, raises ValueError otherwise
    """

    table    = config["table"]
    expected = config["rows"]
    columns  = config["columns"]
    errors   = []

    # 1. Empty check
    if df.empty:
        raise ValueError("Generated DataFrame is empty.")

    # 2. Row count check
    if len(df) != expected:
        errors.append(
            f"Row count mismatch: expected {expected}, got {len(df)}"
        )

    # 3. Column name check against schema catalog
    catalog = build_catalog()

    if table not in catalog:
        errors.append(f"Table '{table}' not found in schema catalog.")
    else:
        schema_cols = set(catalog[table]["columns"].keys())
        # Normalise to uppercase for comparison
        requested   = set(c.upper() for c in columns)
        unknown     = requested - schema_cols

        if unknown:
            errors.append(
                f"Columns not found in schema for table '{table}': {unknown}"
            )

        # 4. NOT NULL check per column
        for col in columns:
            col_upper = col.upper()
            if col_upper in schema_cols:
                nullable = catalog[table]["columns"][col_upper].get("nullable", "YES")
                if nullable == "NO":
                    null_count = df[col].isnull().sum()
                    if null_count > 0:
                        errors.append(
                            f"Column '{col}' is NOT NULL but has {null_count} null value(s)."
                        )

    # 5. General null check across all columns
    total_nulls = df.isnull().sum().sum()
    if total_nulls > 0:
        null_summary = df.isnull().sum()
        null_cols    = null_summary[null_summary > 0].to_dict()
        errors.append(f"DataFrame contains null values: {null_cols}")

    if errors:
        raise ValueError(
            f"Validation failed with {len(errors)} error(s):\n" +
            "\n".join(f"  - {e}" for e in errors)
        )

    print(f"[validator] All {len(df)} rows passed validation for table '{table}'")
    return True


if __name__ == "__main__":
    df = pd.DataFrame({
        "USER_ID": [1, 2],
        "NAME":    ["Ravi Kumar", "Priya Sharma"],
        "EMAIL":   ["ravi@example.com", "priya@example.com"]
    })
    config = {
        "table":   "USERS",
        "rows":    2,
        "columns": ["USER_ID", "NAME", "EMAIL"],
        "hints":   {}
    }
    print(validate_dataframe(df, config))