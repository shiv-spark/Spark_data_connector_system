from metadata.catalog_builder import build_catalog


def validate_pipeline(pipeline):

    catalog = build_catalog()

    table = pipeline["table"]
    table=table.upper()

    if table not in catalog:
        raise ValueError(
            f"Table '{table}' not found in schema catalog."
        )

    print(f"✓ Table '{table}' validated")

    return True




# import sys
# import os

# sys.path.append(
#     os.path.dirname(
#         os.path.dirname(os.path.abspath(__file__))
#     )
# )

# import re
# from metadata.catalog_builder import build_catalog

# VALID_SOURCES = ["snowflake"]
# VALID_TARGETS = ["snowflake", "local_file_system", "s3"]
# VALID_STEPS   = ["extract", "transform", "load"]
# CRON_PATTERN  = re.compile(
#     r"^(\*|[0-9,\-\/]+)\s+"   # minute
#     r"(\*|[0-9,\-\/]+)\s+"   # hour
#     r"(\*|[0-9,\-\/]+)\s+"   # day of month
#     r"(\*|[0-9,\-\/]+)\s+"   # month
#     r"(\*|[0-9,\-\/]+)$"     # day of week
# )


# def validate_pipeline(pipeline: dict) -> bool:
#     """
#     Validates a pipeline spec against:
#       1. Required fields present
#       2. Table exists in schema catalog
#       3. Source is a supported value
#       4. Target is a supported value
#       5. Steps are valid
#       6. Schedule is valid cron or "manual"

#     Raises ValueError with all errors listed.
#     Returns True if all checks pass.
#     """

#     errors  = []
#     catalog = build_catalog()

#     # 1. Required fields
#     required = ["pipeline_name", "source", "target", "table", "schedule", "steps"]
#     for field in required:
#         if field not in pipeline or not pipeline[field]:
#             errors.append(f"Missing required field: '{field}'")

#     if errors:
#         raise ValueError("Validation failed:\n" + "\n".join(f"  - {e}" for e in errors))

#     # 2. Table exists in catalog
#     table = pipeline["table"].upper()
#     real_tables = [k for k in catalog if not k.startswith("_")]
#     if table not in real_tables:
#         errors.append(
#             f"Table '{table}' not found in schema. "
#             f"Available: {real_tables}"
#         )

#     # 3. Valid source
#     if pipeline["source"].lower() not in VALID_SOURCES:
#         errors.append(
#             f"Invalid source '{pipeline['source']}'. "
#             f"Must be one of: {VALID_SOURCES}"
#         )

#     # 4. Valid target
#     if pipeline["target"].lower() not in VALID_TARGETS:
#         errors.append(
#             f"Invalid target '{pipeline['target']}'. "
#             f"Must be one of: {VALID_TARGETS}"
#         )

#     # 5. Valid steps
#     for step in pipeline.get("steps", []):
#         if step not in VALID_STEPS:
#             errors.append(
#                 f"Invalid step '{step}'. Must be one of: {VALID_STEPS}"
#             )

#     # 6. Valid schedule
#     schedule = pipeline.get("schedule", "").strip()
#     if schedule != "manual" and not CRON_PATTERN.match(schedule):
#         errors.append(
#             f"Invalid schedule '{schedule}'. "
#             f"Must be a valid cron expression (e.g. '0 2 * * *') or 'manual'."
#         )

#     if errors:
#         raise ValueError(
#             f"Validation failed with {len(errors)} error(s):\n" +
#             "\n".join(f"  - {e}" for e in errors)
#         )

#     print(f"[pipeline_validator] Pipeline '{pipeline['pipeline_name']}' passed all checks")
#     return True


# if __name__ == "__main__":
#     test = {
#         "pipeline_name": "Daily Departments ETL",
#         "source":        "snowflake",
#         "target":        "local_file_system",
#         "table":         "DEPARTMENTS",
#         "schedule":      "0 2 * * *",
#         "steps":         ["extract", "load"],
#         "filters":       "",
#         "description":   "Test pipeline"
#     }
#     print(validate_pipeline(test))