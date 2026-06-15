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

# Load .env file
load_dotenv()

# Create Groq client
client = Groq(
    api_key=os.getenv("GROQ_API_KEY")
)

# ------------------------------------------------------------------
# SYSTEM PROMPT
# working: Provides clear instructions to the LLM about the expected JSON output format.
# ------------------------------------------------------------------

PIPELINE_SYSTEM_PROMPT = """
You are an ETL pipeline orchestration assistant.

Convert the user's request into a valid JSON pipeline specification.

Return ONLY JSON.

Format:

{
  "pipeline_name": "",
  "source": "",
  "target": "",
  "table": "",
  "schedule": "",
  "steps": []
}
"""

# ------------------------------------------------------------------
# parse_pipeline_prompt()
#
# Input:
#   Natural language request
#
# Example:
#   "Create a daily ETL pipeline that moves orders
#    from Snowflake to S3 every night at 2am"
#
# Output:
#   Python dictionary
# ------------------------------------------------------------------

def parse_pipeline_prompt(user_prompt):

    # Send request to LLM
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {
                "role": "system",
                "content": PIPELINE_SYSTEM_PROMPT
            },
            {
                "role": "user",
                "content": user_prompt
            }
        ],
        temperature=0
    )

    # Extract raw text from LLM response
    raw = response.choices[0].message.content.strip()

    # Remove markdown fences if LLM returns:
    #
    # ```json
    # {...}
    # ```
    #
    raw = re.sub(
        r"^```json|^```|```$",
        "",
        raw,
        flags=re.MULTILINE
    ).strip()

    # Convert JSON string -> Python dict
    spec = json.loads(raw)
    spec["source"] = (
    spec["source"]
    .lower()
    .replace(" ", "_")
        )

    spec["target"] = (
        spec["target"]
        .lower()
        .replace(" ", "_")
        )

    return spec


# ------------------------------------------------------------------
# TEST
#
# Run this file directly:
#
# python -m orchestration.pipeline_parser
#
# ------------------------------------------------------------------

if __name__ == "__main__":

    user_request = (
        "Create a daily ETL pipeline that moves "
        "department data from Snowflake to csv every night at 2am"
    )

    spec = parse_pipeline_prompt(user_request)

    print("\nGenerated Pipeline Spec:\n")

    print(
        json.dumps(
            spec,
            indent=4
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
# import re
# from groq import Groq
# from dotenv import load_dotenv
# from metadata.catalog_builder import build_catalog

# load_dotenv()

# client = Groq(api_key=os.getenv("GROQ_API_KEY"))

# VALID_SOURCES  = ["snowflake"]
# VALID_TARGETS  = ["snowflake", "local_file_system", "s3"]


# def _build_system_prompt(catalog: dict) -> str:
#     """
#     Builds system prompt with real schema catalog injected
#     so the LLM knows exact table names, columns, and relationships.
#     """

#     tables = {k: v for k, v in catalog.items() if not k.startswith("_")}
#     relationships = catalog.get("_relationships", {})

#     schema_lines = []
#     for table, meta in tables.items():
#         desc = meta.get("description", "")
#         schema_lines.append(f"  {table} — {desc}")

#     rel_lines = []
#     if relationships:
#         for fk, ref in relationships.items():
#             rel_lines.append(f"  {fk} → {ref}")

#     schema_summary  = "\n".join(schema_lines)
#     rel_summary     = "\n".join(rel_lines) if rel_lines else "  none"

#     return f"""
# You are an ETL pipeline orchestration assistant with full knowledge of the database schema.

# Convert the user's plain-English request into a valid JSON pipeline specification.

# Rules:
#   - "pipeline_name" : short descriptive name
#   - "source"        : must be one of {VALID_SOURCES}
#   - "target"        : must be one of {VALID_TARGETS}
#   - "table"         : must exactly match a table name from the schema below (case-sensitive)
#   - "schedule"      : cron expression e.g. "0 2 * * *" for 2am daily, "0 * * * *" for hourly
#                       use "manual" if no schedule mentioned
#   - "steps"         : list from ["extract", "transform", "load"]
#   - "filters"       : optional SQL WHERE clause condition e.g. "AMOUNT > 1000"
#   - "description"   : plain English summary of what this pipeline does

# Return ONLY valid JSON, no explanation, no markdown, no code fences.

# Available tables:
# {schema_summary}

# Relationships:
# {rel_summary}

# Example output:
# {{
#   "pipeline_name": "Daily Orders ETL",
#   "source": "snowflake",
#   "target": "local_file_system",
#   "table": "ORDERS",
#   "schedule": "0 2 * * *",
#   "steps": ["extract", "load"],
#   "filters": "",
#   "description": "Exports orders data from Snowflake to CSV every night at 2am"
# }}
# """


# def parse_pipeline_prompt(user_prompt: str) -> dict:
#     """
#     Uses LLM + schema catalog to parse a plain-English pipeline request.

#     Returns structured pipeline spec dict.
#     """

#     catalog       = build_catalog()
#     system_prompt = _build_system_prompt(catalog)

#     response = client.chat.completions.create(
#         model="llama-3.3-70b-versatile",
#         messages=[
#             {"role": "system", "content": system_prompt},
#             {"role": "user",   "content": user_prompt}
#         ],
#         temperature=0
#     )

#     raw = response.choices[0].message.content.strip()
#     raw = re.sub(r"^```json|^```|```$", "", raw, flags=re.MULTILINE).strip()

#     try:
#         spec = json.loads(raw)
#     except json.JSONDecodeError as e:
#         print(f"[pipeline_parser] JSON parse error: {e}\nRaw:\n{raw}")
#         raise

#     return spec


# if __name__ == "__main__":
#     spec = parse_pipeline_prompt(
#         "Create a daily ETL pipeline that moves department data "
#         "from Snowflake to CSV every night at 2am"
#     )
#     print(json.dumps(spec, indent=4))