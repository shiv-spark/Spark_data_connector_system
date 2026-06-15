# import sys
# import os

# sys.path.append(
#     os.path.dirname(
#         os.path.dirname(os.path.abspath(__file__))
#     )
# )

# from generator.prompt_parser import parse_prompt
# from generator.fake_generator import generate_data
# from generator.validator      import validate_dataframe
# from generator.csv_writer     import save_csv
# from generator.loader         import load_to_snowflake, verify_load


# def run(user_prompt: str, load_to_db: bool = True) -> dict:
#     """
#     Full pipeline: plain-English prompt → validated CSV → Snowflake.

#     Steps:
#         1. parse_prompt    → structured config (table, rows, columns, hints)
#         2. generate_data   → pandas DataFrame with fake data
#         3. validate        → checks schema, row count, nullability
#         4. save_csv        → writes timestamped CSV to generator/generated/
#         5. load_to_db      → PUT + COPY INTO Snowflake table  (optional)
#         6. verify_load     → SELECT COUNT(*) sanity check

#     Args:
#         user_prompt : plain-English data request
#         load_to_db  : set False to stop after CSV (useful for testing)

#     Returns:
#         dict with keys: config, filepath, total_rows
#     """

#     print(f"\n{'='*55}")
#     print(f"Prompt  : {user_prompt}")
#     print(f"Load DB : {load_to_db}")
#     print(f"{'='*55}\n")

#     # ── Step 1: Parse ────────────────────────────────────────
#     print("[1/5] Parsing prompt with LLM...")
#     config = parse_prompt(user_prompt)
#     print(f"      Table   : {config['table']}")
#     print(f"      Rows    : {config['rows']}")
#     print(f"      Locale  : {config['locale']}")
#     print(f"      Columns : {config['columns']}\n")

#     # ── Step 2: Generate ─────────────────────────────────────
#     print("[2/5] Generating fake data...")
#     df = generate_data(config)
#     print(f"      {len(df)} rows × {len(df.columns)} columns\n")

#     # ── Step 3: Validate ─────────────────────────────────────
#     print("[3/5] Validating...")
#     validate_dataframe(df, config)
#     print()

#     # ── Step 4: Save CSV ─────────────────────────────────────
#     print("[4/5] Saving to CSV...")
#     filepath = save_csv(df, config)
#     print()

#     # ── Step 5: Load to Snowflake ────────────────────────────
#     total_rows = None
#     if load_to_db:
#         print("[5/5] Loading to Snowflake...")
#         total_rows = load_to_snowflake(filepath, config)

#         verified = verify_load(config["table"], expected_rows=config["rows"])
#         if not verified:
#             print("[pipeline] WARNING: Row count verification failed after load.")
#         print()

#     # ── Done ─────────────────────────────────────────────────
#     print(f"{'='*55}")
#     print(f"Done!")
#     print(f"  CSV     : {filepath}")
#     if load_to_db:
#         print(f"  Table   : {config['table']} ({total_rows} total rows in Snowflake)")
#     print(f"{'='*55}\n")

#     return {
#         "config":     config,
#         "filepath":   filepath,
#         "total_rows": total_rows
#     }


# # if __name__ == "__main__":
# #     # Run full pipeline including DB load
# #     result = run(
# #         "Generate 100 realistic Indian users with name, email, phone and city",
# #         load_to_db=True
# #     )

# if __name__ == "__main__":
#     # Run full pipeline including DB load
#     result = run(
#         "Generate 100 realistic  orders with name, email, phone,city,order id,ampount,product name and order date",
#         load_to_db=True
#     )



# if __name__ == "__main__":
#     # Run full pipeline including DB load
#     result = run(
#         "Generate 100 realistic  department with location",
#         load_to_db=True
#     )


#     # Or test CSV-only (skip DB load):
#     # result = run("Generate 10 users", load_to_db=False)



import sys
import os

sys.path.append(
    os.path.dirname(
        os.path.dirname(os.path.abspath(__file__))
    )
)

from generator.prompt_parser  import parse_prompt, MAX_ROWS
from generator.fake_generator  import generate_data
from generator.validator       import validate_dataframe
from generator.csv_writer      import save_csv
from generator.loader          import load_to_snowflake, verify_load


def run(user_prompt: str, load_to_db: bool = True) -> dict:
    """
    Single-table pipeline: plain-English prompt → validated CSV → Snowflake.

    Steps:
        1. parse_prompt   → structured config (table, rows, columns, hints)
        2. row cap        → hard limit of MAX_ROWS (1000)
        3. generate_data  → pandas DataFrame with fake data
        4. validate       → schema + nullability checks
        5. save_csv       → timestamped CSV in generator/generated/
        6. load_to_db     → PUT + COPY INTO Snowflake (optional)
        7. verify         → SELECT COUNT(*) sanity check

    Args:
        user_prompt : plain-English data request
        load_to_db  : set False to stop after CSV (useful for testing)

    Returns:
        dict with keys: config, filepath, total_rows
    """

    print(f"\n{'='*55}")
    print(f"Prompt  : {user_prompt}")
    print(f"Load DB : {load_to_db}")
    print(f"{'='*55}\n")

    # ── Step 1: Parse ────────────────────────────────────────
    print("[1/6] Parsing prompt with LLM...")
    config = parse_prompt(user_prompt)
    print(f"      Table   : {config['table']}")
    print(f"      Rows    : {config['rows']}")
    print(f"      Locale  : {config['locale']}")
    print(f"      Columns : {config['columns']}\n")

    # ── Step 2: Row cap (safety net on top of prompt_parser) ─
    if config["rows"] > MAX_ROWS:
        print(f"[2/6] Row cap: {config['rows']} → {MAX_ROWS}")
        config["rows"] = MAX_ROWS
    else:
        print(f"[2/6] Row count: {config['rows']} (within limit of {MAX_ROWS})\n")

    # ── Step 3: Generate ─────────────────────────────────────
    print("[3/6] Generating fake data...")
    df = generate_data(config)
    print(f"      {len(df)} rows × {len(df.columns)} columns\n")

    # ── Step 4: Validate ─────────────────────────────────────
    print("[4/6] Validating...")
    validate_dataframe(df, config)
    print()

    # ── Step 5: Save CSV ─────────────────────────────────────
    print("[5/6] Saving to CSV...")
    filepath = save_csv(df, config)
    print()

    # ── Step 6: Load to Snowflake ────────────────────────────
    total_rows = None
    if load_to_db:
        print("[6/6] Loading to Snowflake...")
        total_rows = load_to_snowflake(filepath, config)
        verify_load(config["table"], expected_rows=config["rows"])
        print()

    print(f"{'='*55}")
    print(f"Done!")
    print(f"  CSV     : {filepath}")
    if load_to_db:
        print(f"  Table   : {config['table']} ({total_rows} total rows in Snowflake)")
    print(f"{'='*55}\n")

    return {
        "config":     config,
        "filepath":   filepath,
        "total_rows": total_rows
    }


if __name__ == "__main__":
    run(
        "Generate 100 realistic demo with id and name   ",
        load_to_db=True
    )