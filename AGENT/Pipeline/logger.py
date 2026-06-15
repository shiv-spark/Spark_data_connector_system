import json
import os
from datetime import datetime


# LOG_FILE = "Pipeline/logs/execution_log.json"
BASE_DIR = os.path.dirname(
    os.path.abspath(__file__)
)

LOG_FILE = os.path.join(
    BASE_DIR,
    "logs",
    "execution_log.json"
)

def log_execution(result):

    os.makedirs(
        "Pipeline/logs",
        exist_ok=True
    )

    result["timestamp"] = datetime.now().strftime(
        "%Y-%m-%d %H:%M:%S"
    )

    if os.path.exists(LOG_FILE):

        with open(LOG_FILE, "r") as f:
            logs = json.load(f)

    else:
        logs = []

    logs.append(result)

    with open(LOG_FILE, "w") as f:
        json.dump(
            logs,
            f,
            indent=4
        )

    print("✓ Execution logged")


# import json
# import os
# from datetime import datetime

# LOG_FILE = os.path.join(
#     os.path.dirname(os.path.abspath(__file__)),
#     "logs",
#     "execution_log.json"
# )


# def log_execution(result: dict):
#     """
#     Appends an execution result to the JSON log file.
#     Works for both SUCCESS and FAILED runs.

#     Args:
#         result: dict with keys — pipeline, status, rows_processed,
#                 duration_seconds, error (optional)
#     """

#     os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)

#     result["timestamp"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

#     # Ensure status is always present
#     if "status" not in result:
#         result["status"] = "UNKNOWN"

#     # Load existing logs
#     if os.path.exists(LOG_FILE):
#         with open(LOG_FILE, "r") as f:
#             try:
#                 logs = json.load(f)
#             except json.JSONDecodeError:
#                 logs = []
#     else:
#         logs = []

#     logs.append(result)

#     with open(LOG_FILE, "w") as f:
#         json.dump(logs, f, indent=4)

#     status_icon = "✓" if result["status"] == "SUCCESS" else "✗"
#     print(f"[logger] {status_icon} Execution logged — status: {result['status']}")


# def get_logs(pipeline_name: str = None) -> list:
#     """
#     Returns all logs, optionally filtered by pipeline name.
#     """

#     if not os.path.exists(LOG_FILE):
#         return []

#     with open(LOG_FILE, "r") as f:
#         try:
#             logs = json.load(f)
#         except json.JSONDecodeError:
#             return []

#     if pipeline_name:
#         logs = [l for l in logs if l.get("pipeline") == pipeline_name]

#     return logs


# if __name__ == "__main__":
#     # Test success log
#     log_execution({
#         "pipeline":         "Daily Departments ETL",
#         "status":           "SUCCESS",
#         "rows_processed":   50,
#         "duration_seconds": 1.23
#     })

#     # Test failure log
#     log_execution({
#         "pipeline":         "Daily Departments ETL",
#         "status":           "FAILED",
#         "rows_processed":   0,
#         "duration_seconds": 0.5,
#         "error":            "Table not found"
#     })

#     print("\nAll logs:", get_logs("Daily Departments ETL"))