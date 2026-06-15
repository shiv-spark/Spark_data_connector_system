def build_execution_plan(pipeline):

    # source = pipeline["source"].lower()
    # target = pipeline["target"].lower()
    source = (
    pipeline["source"]
    .lower()
    .replace(" ", "_")
    )

    target = (
        pipeline["target"]
        .lower()
        .replace(" ", "_")
    )

    plan = []

    # Source
    if source == "snowflake":
        plan.append("extract_from_snowflake")

    # Future:
    # elif source == "api":
    #     plan.append("extract_from_api")

    # Target
    if target == "local_file_system":
        plan.append("save_to_local")

    elif target == "s3":
        plan.append("upload_to_s3")

    elif target == "snowflake":
        plan.append("load_to_snowflake")

    return plan


if __name__ == "__main__":

    pipeline = {
        "source": "snowflake",
        "target": "local_file_system"
    }

    plan = build_execution_plan(pipeline)

    print(plan)

# import sys
# import os

# sys.path.append(
#     os.path.dirname(
#         os.path.dirname(os.path.abspath(__file__))
#     )
# )


# SUPPORTED_ROUTES = {
#     ("snowflake", "local_file_system") : ["extract_from_snowflake", "save_to_local"],
#     ("snowflake", "s3")                : ["extract_from_snowflake", "upload_to_s3"],
#     ("snowflake", "snowflake")         : ["extract_from_snowflake", "load_to_snowflake"],
# }


# def build_execution_plan(pipeline: dict) -> list[str]:
#     """
#     Builds an ordered list of execution steps based on source → target.
#     Injects a transform step if filters are present.

#     Args:
#         pipeline: validated pipeline spec dict

#     Returns:
#         list of step names e.g. ["extract_from_snowflake", "apply_filters", "save_to_local"]
#     """

#     source = pipeline["source"].lower()
#     target = pipeline["target"].lower()
#     route  = (source, target)

#     if route not in SUPPORTED_ROUTES:
#         raise ValueError(
#             f"Unsupported route: {source} → {target}. "
#             f"Supported: {list(SUPPORTED_ROUTES.keys())}"
#         )

#     plan = list(SUPPORTED_ROUTES[route])

#     # Inject transform step between extract and load if filters exist
#     if pipeline.get("filters", "").strip():
#         plan.insert(1, "apply_filters")

#     return plan


# if __name__ == "__main__":
#     # Test all routes
#     for source, target in SUPPORTED_ROUTES:
#         pipeline = {
#             "source":  source,
#             "target":  target,
#             "filters": "AMOUNT > 1000" if target == "local_file_system" else ""
#         }
#         plan = build_execution_plan(pipeline)
#         print(f"{source} → {target}: {plan}")