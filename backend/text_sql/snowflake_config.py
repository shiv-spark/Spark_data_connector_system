"""
Snowflake Configuration for Text-to-SQL Agent
"""

import os

# ============================================================
# SNOWFLAKE CONFIG
# ============================================================
# Read from the environment. Set these in .env - see .env.example.

SNOWFLAKE_CONFIG = {
    "user": os.getenv("SNOWFLAKE_USER", ""),
    "password": os.getenv("SNOWFLAKE_PASSWORD", ""),
    "account": os.getenv("SNOWFLAKE_ACCOUNT", ""),
    "warehouse": os.getenv("SNOWFLAKE_WAREHOUSE", ""),
    "database": os.getenv("SNOWFLAKE_DATABASE", ""),
    "schema": os.getenv("SNOWFLAKE_SCHEMA", "PUBLIC"),
}

# API Config
MODEL_NAME = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")

MAX_RETRIES = int(os.getenv("TEXT_SQL_MAX_RETRIES", "2"))


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
