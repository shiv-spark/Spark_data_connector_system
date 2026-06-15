"""
PostgreSQL Configuration for Text-to-SQL Agent
"""

import os
from typing import Dict, Any

# Note: Environment variables should be loaded by the main application (main.py)
# This module relies on those environment variables being set

# ============================================================
# POSTGRESQL CONFIG
# ============================================================

# Read from environment variables (consistent with main.py)
def get_postgres_config() -> Dict[str, Any]:
    """Get PostgreSQL configuration from environment variables."""
    return {
        "host": os.getenv("DB_HOST", "localhost"),
        "port": int(os.getenv("DB_PORT", "5432")),
        "database": os.getenv("DB_NAME", "airflow"),
        "user": os.getenv("DB_USER", "postgres"),
        "password": os.getenv("DB_PASSWORD", "spark")
    }

POSTGRES_CONFIG = get_postgres_config()

# ============================================================
# LLM CONFIGURATION
# ============================================================

# Support multiple LLM providers
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "groq").lower()

if LLM_PROVIDER == "groq":
    MODEL_NAME = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
    API_KEY = os.getenv("GROQ_API_KEY", "")
elif LLM_PROVIDER == "openrouter":
    MODEL_NAME = os.getenv("OPENROUTER_MODEL", "meta-llama/llama-3.3-70b-instruct:free")
    API_KEY = os.getenv("OPENROUTER_API_KEY", "")
else:
    MODEL_NAME = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
    API_KEY = os.getenv("GROQ_API_KEY", "")

MAX_RETRIES = int(os.getenv("TEXT_SQL_MAX_RETRIES", "2"))
TEMPERATURE = float(os.getenv("TEXT_SQL_TEMPERATURE", "0.0"))

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
    "date",
    "sales",
    "revenue",
    "product",
    "order",
    "pipeline",
    "ingest",
    "sync",
]

# ============================================================
# METADATA TABLE CONFIG
# ============================================================

METADATA_TABLE_NAME = "text2sql_run_metadata"

METADATA_TABLE_SCHEMA = """
CREATE TABLE IF NOT EXISTS {table_name} (
    run_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    user_question TEXT,
    generated_sql TEXT,
    validation_status VARCHAR(50),
    execution_approved BOOLEAN,
    execution_status VARCHAR(50),
    row_count INTEGER,
    model_name VARCHAR(100),
    prompt_tokens INTEGER,
    completion_tokens INTEGER,
    total_tokens INTEGER,
    llm_latency_seconds NUMERIC(10,2),
    execution_latency_seconds NUMERIC(10,2),
    response_summary TEXT,
    error_message TEXT
);
"""
