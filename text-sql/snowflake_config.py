"""
Snowflake Configuration for Text-to-SQL Agent
"""

import os

# ============================================================
# SNOWFLAKE CONFIG
# ============================================================

SNOWFLAKE_CONFIG = {
    "user": "Shiv99",
    "password": "Sparkbrains@1234",
    "account": "XROJPNQ-RO43084",
    "warehouse": "COMPUTE_WH",
    "database": "AGENT_DB",
    "schema": "agents"
}

# API Config
os.environ["GROQ_API_KEY"] = "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"

MODEL_NAME = "llama-3.3-70b-versatile"

MAX_RETRIES = 2


# ============================================================
# INPUT SCREENING
# ============================================================

BLOCK_PATTERNS = [
    r"\bdelete\b",
    r"\bupdate\b",
    r"\binsert\b",
    r"\bdrop\b",
    r"\balter\b",
    r"\btruncate\b",
    r"\bcreate\b",
    r"\bgrant\b",
    r"\brevoke\b",
    r"\bmerge\b",
    r"\bcall\b",
    r"\bexecute\b",
    r"\bexec\b",
    r"\bignore previous instructions\b",
    r"\bbypass\b",
    r"\bsystem prompt\b",
    r"\bdeveloper message\b",
    r"/\*",
    r"\*/",
    r"--",
]

ANALYTICS_HINTS = [
    "show",
    "list",
    "find",
    "top",
    "highest",
    "lowest",
    "count",
    "sum",
    "avg",
    "average",
    "total",
    "report",
    "customers",
    "accounts",
    "transactions",
    "balance",
    "city",
    "date"
]
