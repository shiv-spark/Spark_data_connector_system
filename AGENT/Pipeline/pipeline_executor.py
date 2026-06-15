import time

from Pipeline.pipeline_store import load_pipeline
import pandas as pd
from metadata.extractor import get_connection
from Pipeline.pipeline_builder import build_execution_plan
from Pipeline.pipeline_validator import validate_pipeline
from Pipeline.logger import log_execution

# def extract_from_snowflake(table_name):
#     """
#     Simulate extraction from Snowflake.
#     Later:
#         SELECT * FROM table_name
#     """

#     print(f"Extracting data from Snowflake table: {table_name}")

#     time.sleep(2)

#     return {
#         "rows": 5000
#     }

def extract_from_snowflake(table_name):

    query = f"SELECT * FROM {table_name}"
    conn = get_connection()

    df = pd.read_sql(query, conn)

    return {
        "table": table_name,
        "rows": len(df),
        "columns": list(df.columns),
        "data": df
    }

    
    # df = pd.read_sql(query, conn)

    # return df


# def load_to_target(target, data):
#     """
#     Simulate loading data.
#     Later:
#         upload to S3
#         write to Postgres
#         etc.
#     """

#     print(
#         f"Loading {data['rows']} rows into {target}"
#     )

#     time.sleep(2)

# def load_to_target(target, df):

#     if target == "local_file_system":

#         filepath = f"output/{table_name}.csv"

#         df.to_csv(
#             filepath,
#             index=False
#         )

#         print(
#             f"Saved to {filepath}"
#         )
import os

def load_to_target(target, data):

    if target == "local_file_system":

        os.makedirs("output", exist_ok=True)

        filepath = f"output/{data['table']}.csv"

        data["data"].to_csv(
            filepath,
            index=False
        )

        print(f"Saved to {filepath}")


STEP_REGISTRY = {
    "extract_from_snowflake": extract_from_snowflake,
    "save_to_local": load_to_target
}


def execute_pipeline(pipeline_name):

    pipeline = load_pipeline(pipeline_name)

    if not pipeline:
        raise ValueError(
            f"Pipeline '{pipeline_name}' not found."
        )
    validate_pipeline(pipeline)
    print("\n" + "=" * 50)
    print(f"Starting Pipeline: {pipeline_name}")
    print("=" * 50)

    source = pipeline["source"]
    target = pipeline["target"]
    table = pipeline["table"]

    start_time = time.time()

    # STEP 1
    plan = build_execution_plan(pipeline)

    print("\nExecution Plan:")
    print(plan)

    data = None

    for step in plan:

        print(f"\nRunning Step: {step}")

        if step == "extract_from_snowflake":

            data = STEP_REGISTRY[step](table)

            print(
                f"Extracted {data['rows']} rows"
            )

        elif step == "save_to_local":

            STEP_REGISTRY[step](
                target,
                data
            )

    duration = round(
        time.time() - start_time,
        2
    )

    result = {
        "pipeline": pipeline_name,
        "status": "SUCCESS",
        "rows_processed": data["rows"],
        "duration_seconds": duration
    }
    log_execution(result)
    print("\nPipeline Finished")
    print(result)

    return result


if __name__ == "__main__":

    execute_pipeline(
        "Department Data ETL"
    )


# import sys
# import os

# sys.path.append(
#     os.path.dirname(
#         os.path.dirname(os.path.abspath(__file__))
#     )
# )

# import time
# import pandas as pd
# from metadata.extractor import get_connection
# from Pipeline.pipeline_store     import load_pipeline
# from Pipeline.pipeline_validator import validate_pipeline
# from Pipeline.pipeline_builder   import build_execution_plan
# from Pipeline.logger             import log_execution


# OUTPUT_DIR = os.path.join(
#     os.path.dirname(os.path.abspath(__file__)),
#     "output"
# )


# # ── Extract ───────────────────────────────────────────────────────

# def extract_from_snowflake(pipeline: dict) -> dict:
#     """
#     Extracts data from a Snowflake table.
#     Applies SQL filter if specified in pipeline spec.
#     Returns { table, data: DataFrame, rows: int }
#     """

#     table   = pipeline["table"].upper()
#     filters = pipeline.get("filters", "").strip()

#     conn   = get_connection()
#     cursor = conn.cursor()

#     query = f"SELECT * FROM {table}"
#     if filters:
#         query += f" WHERE {filters}"

#     print(f"[executor] Running: {query}")
#     cursor.execute(query)

#     rows      = cursor.fetchall()
#     col_names = [desc[0] for desc in cursor.description]

#     cursor.close()
#     conn.close()

#     df = pd.DataFrame(rows, columns=col_names)
#     print(f"[executor] Extracted {len(df)} rows from {table}")

#     return {"table": table, "data": df, "rows": len(df)}


# # ── Transform ─────────────────────────────────────────────────────

# def apply_filters(pipeline: dict, data: dict) -> dict:
#     """
#     Applies additional in-memory filtering/transformation.
#     Currently a passthrough — extend here for column renaming,
#     type casting, deduplication etc.
#     """
#     print(f"[executor] Transform step — {len(data['data'])} rows passed through")
#     return data


# # ── Load ──────────────────────────────────────────────────────────

# def save_to_local(pipeline: dict, data: dict) -> str:
#     """Saves DataFrame to a CSV file in Pipeline/output/"""

#     os.makedirs(OUTPUT_DIR, exist_ok=True)
#     filepath = os.path.join(OUTPUT_DIR, f"{data['table'].lower()}.csv")
#     data["data"].to_csv(filepath, index=False)
#     print(f"[executor] Saved to {filepath}")
#     return filepath


# def upload_to_s3(pipeline: dict, data: dict):
#     """Placeholder for S3 upload — implement with boto3 when needed."""
#     print("[executor] S3 upload not yet implemented")
#     raise NotImplementedError("S3 upload coming in next version")


# def load_to_snowflake_target(pipeline: dict, data: dict):
#     """
#     Loads DataFrame into a different Snowflake table.
#     Uses the same PUT + COPY INTO pattern as the data generator.
#     """
#     import tempfile
#     from Pipeline.logger import log_execution

#     table = pipeline.get("target_table", data["table"] + "_COPY").upper()
#     df    = data["data"]

#     # Write to temp CSV then load
#     with tempfile.NamedTemporaryFile(suffix=".csv", delete=False, mode="w") as f:
#         df.to_csv(f, index=False)
#         tmp_path = f.name

#     conn   = get_connection()
#     cursor = conn.cursor()
#     norm   = tmp_path.replace("\\", "/")
#     fname  = os.path.basename(tmp_path)

#     cursor.execute(f"PUT 'file://{norm}' @%{table} OVERWRITE=TRUE AUTO_COMPRESS=FALSE")
#     cursor.execute(f"""
#         COPY INTO {table}
#         FROM @%{table}/{fname}
#         FILE_FORMAT = (TYPE='CSV' SKIP_HEADER=1 FIELD_OPTIONALLY_ENCLOSED_BY='"')
#         ON_ERROR = 'ABORT_STATEMENT'
#     """)
#     cursor.execute(f"REMOVE @%{table}/{fname}")
#     cursor.close()
#     conn.close()
#     os.unlink(tmp_path)
#     print(f"[executor] Loaded {len(df)} rows into Snowflake table {table}")


# # ── Step registry ─────────────────────────────────────────────────

# STEP_REGISTRY = {
#     "extract_from_snowflake": extract_from_snowflake,
#     "apply_filters":          apply_filters,
#     "save_to_local":          save_to_local,
#     "upload_to_s3":           upload_to_s3,
#     "load_to_snowflake":      load_to_snowflake_target,
# }


# # ── Main executor ─────────────────────────────────────────────────

# def execute_pipeline(pipeline_name: str) -> dict:
#     """
#     Loads, validates, and executes a named pipeline.

#     Flow:
#         1. Load pipeline spec from pipelines.json
#         2. Validate spec against schema catalog
#         3. Build execution plan (list of steps)
#         4. Run each step in order
#         5. Log result (SUCCESS or FAILED)

#     Returns:
#         result dict with status, rows_processed, duration_seconds
#     """

#     pipeline = load_pipeline(pipeline_name)
#     if not pipeline:
#         raise ValueError(f"Pipeline '{pipeline_name}' not found.")

#     validate_pipeline(pipeline)

#     print("\n" + "=" * 50)
#     print(f"Starting Pipeline : {pipeline_name}")
#     print(f"Source → Target   : {pipeline['source']} → {pipeline['target']}")
#     print(f"Table             : {pipeline['table']}")
#     print("=" * 50)

#     plan       = build_execution_plan(pipeline)
#     start_time = time.time()
#     data       = None

#     print(f"\nExecution plan: {plan}\n")

#     try:
#         for step in plan:
#             print(f"[executor] Running step: {step}")

#             if step == "extract_from_snowflake":
#                 data = STEP_REGISTRY[step](pipeline)

#             elif step == "apply_filters":
#                 data = STEP_REGISTRY[step](pipeline, data)

#             elif step in ("save_to_local", "upload_to_s3", "load_to_snowflake"):
#                 STEP_REGISTRY[step](pipeline, data)

#         duration = round(time.time() - start_time, 2)
#         result   = {
#             "pipeline":         pipeline_name,
#             "status":           "SUCCESS",
#             "rows_processed":   data["rows"] if data else 0,
#             "duration_seconds": duration
#         }

#     except Exception as e:
#         duration = round(time.time() - start_time, 2)
#         result   = {
#             "pipeline":         pipeline_name,
#             "status":           "FAILED",
#             "rows_processed":   0,
#             "duration_seconds": duration,
#             "error":            str(e)
#         }
#         print(f"[executor] ERROR: {e}")

#     log_execution(result)

#     print("\n" + "=" * 50)
#     print(f"Pipeline finished — {result['status']}")
#     print(result)
#     print("=" * 50)

#     return result


# if __name__ == "__main__":
#     execute_pipeline("Daily Departments ETL")