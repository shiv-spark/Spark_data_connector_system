import sys
import os
from Pipeline.dag_generator import generate_airflow_dag
sys.path.append(
    os.path.dirname(
        os.path.dirname(os.path.abspath(__file__))
    )
)
import json
BASE_DIR = os.path.dirname(
    os.path.abspath(__file__)
)

PIPELINES_FILE = os.path.join(
    BASE_DIR,
    "pipelines.json"
)

# File where all pipeline definitions will be stored
# PIPELINES_FILE = "Pipeline/pipelines.json"


def load_all_pipelines():
    """
    Load all saved pipelines.

    Returns:
        dict
    """

    if not os.path.exists(PIPELINES_FILE):
        return {}

    with open(PIPELINES_FILE, "r") as f:
        return json.load(f)


def save_pipeline(spec):
    """
    Save a pipeline spec.

    Args:
        spec (dict)
    """

    pipelines = load_all_pipelines()

    pipeline_name = spec["pipeline_name"]

    pipelines[pipeline_name] = spec

    # with open(PIPELINES_FILE, "w") as f:
    #     json.dump(
    #         pipelines,
    #         f,
    #         indent=4
    #     )

    # print(f"✓ Pipeline saved: {pipeline_name}")
    with open(PIPELINES_FILE, "w") as f:
        json.dump(
            pipelines,
            f,
            indent=4
        )

    print(f"✓ Pipeline saved: {pipeline_name}")

    generate_airflow_dag(spec)


def load_pipeline(pipeline_name):
    """
    Load one pipeline by name.
    """

    pipelines = load_all_pipelines()

    return pipelines.get(pipeline_name)


def list_pipelines():
    """
    List all saved pipeline names.
    """

    pipelines = load_all_pipelines()

    return list(pipelines.keys())


# ------------------------------------------------
# TEST
# ------------------------------------------------

if __name__ == "__main__":

    sample_pipeline = {
        "pipeline_name": "Department Data ETL",
        "source": "snowflake",
        "target": "local_file_system",
        "table": "departments",
        "schedule": "0 2 * * *",
        "steps": [
            "extract",
            "load"
        ]
    }

    save_pipeline(sample_pipeline)

    print("\nSaved Pipelines:")
    print(list_pipelines())

    print("\nLoaded Pipeline:")
    print(
        load_pipeline(
            "Department Data ETL"
        )
    )



# import sys
# import os

# sys.path.append(
#     os.path.dirname(
#         os.path.dirname(os.path.abspath(__file__))
#     )
# )

# import json

# PIPELINES_FILE = os.path.join(
#     os.path.dirname(os.path.abspath(__file__)),
#     "pipelines.json"
# )


# def load_all_pipelines() -> dict:
#     if not os.path.exists(PIPELINES_FILE):
#         return {}
#     with open(PIPELINES_FILE, "r") as f:
#         return json.load(f)


# def save_pipeline(spec: dict):
#     pipelines = load_all_pipelines()
#     name = spec["pipeline_name"]
#     pipelines[name] = spec
#     with open(PIPELINES_FILE, "w") as f:
#         json.dump(pipelines, f, indent=4)
#     print(f"[pipeline_store] Saved: {name}")


# def load_pipeline(name: str) -> dict | None:
#     return load_all_pipelines().get(name)


# def list_pipelines() -> list[str]:
#     return list(load_all_pipelines().keys())


# def delete_pipeline(name: str) -> bool:
#     """
#     Deletes a pipeline by name.
#     Returns True if deleted, False if not found.
#     """
#     pipelines = load_all_pipelines()
#     if name not in pipelines:
#         print(f"[pipeline_store] Not found: {name}")
#         return False
#     del pipelines[name]
#     with open(PIPELINES_FILE, "w") as f:
#         json.dump(pipelines, f, indent=4)
#     print(f"[pipeline_store] Deleted: {name}")
#     return True


# if __name__ == "__main__":
#     sample = {
#         "pipeline_name": "Daily Departments ETL",
#         "source":        "snowflake",
#         "target":        "local_file_system",
#         "table":         "DEPARTMENTS",
#         "schedule":      "0 2 * * *",
#         "steps":         ["extract", "load"],
#         "filters":       "",
#         "description":   "Exports departments to CSV every night at 2am"
#     }
#     save_pipeline(sample)
#     print("All pipelines:", list_pipelines())
#     print("Loaded:", load_pipeline("Daily Departments ETL"))
#     delete_pipeline("Daily Departments ETL")
#     print("After delete:", list_pipelines())