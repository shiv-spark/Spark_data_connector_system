

import re
import json
import httpx
from pydantic import BaseModel
from typing import Optional, List
import httpx
import os
import sys
from fastapi.middleware.cors import CORSMiddleware
from fastapi import FastAPI, Query, HTTPException
from pydantic import BaseModel
import psycopg2
from psycopg2 import sql
import requests
import threading
import time
from requests.auth import HTTPBasicAuth
from typing import Optional
from utils.dag_generator import create_dag_file, delete_dag_file, list_dag_files
from connectors.csv_connector import csv_connector
from connectors.excel_connector import excel_connector
from connectors.google_sheets_connector import google_sheet_connector
from connectors.api_connector import api_connector
from utils.ingest_runner import run_ingestion
import smtplib
from typing import List
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from pathlib import Path
from dotenv import load_dotenv
from datetime import datetime
from connectors.postgres_connector import postgres_connector
from connectors.s3_connector import s3_connector
from connectors.snowflake_connector import snowflake_connector  # ADDED
from connectors.salesforce_connector import salesforce_connector
from connectors.hubspot_connector import hubspot_connector
from connectors.zoho_connector import zoho_connector
import polars as pl

from fastapi import FastAPI
from agent.agent_router import router as agent_router
from sql_executors import get_executor, is_sql_capable, get_supported_types
from sql_executors.base import QueryError
from testers import get_tester



# Import Data Generator router
try:
    from data_generator.router import router as data_gen_router
    DATA_GEN_AVAILABLE = True
    print("✓ Data Generator router imported successfully")
except ImportError as e:
    import traceback
    print(f"Warning: Data Generator module not available: {e}")
    print(f"Traceback: {traceback.format_exc()}")
    DATA_GEN_AVAILABLE = False
    data_gen_router = None



try:
    from quality.router import router as quality_router
    QUALITY_AVAILABLE = True
    print("✓ Data Quality router imported successfully")
except ImportError as e:
    import traceback
    print(f"Warning: Data Quality module not available: {e}")
    print(f"Traceback: {traceback.format_exc()}")
    QUALITY_AVAILABLE = False
    quality_router = None

try:
    from reverse_etl.router import router as reverse_etl_router
    REVERSE_ETL_AVAILABLE = True
    print("✓ Reverse ETL router imported successfully")
except ImportError as e:
    import traceback
    print(f"Warning: Reverse ETL module not available: {e}")
    print(f"Traceback: {traceback.format_exc()}")
    REVERSE_ETL_AVAILABLE = False
    reverse_etl_router = None

try:
    from lineage.router import router as lineage_router
    LINEAGE_AVAILABLE = True
    print("✓ Data Lineage router imported successfully")
except ImportError as e:
    import traceback
    print(f"Warning: Data Lineage module not available: {e}")
    print(f"Traceback: {traceback.format_exc()}")
    LINEAGE_AVAILABLE = False
    lineage_router = None

# Load environment variables from project root .env file
project_root = Path(__file__).resolve().parent.parent
env_path = project_root / ".env"
if env_path.exists():
    load_dotenv(env_path)
else:
    load_dotenv()

# Import Text-to-SQL router (after loading env vars)
try:
    from text_sql.router import router as text2sql_router
    TEXT2SQL_AVAILABLE = True
    print("✓ Text-to-SQL router imported successfully")
except ImportError as e:
    import traceback
    print(f"Warning: Text-to-SQL module not available: {e}")
    print(f"Traceback: {traceback.format_exc()}")
    TEXT2SQL_AVAILABLE = False


app = FastAPI()

def _rows_to_dicts(cursor):
    """Convert psycopg2 cursor result to list of dictionaries"""
    columns = [desc[0] for desc in cursor.description]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]

EMAIL_SENDER = os.getenv("EMAIL_SENDER")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")
EMAIL_RECEIVER = os.getenv("EMAIL_RECEIVER")
SMTP_HOST      = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))

def send_failure_email(dag_id: str, run_id: str, error: str = "", status: str = "failed"):
    try:
        msg = MIMEMultipart()
        msg["From"]    = EMAIL_SENDER
        msg["To"]      = EMAIL_RECEIVER
        msg["Subject"] = f"Pipeline {status.upper()}: {dag_id}"

        emoji = "✅" if status == "success" else "❌"
        body = f"""
Pipeline {status.upper()} Alert
──────────────────────────────
{emoji} DAG ID : {dag_id}
   Run ID : {run_id}
   Status : {status.upper()}
   {f'Error  : {error}' if status == 'failed' else ''}

Airflow UI: http://localhost:8081
        """
        msg.attach(MIMEText(body, "plain"))
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.starttls()
            server.login(EMAIL_SENDER, EMAIL_PASSWORD)
            server.sendmail(EMAIL_SENDER, EMAIL_RECEIVER, msg.as_string())
        print(f"Alert email sent for: {dag_id} — {status.upper()}")
    except Exception as e:
        print(f"Email send failed: {e}")

#################################

app.include_router(agent_router)

# Include Text-to-SQL router if available
if TEXT2SQL_AVAILABLE:
    # Router already has prefix="/text2sql" defined in router.py
    app.include_router(text2sql_router)
    print("✓ Text-to-SQL router loaded")
    # Log available routes
    print("✓ Text-to-SQL routes registered:")
    for route in text2sql_router.routes:
        if hasattr(route, 'methods'):
            print(f"    {list(route.methods)} {route.path}")
else:
    print("⚠ Text-to-SQL router not available - check import errors above")
    
# Include Data Quality router if available
if QUALITY_AVAILABLE:
    app.include_router(quality_router)
    print("✓ Data Quality router loaded")
    print("✓ Data Quality routes registered:")
    for route in quality_router.routes:
        if hasattr(route, 'methods'):
            print(f"    {list(route.methods)} {route.path}")
else:
    print("⚠ Data Quality router not available - check import errors above")

# Include Data Lineage router if available
if LINEAGE_AVAILABLE:
    app.include_router(lineage_router)
    print("✓ Data Lineage router loaded")
    print("✓ Data Lineage routes registered:")
    for route in lineage_router.routes:
        if hasattr(route, 'methods'):
            print(f"    {list(route.methods)} {route.path}")
else:
    print("⚠ Data Lineage router not available - check import errors above")

# Include Reverse ETL router if available
if REVERSE_ETL_AVAILABLE:
    app.include_router(reverse_etl_router)
    print("✓ Reverse ETL router loaded")
    print("✓ Reverse ETL routes registered:")
    for route in reverse_etl_router.routes:
        if hasattr(route, 'methods'):
            print(f"    {list(route.methods)} {route.path}")
else:
    print("⚠ Reverse ETL router not available - check import errors above")

# Include SQL Editor router
from sql_router import router as sql_router
app.include_router(sql_router)
print("✓ SQL Editor router loaded")

# Include Data Generator router if available
if DATA_GEN_AVAILABLE:
    app.include_router(data_gen_router)
    print("✓ Data Generator router loaded")
    print("✓ Data Generator routes registered:")
    for route in data_gen_router.routes:
        if hasattr(route, 'methods'):
            print(f"    {list(route.methods)} {route.path}")
else:
    print("⚠ Data Generator router not available - check import errors above")

# Startup event to log all registered routes
@app.on_event("startup")
async def log_routes():
    # Check and regenerate business context if the Snowflake schema changed.
    # This opens a Snowflake connection and can trigger LLM calls to rebuild
    # business_context.json, so it is opt-in rather than run on every boot.
    if os.getenv("SNOWFLAKE_SCHEMA_CHECK_ON_STARTUP", "false").strip().lower() in ("1", "true", "yes"):
        try:
            from text_sql.snowflake_schema_manager import check_schema_changes
            print("\n" + "="*60)
            print("CHECKING FOR SCHEMA CHANGES...")
            print("="*60)
            regenerated = check_schema_changes()
            if regenerated:
                print("✓ Business context regenerated with updated schema")
            else:
                print("✓ No schema changes detected")
        except ImportError as e:
            print(f"⚠ Schema manager not available: {e}")
        except Exception as e:
            print(f"⚠ Schema check failed: {e}")


    print("\n" + "="*60)
    print("REGISTERED ROUTES:")
    print("="*60)
    for route in app.routes:
        if hasattr(route, 'methods'):
            methods = list(route.methods)
            if 'GET' in methods or 'POST' in methods or 'PUT' in methods or 'DELETE' in methods:
                print(f"  {methods} {route.path}")
    print("="*60 + "\n")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─────────────────────────────────────────────
# GLOBAL CONFIG
# ─────────────────────────────────────────────
AIRFLOW_BASE = os.getenv("AIRFLOW_BASE_URL", "http://airflow-webserver:8080/api/v1/dags")

# AIRFLOW_AUTH = HTTPBasicAuth("admin", "admin")
AIRFLOW_AUTH = HTTPBasicAuth(
    os.getenv("AIRFLOW_USER", "admin"),
    os.getenv("AIRFLOW_PASSWORD", "admin")
)

DAG_MAP = {
    "csv":           "dynamic_connector_dag",   
    "excel":         "dynamic_connector_dag",
    "api":           "dynamic_connector_dag",
    "google_sheets": "dynamic_connector_dag",
    "snowflake":     "dynamic_connector_dag",  
}

OPTION_MAP = {
    "1": "append",
    "2": "overwrite",
    "3": "create_new"
}

# ─────────────────────────────────────────────
# DB CONFIG
# ─────────────────────────────────────────────
DB_CONFIG = {
    "host":     os.getenv("DB_HOST",     "postgres"),
    "database": os.getenv("DB_NAME",     "airflow"),
    "user":     os.getenv("DB_USER",     "airflow"),
    "password": os.getenv("DB_PASSWORD", "airflow"),
    "port":     os.getenv("DB_PORT",     "5432")
}

def get_conn():
    return psycopg2.connect(**DB_CONFIG)


class ConnectionRequest(BaseModel):
    name: str
    source_type: str
    config: dict = {}

def ensure_connections_table():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS saved_connections (
            id SERIAL PRIMARY KEY,
            name VARCHAR(160) NOT NULL,
            source_type VARCHAR(60) NOT NULL,
            config JSONB NOT NULL DEFAULT '{}'::jsonb,
            status VARCHAR(30) NOT NULL DEFAULT 'created',
            created_at TIMESTAMP DEFAULT NOW(),
            updated_at TIMESTAMP DEFAULT NOW()
        )
    """)
    conn.commit()
    cur.close()
    conn.close()


def ensure_sql_tables():
    """Create SQL query history and saved queries tables if they don't exist."""
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS sql_query_history (
                query_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                connection_id INTEGER NOT NULL REFERENCES saved_connections(id),
                user_id INTEGER NOT NULL REFERENCES app_users(id),
                query_text TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'success',
                row_count INTEGER,
                error_message TEXT,
                duration_ms INTEGER,
                executed_at TIMESTAMPTZ DEFAULT now()
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS sql_saved_queries (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                connection_id INTEGER NOT NULL REFERENCES saved_connections(id),
                user_id INTEGER NOT NULL REFERENCES app_users(id),
                name TEXT NOT NULL,
                query_text TEXT NOT NULL,
                created_at TIMESTAMPTZ DEFAULT NOW(),
                updated_at TIMESTAMPTZ DEFAULT NOW()
            )
        """)
        cur.execute("CREATE INDEX IF NOT EXISTS idx_sql_query_history_user ON sql_query_history(user_id)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_sql_query_history_connection ON sql_query_history(connection_id)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_sql_query_history_executed_at ON sql_query_history(executed_at DESC)")
        conn.commit()
    except Exception as e:
        print(f"Error creating SQL tables: {e}")
        conn.rollback()
    finally:
        cur.close()
        conn.close()

def _public_connection(row: dict) -> dict:
    config = row.get("config") or {}
    safe_config = dict(config)
    for key in list(safe_config.keys()):
        lower = key.lower()
        if "password" in lower or "secret" in lower or "token" in lower or ("key" in lower and "path" not in lower):
            safe_config[key] = "********"
    return {**row, "config": safe_config}

@app.get("/connections")
def list_connections():
    ensure_connections_table()
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        SELECT id, name, source_type, config, status, created_at, updated_at
        FROM saved_connections
        ORDER BY updated_at DESC, id DESC
    """)
    rows = _rows_to_dicts(cur)
    cur.close()
    conn.close()
    return {"connections": [_public_connection(row) for row in rows]}



@app.post("/connections")
def save_connection(req: ConnectionRequest):
    ensure_connections_table()
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO saved_connections (name, source_type, config, status, updated_at)
        VALUES (%s, %s, %s::jsonb, 'connected', NOW())
        RETURNING id, name, source_type, config, status, created_at, updated_at
    """, (req.name, req.source_type, json.dumps(req.config)))
    row = dict(zip([d[0] for d in cur.description], cur.fetchone()))
    conn.commit()
    cur.close()
    conn.close()
    return _public_connection(row)


@app.get("/connections/{connection_id}")
def get_connection(connection_id: int):
    ensure_connections_table()
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        SELECT id, name, source_type, config, status, created_at, updated_at
        FROM saved_connections WHERE id = %s
    """, (connection_id,))
    row = cur.fetchone()
    if not row:
        cur.close()
        conn.close()
        raise HTTPException(status_code=404, detail="Connection not found")
    data = dict(zip([d[0] for d in cur.description], row))
    cur.close()
    conn.close()
    return _public_connection(data)




@app.delete("/connections/{connection_id}")
def delete_connection(connection_id: int):
    ensure_connections_table()
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("DELETE FROM saved_connections WHERE id = %s RETURNING id", (connection_id,))
    deleted = cur.fetchone()
    conn.commit()
    cur.close()
    conn.close()
    if not deleted:
        raise HTTPException(status_code=404, detail="Connection not found")
    return {"status": "DELETED", "id": connection_id}

@app.put("/connections/{connection_id}")
def update_connection(connection_id: int, req: ConnectionRequest):
    ensure_connections_table()
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        UPDATE saved_connections 
        SET name = %s, source_type = %s, config = %s::jsonb, status = 'connected', updated_at = NOW()
        WHERE id = %s
        RETURNING id, name, source_type, config, status, created_at, updated_at
    """, (req.name, req.source_type, json.dumps(req.config), connection_id))
    row = cur.fetchone()
    if not row:
        cur.close()
        conn.close()
        raise HTTPException(status_code=404, detail="Connection not found")
    conn.commit()
    cur.close()
    conn.close()
    return _public_connection(dict(zip([d[0] for d in cur.description], row)))

class ConnectionTestRequest(BaseModel):
    source_type: str
    config: dict = {}
    test_write: bool = False


@app.post("/connectors/test")
def test_connector(req: ConnectionTestRequest):
    """
    Test a connector configuration without saving.
    
    Validates connectivity, authentication, and permissions for:
    - snowflake
    - postgres
    - mysql
    - oracle
    - mongodb
    - s3
    - api
    - salesforce
    - hubspot
    - zoho
    - local_folder
    - google_sheet
    - figma_design
    """
    import os

    source_type = req.source_type.lower().strip()

    # Handle source types that don't need network testing
    if source_type == "local_folder":
        base_path = req.config.get("base_path", "")
        if not base_path:
            return {
                "success": False,
                "message": "Missing required field: base_path",
                "category": "connectivity",
                "details": {}
            }
        if os.path.isdir(base_path):
            return {
                "success": True,
                "message": f"Directory exists and is accessible: {base_path}",
                "category": "success",
                "details": {"base_path": base_path, "type": "folder"}
            }
        elif os.path.isfile(base_path):
            return {
                "success": True,
                "message": f"File exists and is accessible: {base_path}",
                "category": "success",
                "details": {"base_path": base_path, "type": "file"}
            }
        else:
            return {
                "success": False,
                "message": f"Path does not exist or is not accessible: {base_path}",
                "category": "not_found",
                "details": {"base_path": base_path}
            }

    
    if source_type == "google_sheet":
        sheet_url = req.config.get("sheet_url", "")
        if not sheet_url:
            return {
                "success": False,
                "message": "Missing required field: sheet_url",
                "category": "connectivity",
                "details": {}
            }
        if "docs.google.com" in sheet_url or "spreadsheets" in sheet_url:
            return {
                "success": True,
                "message": "Google Sheet URL format appears valid",
                "category": "success",
                "details": {"sheet_url": "********"}
            }
        return {
            "success": False,
            "message": "Invalid Google Sheet URL format",
            "category": "connectivity",
            "details": {}
        }
    
    if source_type == "figma_design":
        figma_url = req.config.get("figma_file_url", "")
        if not figma_url:
            return {
                "success": False,
                "message": "Missing required field: figma_file_url",
                "category": "connectivity",
                "details": {}
            }
        if "figma.com" in figma_url:
            return {
                "success": True,
                "message": "Figma URL format appears valid",
                "category": "success",
                "details": {"figma_file_url": "********"}
            }
        return {
            "success": False,
            "message": "Invalid Figma URL format",
            "category": "connectivity",
            "details": {}
        }
    
    tester = get_tester(source_type)
    if tester is None:
        return {
            "success": False,
            "message": f"Unknown source_type: {source_type}. Valid types: snowflake, postgres, mysql, oracle, mongodb, s3, api, salesforce, hubspot, zoho, local_folder, google_sheet, figma_design",
            "category": "connectivity",
            "details": {}
        }

    try:
        return tester(req.config, req.test_write)
    except Exception as e:
        return {
            "success": False,
            "message": f"Test failed: {str(e)}",
            "category": "connectivity",
            "details": {}
        }

# ─────────────────────────────────────────────
# SNOWFLAKE CONNECTION TEST
# ─────────────────────────────────────────────

class SnowflakeTestRequest(BaseModel):
    account: str
    user: str
    password: str
    warehouse: str
    database: str
    schema: str = "PUBLIC"
    role: Optional[str] = None

@app.post("/test_snowflake_connection")
def test_snowflake_conn(req: SnowflakeTestRequest):
    """Test Snowflake connection."""
    try:
        from connectors.snowflake_connector import test_snowflake_connection
        success, message = test_snowflake_connection(
            account=req.account,
            user=req.user,
            password=req.password,
            warehouse=req.warehouse,
            database=req.database,
            schema=req.schema,
            role=req.role
        )
        return {"success": success, "message": message}
    except Exception as e:
        return {"success": False, "message": str(e)}

# ─────────────────────────────────────────────
# ROOT
# ─────────────────────────────────────────────

@app.get("/")
def root():
    return {"message": "SparkBrains Data Connector API Running — Ready to ingest data into Airflow pipelines!"}


# ─────────────────────────────────────────────
# DESTINATIONS — supported ingest targets (Postgres/MySQL/Oracle/MongoDB/
# Snowflake) so the frontend can render a destination picker (dropdown +
# manual-entry field list) instead of hardcoding Postgres. Actual
# credentials still come from either a saved_connections id
# (destination_connection_id) or an inline destination_config — see
# backend/destinations/__init__.py.
# ─────────────────────────────────────────────

@app.get("/destinations/types")
def get_destination_types():
    from destinations import list_supported_destinations
    return {"destinations": list_supported_destinations()}

# ─────────────────────────────────────────────
# VALIDATION
# ─────────────────────────────────────────────

def validate_inputs(option, table_name, file_path: str | None = None):
    if option not in ["1", "2", "3"]:
        raise HTTPException(status_code=400, detail="Invalid option. Use 1, 2, or 3")
    if not table_name:
        raise HTTPException(status_code=400, detail="table_name is required")
    if file_path is not None:
         if not file_path.strip():
             raise HTTPException(status_code=400, detail="file_path is required and cannot be empty")
         if not os.path.exists(file_path):
             raise HTTPException(status_code=400, detail=f"file_path does not exist on the server: {file_path}")

# ─────────────────────────────────────────────
# CSV
# ─────────────────────────────────────────────

class CSVRequest(BaseModel):
    file_path: str
    option: str
    table_name: str | None = None
    sync_mode:  str        = "full"
    incremental_column: str | None = None
    connection_id: int | None = None   # informational only — file_path is already fully resolved client-side
    pipeline_id: str | None = None     # set by the scheduler DAG so metrics/logs stay keyed by the real pipeline
    # ── optional data-quality gate, run right after load_to_db() succeeds ──
    quality_connection_id: int | None = None   # saved_connections id to run checks against (usually the warehouse this loads into)
    quality_config: dict | None = None          # same shape as quality.router.TableCheckSpec, minus table_name
    quality_on_fail: str = "warn"               # "warn" (log only) | "block" (mark this run FAILED)
    # ── optional PRE-INGEST dataframe-level quality gate, runs BEFORE load_to_db() ──
    df_quality_config: dict | None = None       # see quality.dataframe_checks.run_dataframe_quality_checks
    df_quality_on_fail: str = "warn"             # "warn" (log only) | "block" (skip ingest entirely)
    custom_schema: dict | None = None          # optional {"column": "type"} to enforce a user-defined schema (type in integer|float|boolean|date|timestamp|text|json) instead of auto-detected types
    destination_type: str = "postgres"           # postgres | mysql | oracle | mongodb | snowflake
    destination_connection_id: int | None = None  # saved_connections id to use as the destination (takes priority over destination_config)
    destination_config: dict | None = None        # inline destination config (host/user/password, or engine-specific fields) — used when destination_connection_id is not supplied


def _resolve_saved_connection(connection_id: int) -> tuple[dict, str]:
    """Raw (unmasked) config for a saved connection — /connections list masks
    passwords/secrets/tokens for display, so anything that actually needs to
    connect (ingest, preview) must fetch the real values via this instead."""
    ensure_connections_table()
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT config, source_type FROM saved_connections WHERE id = %s", (connection_id,))
    row = cur.fetchone()
    cur.close()
    conn.close()
    if not row:
        raise HTTPException(status_code=404, detail="Connection not found")
    config, source_type = row
    config = config if isinstance(config, dict) else json.loads(config)
    return config, source_type


@app.post("/ingest_csv")
def ingest_csv(req: CSVRequest):
    validate_inputs(req.option, req.table_name, req.file_path)
    return run_ingestion(
        csv_connector,
        req.file_path,
        "CSVConnector",
        req.file_path,
        option=req.option,
        table_name=req.table_name,
        pipeline_id=req.pipeline_id,
        sync_mode          = req.sync_mode,
        incremental_column = req.incremental_column,
        quality_connection_id = req.quality_connection_id,
        quality_config         = req.quality_config,
        quality_on_fail        = req.quality_on_fail,
        df_quality_config      = req.df_quality_config,
        df_quality_on_fail     = req.df_quality_on_fail,
        custom_schema          = req.custom_schema,
        destination_type           = req.destination_type,
        destination_connection_id  = req.destination_connection_id,
        destination_config         = req.destination_config,
    )

# ─────────────────────────────────────────────
# EXCEL
# ─────────────────────────────────────────────

class ExcelRequest(BaseModel):
    file_path: str
    option: str
    table_name: str | None = None
    sync_mode:  str        = "full"
    incremental_column: str | None = None
    sheet_name: str | None = None      # ← NEW
    all_sheets: bool = False
    connection_id: int | None = None   # informational only — file_path is already fully resolved client-side
    pipeline_id: str | None = None     # set by the scheduler DAG so metrics/logs stay keyed by the real pipeline
    # ── optional data-quality gate, run right after load_to_db() succeeds ──
    quality_connection_id: int | None = None   # saved_connections id to run checks against (usually the warehouse this loads into)
    quality_config: dict | None = None          # same shape as quality.router.TableCheckSpec, minus table_name
    quality_on_fail: str = "warn"               # "warn" (log only) | "block" (mark this run FAILED)
    # ── optional PRE-INGEST dataframe-level quality gate, runs BEFORE load_to_db() ──
    df_quality_config: dict | None = None       # see quality.dataframe_checks.run_dataframe_quality_checks
    df_quality_on_fail: str = "warn"             # "warn" (log only) | "block" (skip ingest entirely)
    custom_schema: dict | None = None          # optional {"column": "type"} to enforce a user-defined schema (type in integer|float|boolean|date|timestamp|text|json) instead of auto-detected types
    destination_type: str = "postgres"           # postgres | mysql | oracle | mongodb | snowflake
    destination_connection_id: int | None = None  # saved_connections id to use as the destination (takes priority over destination_config)
    destination_config: dict | None = None        # inline destination config (host/user/password, or engine-specific fields) — used when destination_connection_id is not supplied


@app.post("/ingest_excel")
def ingest_excel(req: ExcelRequest):
    validate_inputs(req.option, req.table_name, req.file_path)
    return run_ingestion(
        excel_connector,
        req.file_path,
        "ExcelConnector",
        req.file_path,
        req.sheet_name,
        req.all_sheets,
        option=req.option,
        table_name=req.table_name,
        pipeline_id=req.pipeline_id,
        sync_mode          = req.sync_mode,
        incremental_column = req.incremental_column,
        quality_connection_id = req.quality_connection_id,
        quality_config         = req.quality_config,
        quality_on_fail        = req.quality_on_fail,
        df_quality_config      = req.df_quality_config,
        df_quality_on_fail     = req.df_quality_on_fail,
        custom_schema          = req.custom_schema,
        destination_type           = req.destination_type,
        destination_connection_id  = req.destination_connection_id,
        destination_config         = req.destination_config,
    )

# ─────────────────────────────────────────────
# GOOGLE SHEETS
# ─────────────────────────────────────────────

class GoogleSheetRequest(BaseModel):
    sheet_url: str = ""
    option: str
    table_name: str | None = None
    sync_mode:  str        = "full"
    incremental_column: str | None = None
    connection_id: int | None = None   # use a saved connection's sheet_url instead of the field above
    pipeline_id: str | None = None     # set by the scheduler DAG so metrics/logs stay keyed by the real pipeline
    # ── optional data-quality gate, run right after load_to_db() succeeds ──
    quality_connection_id: int | None = None   # saved_connections id to run checks against (usually the warehouse this loads into)
    quality_config: dict | None = None          # same shape as quality.router.TableCheckSpec, minus table_name
    quality_on_fail: str = "warn"               # "warn" (log only) | "block" (mark this run FAILED)
    # ── optional PRE-INGEST dataframe-level quality gate, runs BEFORE load_to_db() ──
    df_quality_config: dict | None = None       # see quality.dataframe_checks.run_dataframe_quality_checks
    df_quality_on_fail: str = "warn"             # "warn" (log only) | "block" (skip ingest entirely)
    custom_schema: dict | None = None          # optional {"column": "type"} to enforce a user-defined schema (type in integer|float|boolean|date|timestamp|text|json) instead of auto-detected types
    destination_type: str = "postgres"           # postgres | mysql | oracle | mongodb | snowflake
    destination_connection_id: int | None = None  # saved_connections id to use as the destination (takes priority over destination_config)
    destination_config: dict | None = None        # inline destination config (host/user/password, or engine-specific fields) — used when destination_connection_id is not supplied


@app.post("/ingest_google_sheet")
def ingest_google_sheet(req: GoogleSheetRequest):
    validate_inputs(req.option, req.table_name)
    sheet_url = req.sheet_url
    if req.connection_id:
        cfg, _ = _resolve_saved_connection(req.connection_id)
        sheet_url = cfg.get("sheet_url", "")
    return run_ingestion(
        google_sheet_connector,
        sheet_url,
        "GoogleSheetsConnector",
        sheet_url,
        "pandas",
        option=req.option,
        table_name=req.table_name,
        pipeline_id=req.pipeline_id,
        sync_mode          = req.sync_mode,
        incremental_column = req.incremental_column,
        quality_connection_id = req.quality_connection_id,
        quality_config         = req.quality_config,
        quality_on_fail        = req.quality_on_fail,
        df_quality_config      = req.df_quality_config,
        df_quality_on_fail     = req.df_quality_on_fail,
        custom_schema          = req.custom_schema,
        destination_type           = req.destination_type,
        destination_connection_id  = req.destination_connection_id,
        destination_config         = req.destination_config,
    )

# ─────────────────────────────────────────────
# Multi-source Google Sheets
# ─────────────────────────────────────────────

class GoogleSheetMultiRequest(BaseModel):
    file_path:  str              # URL file  path
    option:     str
    table_name: str | None = None
    engine:     str        = "pandas"
    sync_mode:  str        = "full"
    incremental_column: str | None = None
    pipeline_id: str | None = None     # set by the scheduler DAG so metrics/logs stay keyed by the real pipeline
    # ── optional data-quality gate, run right after load_to_db() succeeds ──
    quality_connection_id: int | None = None   # saved_connections id to run checks against (usually the warehouse this loads into)
    quality_config: dict | None = None          # same shape as quality.router.TableCheckSpec, minus table_name
    quality_on_fail: str = "warn"               # "warn" (log only) | "block" (mark this run FAILED)
    # ── optional PRE-INGEST dataframe-level quality gate, runs BEFORE load_to_db() ──
    df_quality_config: dict | None = None       # see quality.dataframe_checks.run_dataframe_quality_checks
    df_quality_on_fail: str = "warn"             # "warn" (log only) | "block" (skip ingest entirely)
    custom_schema: dict | None = None          # optional {"column": "type"} to enforce a user-defined schema (type in integer|float|boolean|date|timestamp|text|json) instead of auto-detected types
    destination_type: str = "postgres"           # postgres | mysql | oracle | mongodb | snowflake
    destination_connection_id: int | None = None  # saved_connections id to use as the destination (takes priority over destination_config)
    destination_config: dict | None = None        # inline destination config (host/user/password, or engine-specific fields) — used when destination_connection_id is not supplied


@app.post("/ingest_google_sheets_multi")
def ingest_google_sheets_multi(req: GoogleSheetMultiRequest):
    """
    Read multiple Google Sheet URLs from a file and ingest all.
    Supported: .txt, .csv, .json, .xlsx
    """
    validate_inputs(req.option, req.table_name)

    from connectors.google_sheets_connector import google_sheets_multi_connector

    return run_ingestion(
        google_sheets_multi_connector,
        req.file_path,
        "GoogleSheetsMultiConnector",
        req.file_path,
        req.engine,
        option             = req.option,
        table_name         = req.table_name,
        pipeline_id        = req.pipeline_id,
        sync_mode          = req.sync_mode,
        incremental_column = req.incremental_column,
        quality_connection_id = req.quality_connection_id,
        quality_config         = req.quality_config,
        quality_on_fail        = req.quality_on_fail,
        df_quality_config      = req.df_quality_config,
        df_quality_on_fail     = req.df_quality_on_fail,
        custom_schema          = req.custom_schema,
        destination_type           = req.destination_type,
        destination_connection_id  = req.destination_connection_id,
        destination_config         = req.destination_config,
    )

# ─────────────────────────────────────────────
# API CONNECTOR
# ─────────────────────────────────────────────

class APIRequest(BaseModel):
    url: str = ""
    method: str = "GET"
    option: str
    table_name: str | None = None
    sync_mode: str = "full"
    incremental_column: str | None = None
    connection_id: int | None = None   # use a saved connection's URL + auth instead of the fields below
    pipeline_id: str | None = None     # set by the scheduler DAG so metrics/logs stay keyed by the real pipeline
    # ── optional data-quality gate, run right after load_to_db() succeeds ──
    quality_connection_id: int | None = None   # saved_connections id to run checks against (usually the warehouse this loads into)
    quality_config: dict | None = None          # same shape as quality.router.TableCheckSpec, minus table_name
    quality_on_fail: str = "warn"               # "warn" (log only) | "block" (mark this run FAILED)
    # ── optional PRE-INGEST dataframe-level quality gate, runs BEFORE load_to_db() ──
    df_quality_config: dict | None = None       # see quality.dataframe_checks.run_dataframe_quality_checks
    df_quality_on_fail: str = "warn"             # "warn" (log only) | "block" (skip ingest entirely)
    custom_schema: dict | None = None          # optional {"column": "type"} to enforce a user-defined schema (type in integer|float|boolean|date|timestamp|text|json) instead of auto-detected types
    destination_type: str = "postgres"           # postgres | mysql | oracle | mongodb | snowflake
    destination_connection_id: int | None = None  # saved_connections id to use as the destination (takes priority over destination_config)
    destination_config: dict | None = None        # inline destination config (host/user/password, or engine-specific fields) — used when destination_connection_id is not supplied


    # ── auth ──
    auth_type: str = "none"          # none | api_key_header | bearer | basic | api_key_query
    api_key: str | None = None
    header_name: str = "Authorization"
    bearer_token: str | None = None
    basic_user: str | None = None
    basic_password: str | None = None
    query_param_name: str = "api_key"

    # ── request shaping ──
    extra_headers: dict | None = None
    extra_params: dict | None = None
    body: dict | None = None

    # ── user-specific custom fields (pUserName, pPoNum, etc.) ──
    custom_fields: dict | None = None
    custom_fields_location: str = "body"
    custom_fields_path: str | None = None

    # ── response shaping ──
    records_path: str | None = None
    flatten: bool = True

    # ── pagination ──
    pagination_type: str = "none"    # none | page | offset_limit | body_bounds
    max_pages: int = 500
    page_param: str = "page"
    page_start: int = 1
    offset_param: str = "offset"
    limit_param: str = "limit"
    limit_size: int = 100
    body_pagination_path: str | None = None
    lower_bound_field: str = "lowerBound"
    higher_bound_field: str = "higherBound"
    initial_lower_bound: int = 0
    step_size: int = 1000
    timeout: int = 30

@app.post("/ingest_api")
def ingest_api(req: APIRequest):
    validate_inputs(req.option, req.table_name)


    connector_kwargs = req.model_dump(
        exclude={"option", "table_name", "sync_mode", "incremental_column", "connection_id",
                 "pipeline_id",
                 "quality_connection_id", "quality_config", "quality_on_fail",
                 "df_quality_config", "df_quality_on_fail", "custom_schema"}
    )

    if req.connection_id:
        cfg, _ = _resolve_saved_connection(req.connection_id)
        connector_kwargs["url"] = cfg.get("base_url", "")
        connector_kwargs["method"] = cfg.get("method", "GET")
        auth_type = cfg.get("auth_type", "none")
        connector_kwargs["auth_type"] = auth_type
        if auth_type == "bearer":
            connector_kwargs["bearer_token"] = cfg.get("api_key", "")
        elif auth_type == "api_key_header":
            connector_kwargs["api_key"] = cfg.get("api_key", "")
            connector_kwargs["header_name"] = cfg.get("header_name", "Authorization")
        elif auth_type == "basic":
            connector_kwargs["basic_user"] = cfg.get("user", "")
            connector_kwargs["basic_password"] = cfg.get("password", "")
        elif auth_type == "api_key_query":
            connector_kwargs["api_key"] = cfg.get("api_key", "")
            connector_kwargs["query_param_name"] = cfg.get("query_param_name", "api_key")
        if isinstance(cfg.get("api_advanced"), dict):
            connector_kwargs.update(cfg["api_advanced"])

    return run_ingestion(
        api_connector,
        connector_kwargs["url"],
        "APIConnector",
        **connector_kwargs,          # url, method, auth_type, body, custom_fields, pagination_* 
        option=req.option,
        table_name=req.table_name,
        pipeline_id=req.pipeline_id,
        sync_mode=req.sync_mode,
        incremental_column=req.incremental_column,
        quality_connection_id=req.quality_connection_id,
        quality_config=req.quality_config,
        quality_on_fail=req.quality_on_fail,
        df_quality_config      = req.df_quality_config,
        df_quality_on_fail     = req.df_quality_on_fail,
        custom_schema          = req.custom_schema,
        destination_type           = req.destination_type,
        destination_connection_id  = req.destination_connection_id,
        destination_config         = req.destination_config,
    )

# ─────────────────────────────────────────────
# POSTGRES CONNECTOR
# ────────────────────────────────────────────
from connectors.postgres_connector import postgres_connector

class PostgresRequest(BaseModel):
    host: str = ""
    database: str = ""
    user: str = ""
    password: str = ""
    port: str = "5432"
    query: str
    option: str
    table_name: str | None = None
    sync_mode:  str        = "full"
    incremental_column: str | None = None
    connection_id: int | None = None   # use a saved connection's real credentials instead of the fields above
    pipeline_id: str | None = None     # set by the scheduler DAG so metrics/logs stay keyed by the real pipeline
    # ── optional data-quality gate, run right after load_to_db() succeeds ──
    quality_connection_id: int | None = None   # saved_connections id to run checks against (usually the warehouse this loads into)
    quality_config: dict | None = None          # same shape as quality.router.TableCheckSpec, minus table_name
    quality_on_fail: str = "warn"               # "warn" (log only) | "block" (mark this run FAILED)
    # ── optional PRE-INGEST dataframe-level quality gate, runs BEFORE load_to_db() ──
    df_quality_config: dict | None = None       # see quality.dataframe_checks.run_dataframe_quality_checks
    df_quality_on_fail: str = "warn"             # "warn" (log only) | "block" (skip ingest entirely)
    custom_schema: dict | None = None          # optional {"column": "type"} to enforce a user-defined schema (type in integer|float|boolean|date|timestamp|text|json) instead of auto-detected types
    destination_type: str = "postgres"           # postgres | mysql | oracle | mongodb | snowflake
    destination_connection_id: int | None = None  # saved_connections id to use as the destination (takes priority over destination_config)
    destination_config: dict | None = None        # inline destination config (host/user/password, or engine-specific fields) — used when destination_connection_id is not supplied


@app.post("/ingest_postgres")
def ingest_postgres(req: PostgresRequest):
    validate_inputs(req.option, req.table_name)
    host, database, user, password, port = req.host, req.database, req.user, req.password, req.port
    if req.connection_id:
        cfg, _ = _resolve_saved_connection(req.connection_id)
        host, database, user, password = cfg.get("host", ""), cfg.get("database", ""), cfg.get("user", ""), cfg.get("password", "")
        port = cfg.get("port", "5432")
    source = f"{host}/{database}"
    return run_ingestion(
        postgres_connector,
        source,
        "PostgresConnector",
        host,
        database,
        user,
        password,
        port,
        req.query,
        option=req.option,
        table_name=req.table_name,
        pipeline_id=req.pipeline_id,
        sync_mode          = req.sync_mode,
        incremental_column = req.incremental_column,
        quality_connection_id = req.quality_connection_id,
        quality_config         = req.quality_config,
        quality_on_fail        = req.quality_on_fail,
        df_quality_config      = req.df_quality_config,
        df_quality_on_fail     = req.df_quality_on_fail,
        custom_schema          = req.custom_schema,
        destination_type           = req.destination_type,
        destination_connection_id  = req.destination_connection_id,
        destination_config         = req.destination_config,
    )

# ─────────────────────────────────────────────
# MYSQL CONNECTOR
# ─────────────────────────────────────────────
from connectors.mysql_connector import mysql_connector

class MySQLRequest(BaseModel):
    host: str = ""
    database: str = ""
    user: str = ""
    password: str = ""
    port: str = "3306"
    query: str
    option: str
    table_name: str | None = None
    sync_mode:  str        = "full"
    incremental_column: str | None = None
    connection_id: int | None = None
    pipeline_id: str | None = None
    quality_connection_id: int | None = None
    quality_config: dict | None = None
    quality_on_fail: str = "warn"
    df_quality_config: dict | None = None
    df_quality_on_fail: str = "warn"
    custom_schema: dict | None = None          # optional {"column": "type"} to enforce a user-defined schema (type in integer|float|boolean|date|timestamp|text|json) instead of auto-detected types
    destination_type: str = "postgres"           # postgres | mysql | oracle | mongodb | snowflake
    destination_connection_id: int | None = None  # saved_connections id to use as the destination (takes priority over destination_config)
    destination_config: dict | None = None        # inline destination config (host/user/password, or engine-specific fields) — used when destination_connection_id is not supplied


@app.post("/ingest_mysql")
def ingest_mysql(req: MySQLRequest):
    validate_inputs(req.option, req.table_name)
    host, database, user, password, port = req.host, req.database, req.user, req.password, req.port
    if req.connection_id:
        cfg, _ = _resolve_saved_connection(req.connection_id)
        host, database, user, password = cfg.get("host", ""), cfg.get("database", ""), cfg.get("user", ""), cfg.get("password", "")
        port = cfg.get("port", "3306")
    source = f"{host}/{database}"
    return run_ingestion(
        mysql_connector,
        source,
        "MySQLConnector",
        host,
        database,
        user,
        password,
        port,
        req.query,
        option=req.option,
        table_name=req.table_name,
        pipeline_id=req.pipeline_id,
        sync_mode          = req.sync_mode,
        incremental_column = req.incremental_column,
        quality_connection_id = req.quality_connection_id,
        quality_config         = req.quality_config,
        quality_on_fail        = req.quality_on_fail,
        df_quality_config      = req.df_quality_config,
        df_quality_on_fail     = req.df_quality_on_fail,
        custom_schema          = req.custom_schema,
        destination_type           = req.destination_type,
        destination_connection_id  = req.destination_connection_id,
        destination_config         = req.destination_config,
    )

# ─────────────────────────────────────────────
# ORACLE CONNECTOR
# ─────────────────────────────────────────────
from connectors.oracle_connector import oracle_connector

class OracleRequest(BaseModel):
    host: str = ""
    database: str = ""   # service name
    user: str = ""
    password: str = ""
    port: str = "1521"
    query: str
    option: str
    table_name: str | None = None
    sync_mode:  str        = "full"
    incremental_column: str | None = None
    connection_id: int | None = None
    pipeline_id: str | None = None
    quality_connection_id: int | None = None
    quality_config: dict | None = None
    quality_on_fail: str = "warn"
    df_quality_config: dict | None = None
    df_quality_on_fail: str = "warn"
    custom_schema: dict | None = None          # optional {"column": "type"} to enforce a user-defined schema (type in integer|float|boolean|date|timestamp|text|json) instead of auto-detected types
    destination_type: str = "postgres"           # postgres | mysql | oracle | mongodb | snowflake
    destination_connection_id: int | None = None  # saved_connections id to use as the destination (takes priority over destination_config)
    destination_config: dict | None = None        # inline destination config (host/user/password, or engine-specific fields) — used when destination_connection_id is not supplied


@app.post("/ingest_oracle")
def ingest_oracle(req: OracleRequest):
    validate_inputs(req.option, req.table_name)
    host, database, user, password, port = req.host, req.database, req.user, req.password, req.port
    if req.connection_id:
        cfg, _ = _resolve_saved_connection(req.connection_id)
        host, database, user, password = cfg.get("host", ""), cfg.get("database", ""), cfg.get("user", ""), cfg.get("password", "")
        port = cfg.get("port", "1521")
    source = f"{host}/{database}"
    return run_ingestion(
        oracle_connector,
        source,
        "OracleConnector",
        host,
        database,
        user,
        password,
        port,
        req.query,
        option=req.option,
        table_name=req.table_name,
        pipeline_id=req.pipeline_id,
        sync_mode          = req.sync_mode,
        incremental_column = req.incremental_column,
        quality_connection_id = req.quality_connection_id,
        quality_config         = req.quality_config,
        quality_on_fail        = req.quality_on_fail,
        df_quality_config      = req.df_quality_config,
        df_quality_on_fail     = req.df_quality_on_fail,
        custom_schema          = req.custom_schema,
        destination_type           = req.destination_type,
        destination_connection_id  = req.destination_connection_id,
        destination_config         = req.destination_config,
    )

# ─────────────────────────────────────────────
# MONGODB CONNECTOR
# ─────────────────────────────────────────────
from connectors.mongodb_connector import mongodb_connector

class MongoDBRequest(BaseModel):
    host: str | None = None
    database: str = ""
    user: str | None = None
    password: str | None = None
    port: str = "27017"
    connection_string: str | None = None   # mongodb:// / mongodb+srv:// URI; overrides host/port/user/password when set
    collection: str
    query: str | None = None               # JSON filter document, e.g. '{"status": "active"}'
    option: str
    table_name: str | None = None
    sync_mode:  str        = "full"
    incremental_column: str | None = None
    connection_id: int | None = None
    pipeline_id: str | None = None
    quality_connection_id: int | None = None
    quality_config: dict | None = None
    quality_on_fail: str = "warn"
    df_quality_config: dict | None = None
    df_quality_on_fail: str = "warn"
    custom_schema: dict | None = None          # optional {"column": "type"} to enforce a user-defined schema (type in integer|float|boolean|date|timestamp|text|json) instead of auto-detected types
    destination_type: str = "postgres"           # postgres | mysql | oracle | mongodb | snowflake
    destination_connection_id: int | None = None  # saved_connections id to use as the destination (takes priority over destination_config)
    destination_config: dict | None = None        # inline destination config (host/user/password, or engine-specific fields) — used when destination_connection_id is not supplied


@app.post("/ingest_mongodb")
def ingest_mongodb(req: MongoDBRequest):
    validate_inputs(req.option, req.table_name)
    host, database, user, password, port = req.host, req.database, req.user, req.password, req.port
    connection_string = req.connection_string
    if req.connection_id:
        cfg, _ = _resolve_saved_connection(req.connection_id)
        host, database, user, password = cfg.get("host", ""), cfg.get("database", ""), cfg.get("user", ""), cfg.get("password", "")
        port = cfg.get("port", "27017")
        connection_string = cfg.get("connection_string") or connection_string
    source = f"{host or connection_string}/{database}.{req.collection}"
    return run_ingestion(
        mongodb_connector,
        source,
        "MongoDBConnector",
        host,
        database,
        user,
        password,
        port,
        req.collection,
        req.query,
        connection_string,
        option=req.option,
        table_name=req.table_name,
        pipeline_id=req.pipeline_id,
        sync_mode          = req.sync_mode,
        incremental_column = req.incremental_column,
        quality_connection_id = req.quality_connection_id,
        quality_config         = req.quality_config,
        quality_on_fail        = req.quality_on_fail,
        df_quality_config      = req.df_quality_config,
        df_quality_on_fail     = req.df_quality_on_fail,
        custom_schema          = req.custom_schema,
        destination_type           = req.destination_type,
        destination_connection_id  = req.destination_connection_id,
        destination_config         = req.destination_config,
    )

# ─────────────────────────────────────────────
# SALESFORCE CONNECTOR
# ─────────────────────────────────────────────

class SalesforceRequest(BaseModel):
    access_token: str | None = None
    instance_url: str | None = None
    login_url: str = "https://login.salesforce.com"
    client_id: str | None = None
    client_secret: str | None = None
    username: str | None = None
    password: str | None = None
    security_token: str | None = None
    object_name: str | None = None      # e.g. "Account", "Contact", "Lead", "Opportunity"
    fields: list | None = None
    soql_query: str | None = None       # overrides object_name/fields entirely
    option: str
    table_name: str | None = None
    sync_mode:  str        = "full"
    incremental_column: str | None = None
    connection_id: int | None = None
    pipeline_id: str | None = None
    quality_connection_id: int | None = None
    quality_config: dict | None = None
    quality_on_fail: str = "warn"
    df_quality_config: dict | None = None
    df_quality_on_fail: str = "warn"
    custom_schema: dict | None = None          # optional {"column": "type"} to enforce a user-defined schema (type in integer|float|boolean|date|timestamp|text|json) instead of auto-detected types
    destination_type: str = "postgres"           # postgres | mysql | oracle | mongodb | snowflake
    destination_connection_id: int | None = None  # saved_connections id to use as the destination (takes priority over destination_config)
    destination_config: dict | None = None        # inline destination config (host/user/password, or engine-specific fields) — used when destination_connection_id is not supplied


@app.post("/ingest_salesforce")
def ingest_salesforce(req: SalesforceRequest):
    validate_inputs(req.option, req.table_name)
    access_token, instance_url = req.access_token, req.instance_url
    login_url, client_id, client_secret = req.login_url, req.client_id, req.client_secret
    username, password, security_token = req.username, req.password, req.security_token
    if req.connection_id:
        cfg, _ = _resolve_saved_connection(req.connection_id)
        access_token = cfg.get("access_token") or access_token
        instance_url = cfg.get("instance_url") or instance_url
        login_url = cfg.get("login_url", login_url)
        client_id = cfg.get("client_id") or client_id
        client_secret = cfg.get("client_secret") or client_secret
        username = cfg.get("username") or username
        password = cfg.get("password") or password
        security_token = cfg.get("security_token") or security_token
    source = req.soql_query or f"{instance_url or login_url}/{req.object_name}"
    return run_ingestion(
        salesforce_connector,
        source,
        "SalesforceConnector",
        option=req.option,
        table_name=req.table_name,
        pipeline_id=req.pipeline_id,
        sync_mode          = req.sync_mode,
        incremental_column = req.incremental_column,
        quality_connection_id = req.quality_connection_id,
        quality_config         = req.quality_config,
        quality_on_fail        = req.quality_on_fail,
        df_quality_config      = req.df_quality_config,
        df_quality_on_fail     = req.df_quality_on_fail,
        custom_schema          = req.custom_schema,
        destination_type           = req.destination_type,
        destination_connection_id  = req.destination_connection_id,
        destination_config         = req.destination_config,
        access_token=access_token,
        instance_url=instance_url,
        login_url=login_url,
        client_id=client_id,
        client_secret=client_secret,
        username=username,
        password=password,
        security_token=security_token,
        object_name=req.object_name,
        fields=req.fields,
        soql_query=req.soql_query,
    )

# ─────────────────────────────────────────────
# HUBSPOT CONNECTOR
# ─────────────────────────────────────────────

class HubSpotRequest(BaseModel):
    access_token: str | None = None
    object_type: str = "contacts"       # contacts | companies | deals | tickets | line_items | products | custom
    properties: list | None = None
    option: str
    table_name: str | None = None
    sync_mode:  str        = "full"
    incremental_column: str | None = None
    connection_id: int | None = None
    pipeline_id: str | None = None
    quality_connection_id: int | None = None
    quality_config: dict | None = None
    quality_on_fail: str = "warn"
    df_quality_config: dict | None = None
    df_quality_on_fail: str = "warn"
    custom_schema: dict | None = None          # optional {"column": "type"} to enforce a user-defined schema (type in integer|float|boolean|date|timestamp|text|json) instead of auto-detected types
    destination_type: str = "postgres"           # postgres | mysql | oracle | mongodb | snowflake
    destination_connection_id: int | None = None  # saved_connections id to use as the destination (takes priority over destination_config)
    destination_config: dict | None = None        # inline destination config (host/user/password, or engine-specific fields) — used when destination_connection_id is not supplied


@app.post("/ingest_hubspot")
def ingest_hubspot(req: HubSpotRequest):
    validate_inputs(req.option, req.table_name)
    access_token = req.access_token
    if req.connection_id:
        cfg, _ = _resolve_saved_connection(req.connection_id)
        access_token = cfg.get("access_token") or access_token
    source = f"hubspot/{req.object_type}"
    return run_ingestion(
        hubspot_connector,
        source,
        "HubSpotConnector",
        option=req.option,
        table_name=req.table_name,
        pipeline_id=req.pipeline_id,
        sync_mode          = req.sync_mode,
        incremental_column = req.incremental_column,
        quality_connection_id = req.quality_connection_id,
        quality_config         = req.quality_config,
        quality_on_fail        = req.quality_on_fail,
        df_quality_config      = req.df_quality_config,
        df_quality_on_fail     = req.df_quality_on_fail,
        custom_schema          = req.custom_schema,
        destination_type           = req.destination_type,
        destination_connection_id  = req.destination_connection_id,
        destination_config         = req.destination_config,
        access_token=access_token,
        object_type=req.object_type,
        properties=req.properties,
    )

# ─────────────────────────────────────────────
# ZOHO CRM CONNECTOR
# ─────────────────────────────────────────────

class ZohoRequest(BaseModel):
    access_token: str | None = None
    refresh_token: str | None = None
    client_id: str | None = None
    client_secret: str | None = None
    accounts_url: str = "https://accounts.zoho.com"
    api_domain: str = "https://www.zohoapis.com"
    module: str | None = None           # e.g. "Leads", "Contacts", "Deals", "Accounts"
    fields: list | None = None
    criteria: str | None = None
    option: str
    table_name: str | None = None
    sync_mode:  str        = "full"
    incremental_column: str | None = None
    connection_id: int | None = None
    pipeline_id: str | None = None
    quality_connection_id: int | None = None
    quality_config: dict | None = None
    quality_on_fail: str = "warn"
    df_quality_config: dict | None = None
    df_quality_on_fail: str = "warn"
    custom_schema: dict | None = None          # optional {"column": "type"} to enforce a user-defined schema (type in integer|float|boolean|date|timestamp|text|json) instead of auto-detected types
    destination_type: str = "postgres"           # postgres | mysql | oracle | mongodb | snowflake
    destination_connection_id: int | None = None  # saved_connections id to use as the destination (takes priority over destination_config)
    destination_config: dict | None = None        # inline destination config (host/user/password, or engine-specific fields) — used when destination_connection_id is not supplied


@app.post("/ingest_zoho")
def ingest_zoho(req: ZohoRequest):
    validate_inputs(req.option, req.table_name)
    access_token, refresh_token = req.access_token, req.refresh_token
    client_id, client_secret = req.client_id, req.client_secret
    accounts_url, api_domain = req.accounts_url, req.api_domain
    if req.connection_id:
        cfg, _ = _resolve_saved_connection(req.connection_id)
        access_token = cfg.get("access_token") or access_token
        refresh_token = cfg.get("refresh_token") or refresh_token
        client_id = cfg.get("client_id") or client_id
        client_secret = cfg.get("client_secret") or client_secret
        accounts_url = cfg.get("accounts_url", accounts_url)
        api_domain = cfg.get("api_domain", api_domain)
    source = f"{api_domain}/{req.module}"
    return run_ingestion(
        zoho_connector,
        source,
        "ZohoConnector",
        option=req.option,
        table_name=req.table_name,
        pipeline_id=req.pipeline_id,
        sync_mode          = req.sync_mode,
        incremental_column = req.incremental_column,
        quality_connection_id = req.quality_connection_id,
        quality_config         = req.quality_config,
        quality_on_fail        = req.quality_on_fail,
        df_quality_config      = req.df_quality_config,
        df_quality_on_fail     = req.df_quality_on_fail,
        custom_schema          = req.custom_schema,
        destination_type           = req.destination_type,
        destination_connection_id  = req.destination_connection_id,
        destination_config         = req.destination_config,
        access_token=access_token,
        refresh_token=refresh_token,
        client_id=client_id,
        client_secret=client_secret,
        accounts_url=accounts_url,
        api_domain=api_domain,
        module=req.module,
        fields=req.fields,
        criteria=req.criteria,
    )

# ─────────────────────────────────────────────
# S3 CONNECTOR
# ─────────────────────────────────────────────

class S3Request(BaseModel):
    bucket:       str = ""
    key:          str = ""      # e.g. "folder/sales.csv"
    file_type:    str = "csv"   # csv, xlsx, parquet, json
    access_key:   str | None = None
    secret_key:   str | None = None
    option:       str
    table_name:   str | None = None
    sync_mode:    str = "full"
    incremental_column: str | None = None
    connection_id: int | None = None   # use a saved connection's real credentials instead of the fields above
    pipeline_id: str | None = None     # set by the scheduler DAG so metrics/logs stay keyed by the real pipeline
    # ── optional data-quality gate, run right after load_to_db() succeeds ──
    quality_connection_id: int | None = None   # saved_connections id to run checks against (usually the warehouse this loads into)
    quality_config: dict | None = None          # same shape as quality.router.TableCheckSpec, minus table_name
    quality_on_fail: str = "warn"               # "warn" (log only) | "block" (mark this run FAILED)
    # ── optional PRE-INGEST dataframe-level quality gate, runs BEFORE load_to_db() ──
    df_quality_config: dict | None = None       # see quality.dataframe_checks.run_dataframe_quality_checks
    df_quality_on_fail: str = "warn"             # "warn" (log only) | "block" (skip ingest entirely)
    custom_schema: dict | None = None          # optional {"column": "type"} to enforce a user-defined schema (type in integer|float|boolean|date|timestamp|text|json) instead of auto-detected types
    destination_type: str = "postgres"           # postgres | mysql | oracle | mongodb | snowflake
    destination_connection_id: int | None = None  # saved_connections id to use as the destination (takes priority over destination_config)
    destination_config: dict | None = None        # inline destination config (host/user/password, or engine-specific fields) — used when destination_connection_id is not supplied


@app.post("/ingest_s3")
def ingest_s3(req: S3Request):
    validate_inputs(req.option, req.table_name)
    bucket, key, file_type, access_key, secret_key = req.bucket, req.key, req.file_type, req.access_key, req.secret_key
    if req.connection_id:
        cfg, _ = _resolve_saved_connection(req.connection_id)
        bucket, file_type = cfg.get("bucket", ""), cfg.get("file_type", "csv")
        key = req.key or cfg.get("prefix", "")   # user still picks the exact object; prefix is just a fallback
        access_key, secret_key = cfg.get("access_key", ""), cfg.get("secret_key", "")
    source = f"s3://{bucket}/{key}"
    return run_ingestion(
        s3_connector,
        source,
        "S3Connector",
        bucket,
        key,
        file_type,
        access_key,
        secret_key,
        option              = req.option,
        table_name          = req.table_name,
        pipeline_id         = req.pipeline_id,
        sync_mode           = req.sync_mode,
        incremental_column  = req.incremental_column,
        quality_connection_id = req.quality_connection_id,
        quality_config         = req.quality_config,
        quality_on_fail        = req.quality_on_fail,
        df_quality_config      = req.df_quality_config,
        df_quality_on_fail     = req.df_quality_on_fail,
        custom_schema          = req.custom_schema,
        destination_type           = req.destination_type,
        destination_connection_id  = req.destination_connection_id,
        destination_config         = req.destination_config,
    )

# ─────────────────────────────────────────────
# SNOWFLAKE CONNECTOR
# ─────────────────────────────────────────────

class SnowflakeRequest(BaseModel):
    account: str = ""
    user: str = ""
    password: str = ""
    warehouse: str = ""
    database: str = ""
    schema: str = "PUBLIC"
    query: str
    option: str
    table_name: str | None = None
    sync_mode: str = "full"
    incremental_column: str | None = None
    role: str | None = None
    connection_id: int | None = None   # use a saved connection's real credentials instead of the fields above
    pipeline_id: str | None = None     # set by the scheduler DAG so metrics/logs stay keyed by the real pipeline
    # ── optional data-quality gate, run right after load_to_db() succeeds ──
    quality_connection_id: int | None = None   # saved_connections id to run checks against (usually the warehouse this loads into)
    quality_config: dict | None = None          # same shape as quality.router.TableCheckSpec, minus table_name
    quality_on_fail: str = "warn"               # "warn" (log only) | "block" (mark this run FAILED)
    # ── optional PRE-INGEST dataframe-level quality gate, runs BEFORE load_to_db() ──
    df_quality_config: dict | None = None       # see quality.dataframe_checks.run_dataframe_quality_checks
    df_quality_on_fail: str = "warn"             # "warn" (log only) | "block" (skip ingest entirely)
    custom_schema: dict | None = None          # optional {"column": "type"} to enforce a user-defined schema (type in integer|float|boolean|date|timestamp|text|json) instead of auto-detected types
    destination_type: str = "postgres"           # postgres | mysql | oracle | mongodb | snowflake
    destination_connection_id: int | None = None  # saved_connections id to use as the destination (takes priority over destination_config)
    destination_config: dict | None = None        # inline destination config (host/user/password, or engine-specific fields) — used when destination_connection_id is not supplied



@app.post("/ingest_snowflake")
def ingest_snowflake(req: SnowflakeRequest):
    validate_inputs(req.option, req.table_name)
    account, user, password, warehouse, database, schema, role = (
        req.account, req.user, req.password, req.warehouse, req.database, req.schema, req.role
    )
    if req.connection_id:
        cfg, _ = _resolve_saved_connection(req.connection_id)
        account, user, password = cfg.get("account", ""), cfg.get("user", ""), cfg.get("password", "")
        warehouse, database, schema = cfg.get("warehouse", ""), cfg.get("database", ""), cfg.get("schema", "PUBLIC")
        role = cfg.get("role", "")
    source = f"snowflake://{account}/{database}/{schema}"
    return run_ingestion(
        snowflake_connector,
        source,
        "SnowflakeConnector",
        account,
        user,
        password,
        warehouse,
        database,
        schema,
        req.query,
        role,
        option=req.option,
        table_name=req.table_name,
        pipeline_id=req.pipeline_id,
        sync_mode=req.sync_mode,
        incremental_column=req.incremental_column,
        quality_connection_id=req.quality_connection_id,
        quality_config=req.quality_config,
        quality_on_fail=req.quality_on_fail,
        df_quality_config      = req.df_quality_config,
        df_quality_on_fail     = req.df_quality_on_fail,
        custom_schema          = req.custom_schema,
        destination_type           = req.destination_type,
        destination_connection_id  = req.destination_connection_id,
        destination_config         = req.destination_config,
    )

@app.get("/runs")
def get_runs():
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM pipeline_runs ORDER BY start_time DESC")
    result = _rows_to_dicts(cursor)
    conn.close()
    return result

@app.get("/logs/{run_id}")
def get_logs(run_id: int):
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM pipeline_logs WHERE run_id=%s ORDER BY log_time",
        (run_id,)
    )
    data = cursor.fetchall()
    conn.close()
    return data

def insert_pipeline_log(data):
    conn = get_conn()
    cur = conn.cursor()

    query = """
    INSERT INTO airflow_pipeline_runs (
        dag_id, dag_run_id, pipeline_name,
        connector_type, file_path, folder_path,
        sheet_url, api_url, operation, table_name,
        schedule, status, execution_date, triggered_by
    )
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """

    cur.execute(query, (
        data.get("dag_id"),
        data.get("dag_run_id"),
        data.get("pipeline_name"),
        data.get("connector_type"),
        data.get("file_path"),
        data.get("folder_path"),
        data.get("sheet_url"),
        data.get("api_url"),
        data.get("operation"),
        data.get("table_name"),
        data.get("schedule"),
        data.get("status"),
        data.get("execution_date"),
        data.get("triggered_by", "manual"),
    ))

    conn.commit()
    cur.close()
    conn.close()

# ─────────────────────────────────────────────
# UPDATE STATUS IN DB
# ─────────────────────────────────────────────

def update_status_in_db(dag_run_id, status):
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""
        UPDATE airflow_pipeline_runs
        SET status = %s
        WHERE dag_run_id = %s
    """, (status, dag_run_id))

    conn.commit()
    cur.close()
    conn.close()

# ─────────────────────────────────────────────
# AUTO STATUS TRACKER — Background Thread
# ─────────────────────────────────────────────

def track_pipeline_status(dag_run_id: str, dag_id: str):
    url = f"{AIRFLOW_BASE}/{dag_id}/dagRuns/{dag_run_id}"

    print(f"🔍 Auto tracking started for: {dag_run_id}")

    max_attempts = 60
    attempt = 0

    while attempt < max_attempts:
        try:
            res = requests.get(url, auth=AIRFLOW_AUTH, timeout=10)

            if res.status_code != 200:
                print(f"⚠️ Airflow API error: {res.status_code}")
                time.sleep(5)
                attempt += 1
                continue

            data   = res.json()
            status = data.get("state")

            print(f"📊 [{dag_run_id}] Status: {status}")

            if status in ["success", "failed"]:
                update_status_in_db(dag_run_id, status.upper())
                print(f"✅ Final status '{status.upper()}' saved for: {dag_run_id}")
                send_failure_email(dag_id=dag_id, run_id=dag_run_id, status=status)
                return

            time.sleep(5)
            attempt += 1

        except Exception as e:
            print(f"❌ Tracking error: {e}")
            time.sleep(5)
            attempt += 1

    update_status_in_db(dag_run_id, "TIMEOUT")
    print(f"⏰ Tracking timeout for: {dag_run_id}")

# ─────────────────────────────────────────────
# MANUAL STATUS CHECK
# ─────────────────────────────────────────────

@app.get("/pipeline_status/{connector_type}/{dag_run_id}")
def get_status(connector_type: str, dag_run_id: str):
    dag_id = DAG_MAP.get(connector_type)
    if not dag_id:
        raise HTTPException(status_code=400, detail=f"Invalid connector_type: {connector_type}")

    url  = f"{AIRFLOW_BASE}/{dag_id}/dagRuns/{dag_run_id}"
    res  = requests.get(url, auth=AIRFLOW_AUTH)
    data = res.json()
    status = data.get("state")
    update_status_in_db(dag_run_id, status)
    return {"dag_id": dag_id, "dag_run_id": dag_run_id, "status": status}

# ─────────────────────────────────────────────
# ALL PIPELINES
# ─────────────────────────────────────────────

@app.get("/all_pipelines")
def get_all():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM airflow_pipeline_runs ORDER BY created_at DESC LIMIT 50")
    rows = cur.fetchall()
    cols = [d[0] for d in cur.description]
    conn.close()
    return [dict(zip(cols, r)) for r in rows]

# ── Request model ────────────────────────────────────────────────────────────

class CreatePipelineRequest(BaseModel):
    pipeline_name:   str
    connector_type:  str
    table_name:      str
    option:          str         = "1"
    after_first_run: Optional[str] = None   # option "3" required — "1" or "2"
    schedule:        str         = "*/5 * * * *"
    timezone:        Optional[str] = "Asia/Kolkata"
    folder_path:     Optional[str] = None
    file_path:       Optional[str] = None
    sheet_url:       Optional[str] = None
    api_url:         Optional[str] = None
    api_config:      Optional[dict] = None
    connection_id:   Optional[int] = None    # ID of saved connection to use
    quality_connection_id: Optional[int] = None
    quality_config:  Optional[dict] = None
    quality_on_fail: str = "warn"
    df_quality_config: Optional[dict] = None
    df_quality_on_fail: str = "warn"
    custom_schema:   Optional[dict] = None   # optional {"column": "type"} — see utils/schema_applier.py
    # ── Destination (where the scheduled loads get WRITTEN to). See
    # backend/destinations/. Defaults to postgres, so existing pipelines
    # created before this field existed keep working unchanged. ──────────
    destination_type: str = "postgres"           # postgres | mysql | oracle | mongodb | snowflake
    destination_connection_id: Optional[int] = None  # saved_connections id (takes priority over destination_config)
    destination_config: Optional[dict] = None        # inline destination config — used when destination_connection_id is not supplied

    # ── Postgres fields ──────────────────
    src_pg_host:     Optional[str] = None
    src_pg_db:       Optional[str] = None
    src_pg_user:     Optional[str] = None
    src_pg_password: Optional[str] = None
    src_pg_port:     Optional[str] = "5432"
    pg_query:        Optional[str] = None
    # ── MySQL fields ──────────────────────
    src_my_host:     Optional[str] = None
    src_my_db:       Optional[str] = None
    src_my_user:     Optional[str] = None
    src_my_password: Optional[str] = None
    src_my_port:     Optional[str] = "3306"
    my_query:        Optional[str] = None
    # ── Oracle fields ─────────────────────
    src_ora_host:     Optional[str] = None
    src_ora_db:       Optional[str] = None   # service name
    src_ora_user:     Optional[str] = None
    src_ora_password: Optional[str] = None
    src_ora_port:     Optional[str] = "1521"
    ora_query:        Optional[str] = None
    # ── MongoDB fields ────────────────────
    src_mongo_host:     Optional[str] = None
    src_mongo_db:       Optional[str] = None
    src_mongo_user:     Optional[str] = None
    src_mongo_password: Optional[str] = None
    src_mongo_port:     Optional[str] = "27017"
    src_mongo_connection_string: Optional[str] = None
    mongo_collection:   Optional[str] = None
    mongo_query:        Optional[str] = None   # JSON filter document, e.g. '{"status": "active"}'
    # ── S3 fields ────────────────────────
    s3_bucket:       Optional[str] = None
    s3_key:          Optional[str] = None
    s3_file_type:    Optional[str] = "csv"
    s3_access_key:   Optional[str] = None
    s3_secret_key:   Optional[str] = None
    # ── Snowflake fields ─────────────────
    sf_account:      Optional[str] = None
    sf_user:         Optional[str] = None
    sf_password:     Optional[str] = None
    sf_warehouse:    Optional[str] = None
    sf_database:     Optional[str] = None
    sf_schema:       Optional[str] = "PUBLIC"
    sf_query:        Optional[str] = None
    sf_role:         Optional[str] = None
    # ── Salesforce CRM fields ─────────────
    sf_crm_access_token:    Optional[str] = None
    sf_crm_instance_url:    Optional[str] = None
    sf_crm_login_url:       Optional[str] = "https://login.salesforce.com"
    sf_crm_client_id:       Optional[str] = None
    sf_crm_client_secret:   Optional[str] = None
    sf_crm_username:        Optional[str] = None
    sf_crm_password:        Optional[str] = None
    sf_crm_security_token:  Optional[str] = None
    sf_crm_object_name:     Optional[str] = None
    sf_crm_fields:          Optional[list] = None
    sf_crm_soql_query:      Optional[str] = None
    # ── HubSpot fields ────────────────────
    hs_access_token: Optional[str] = None
    hs_object_type:  Optional[str] = "contacts"
    hs_properties:   Optional[list] = None
    # ── Zoho CRM fields ───────────────────
    zoho_access_token:  Optional[str] = None
    zoho_refresh_token: Optional[str] = None
    zoho_client_id:      Optional[str] = None
    zoho_client_secret:  Optional[str] = None
    zoho_accounts_url:   Optional[str] = "https://accounts.zoho.com"
    zoho_api_domain:     Optional[str] = "https://www.zohoapis.com"
    zoho_module:         Optional[str] = None
    zoho_fields:         Optional[list] = None
    zoho_criteria:       Optional[str] = None
    # ─── Incremental fields ─────────────────────
    sync_mode:     Optional[str] = "full"   # "full" or "incremental"
    incremental_column:    Optional[str] = None     # required if load_type is "incremental"
    # ── optional data-quality gates, same shape as Direct Ingest ──────────
    quality_connection_id: int | None = None
    quality_config: dict | None = None
    quality_on_fail: str = "warn"
    df_quality_config: dict | None = None
    df_quality_on_fail: str = "warn"
    custom_schema: dict | None = None          # optional {"column": "type"} to enforce a user-defined schema (type in integer|float|boolean|date|timestamp|text|json) instead of auto-detected types

CONNECTOR_TYPE_MAP = {
    "csv": "local_folder",
    "excel": "local_folder",
    "google_sheets": "google_sheet",
    "api": "api",
    "postgres": "postgres",
    "mysql": "mysql",
    "oracle": "oracle",
    "mongodb": "mongodb",
    "s3": "s3",
    "snowflake": "snowflake",
    "salesforce": "salesforce",
    "hubspot": "hubspot",
    "zoho": "zoho",
}

def _resolve_connection_config(req: CreatePipelineRequest) -> dict:
    """Fetch connection config and merge with request fields."""
    if not req.connection_id:
        return req.model_dump()

    ensure_connections_table()
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        SELECT config, source_type FROM saved_connections WHERE id = %s
    """, (req.connection_id,))
    row = cur.fetchone()
    cur.close()
    conn.close()

    if not row:
        raise HTTPException(status_code=404, detail="Connection not found")

    config, source_type = row
    expected_source_type = CONNECTOR_TYPE_MAP.get(req.connector_type)
    if source_type != expected_source_type:
        raise HTTPException(status_code=400, detail=f"Connection type '{source_type}' does not match connector type '{req.connector_type}'")

    config = config if isinstance(config, dict) else json.loads(config)

    merged = req.model_dump()

    if req.connector_type == "postgres":
        merged["src_pg_host"] = config.get("host", "")
        merged["src_pg_db"] = config.get("database", "")
        merged["src_pg_user"] = config.get("user", "")
        merged["src_pg_password"] = config.get("password", "")
        merged["src_pg_port"] = config.get("port", "5432")
    elif req.connector_type == "mysql":
        merged["src_my_host"] = config.get("host", "")
        merged["src_my_db"] = config.get("database", "")
        merged["src_my_user"] = config.get("user", "")
        merged["src_my_password"] = config.get("password", "")
        merged["src_my_port"] = config.get("port", "3306")
    elif req.connector_type == "oracle":
        merged["src_ora_host"] = config.get("host", "")
        merged["src_ora_db"] = config.get("database", "")
        merged["src_ora_user"] = config.get("user", "")
        merged["src_ora_password"] = config.get("password", "")
        merged["src_ora_port"] = config.get("port", "1521")
    elif req.connector_type == "mongodb":
        merged["src_mongo_host"] = config.get("host", "")
        merged["src_mongo_db"] = config.get("database", "")
        merged["src_mongo_user"] = config.get("user", "")
        merged["src_mongo_password"] = config.get("password", "")
        merged["src_mongo_port"] = config.get("port", "27017")
        merged["src_mongo_connection_string"] = config.get("connection_string", "")
        merged["mongo_collection"] = merged.get("mongo_collection") or config.get("collection", "")
    elif req.connector_type == "s3":
        merged["s3_bucket"] = config.get("bucket", "")
        merged["s3_key"] = config.get("prefix", "")
        merged["s3_file_type"] = config.get("file_type", "csv")
        merged["s3_access_key"] = config.get("access_key", "")
        merged["s3_secret_key"] = config.get("secret_key", "")
    elif req.connector_type == "snowflake":
        merged["sf_account"] = config.get("account", "")
        merged["sf_user"] = config.get("user", "")
        merged["sf_password"] = config.get("password", "")
        merged["sf_warehouse"] = config.get("warehouse", "")
        merged["sf_database"] = config.get("database", "")
        merged["sf_schema"] = config.get("schema", "PUBLIC")
        merged["sf_role"] = config.get("role", "")
    elif req.connector_type == "api":
        merged["api_url"] = config.get("base_url", "")

        resolved_api_config: dict = {
            "method":    config.get("method", "GET"),
            "auth_type": config.get("auth_type", "none"),
        }
        auth_type = config.get("auth_type", "none")
        if auth_type == "bearer":
            resolved_api_config["bearer_token"]  = config.get("api_key", "")
            resolved_api_config["bearer_prefix"] = config.get("bearer_prefix", "Bearer")
        elif auth_type == "api_key_header":
            resolved_api_config["api_key"]     = config.get("api_key", "")
            resolved_api_config["header_name"] = config.get("header_name", "Authorization")
        elif auth_type == "basic":
            resolved_api_config["basic_user"]     = config.get("user", "")
            resolved_api_config["basic_password"] = config.get("password", "")
        elif auth_type == "api_key_query":
            resolved_api_config["api_key"]           = config.get("api_key", "")
            resolved_api_config["query_param_name"]  = config.get("query_param_name", "api_key")

        # body, pagination_type, extra_headers, extra_params, custom_fields, etc.
        if isinstance(config.get("api_advanced"), dict):
            resolved_api_config.update(config["api_advanced"])

        # If the request itself ALSO carried api_config (e.g. user typed one
        # in the pipeline form in addition to picking a saved connection),
        # let that win — it's the more specific, most-recent input.
        if merged.get("api_config"):
            resolved_api_config.update(merged["api_config"])

        merged["api_config"] = resolved_api_config
    elif req.connector_type == "google_sheets":
        merged["sheet_url"] = config.get("sheet_url", "")
    elif req.connector_type in ("csv", "excel"):
        merged["folder_path"] = config.get("base_path", "")
        merged["s3_file_type"] = config.get("file_type", "csv")
    elif req.connector_type == "salesforce":
        merged["sf_crm_access_token"] = config.get("access_token", "")
        merged["sf_crm_instance_url"] = config.get("instance_url", "")
        merged["sf_crm_login_url"] = config.get("login_url", "https://login.salesforce.com")
        merged["sf_crm_client_id"] = config.get("client_id", "")
        merged["sf_crm_client_secret"] = config.get("client_secret", "")
        merged["sf_crm_username"] = config.get("username", "")
        merged["sf_crm_password"] = config.get("password", "")
        merged["sf_crm_security_token"] = config.get("security_token", "")
    elif req.connector_type == "hubspot":
        merged["hs_access_token"] = config.get("access_token", "")
    elif req.connector_type == "zoho":
        merged["zoho_access_token"] = config.get("access_token", "")
        merged["zoho_refresh_token"] = config.get("refresh_token", "")
        merged["zoho_client_id"] = config.get("client_id", "")
        merged["zoho_client_secret"] = config.get("client_secret", "")
        merged["zoho_accounts_url"] = config.get("accounts_url", "https://accounts.zoho.com")
        merged["zoho_api_domain"] = config.get("api_domain", "https://www.zohoapis.com")

    return merged



@app.post("/create_pipeline")
def create_pipeline(req: CreatePipelineRequest):
    if req.api_config is not None:
        try:
            json.dumps(req.api_config)
        except (TypeError, ValueError):
            raise HTTPException(status_code=400, detail="api_config must be JSON-serializable")

    payload = _resolve_connection_config(req)
    result = create_dag_file(payload)

    if result.get("status") == "FAILED":
        raise HTTPException(status_code=400, detail=result)

    dag_id = result.get("dag_id")
    insert_pipeline_log({
        "dag_id":         dag_id,
        "dag_run_id":     f"created__{dag_id}",
        "pipeline_name":  dag_id,
        "connector_type": req.connector_type,
        "file_path":      req.file_path,
        "folder_path":    req.folder_path,
        "sheet_url":      req.sheet_url,
        "api_url":        req.api_url,
        "operation":      OPTION_MAP.get(req.option, "unknown"),
        "table_name":     req.table_name,
        "schedule":       req.schedule,
        "status":         "CREATED",
        "execution_date": None,
        "triggered_by":   "create_pipeline",
    })

    return result
# ────────────────────────────────────────────
# Multiple sources pipeline creation 
# ───────────────────────────────────────────

class SourceConfig(BaseModel):
    connector_type: str          # csv, excel, google_sheets, api, postgres, s3, snowflake
    file_path:      Optional[str] = None
    folder_path:    Optional[str] = None
    sheet_url:      Optional[str] = None
    api_url:        Optional[str] = None
    api_config:      Optional[dict] = None
    s3_bucket:      Optional[str] = None
    s3_key:         Optional[str] = None
    s3_file_type:   Optional[str] = "csv"
    s3_access_key:  Optional[str] = None
    s3_secret_key:  Optional[str] = None
    src_pg_host:    Optional[str] = None
    src_pg_db:      Optional[str] = None
    src_pg_user:    Optional[str] = None
    src_pg_password:Optional[str] = None
    src_pg_port:    Optional[str] = "5432"
    pg_query:       Optional[str] = None
    # MySQL fields
    src_my_host:     Optional[str] = None
    src_my_db:       Optional[str] = None
    src_my_user:     Optional[str] = None
    src_my_password: Optional[str] = None
    src_my_port:     Optional[str] = "3306"
    my_query:        Optional[str] = None
    # Oracle fields
    src_ora_host:     Optional[str] = None
    src_ora_db:       Optional[str] = None
    src_ora_user:     Optional[str] = None
    src_ora_password: Optional[str] = None
    src_ora_port:     Optional[str] = "1521"
    ora_query:        Optional[str] = None
    # MongoDB fields
    src_mongo_host:     Optional[str] = None
    src_mongo_db:       Optional[str] = None
    src_mongo_user:     Optional[str] = None
    src_mongo_password: Optional[str] = None
    src_mongo_port:     Optional[str] = "27017"
    src_mongo_connection_string: Optional[str] = None
    mongo_collection:   Optional[str] = None
    mongo_query:        Optional[str] = None
    # Snowflake fields
    sf_account:     Optional[str] = None
    sf_user:        Optional[str] = None
    sf_password:    Optional[str] = None
    sf_warehouse:   Optional[str] = None
    sf_database:    Optional[str] = None
    sf_schema:      Optional[str] = "PUBLIC"
    sf_query:       Optional[str] = None
    sf_role:        Optional[str] = None
    # Salesforce CRM fields
    sf_crm_access_token:    Optional[str] = None
    sf_crm_instance_url:    Optional[str] = None
    sf_crm_login_url:       Optional[str] = "https://login.salesforce.com"
    sf_crm_client_id:       Optional[str] = None
    sf_crm_client_secret:   Optional[str] = None
    sf_crm_username:        Optional[str] = None
    sf_crm_password:        Optional[str] = None
    sf_crm_security_token:  Optional[str] = None
    sf_crm_object_name:     Optional[str] = None
    sf_crm_fields:          Optional[list] = None
    sf_crm_soql_query:      Optional[str] = None
    # HubSpot fields
    hs_access_token: Optional[str] = None
    hs_object_type:  Optional[str] = "contacts"
    hs_properties:   Optional[list] = None
    # Zoho CRM fields
    zoho_access_token:   Optional[str] = None
    zoho_refresh_token:  Optional[str] = None
    zoho_client_id:      Optional[str] = None
    zoho_client_secret:  Optional[str] = None
    zoho_accounts_url:   Optional[str] = "https://accounts.zoho.com"
    zoho_api_domain:     Optional[str] = "https://www.zohoapis.com"
    zoho_module:         Optional[str] = None
    zoho_fields:         Optional[list] = None
    zoho_criteria:       Optional[str] = None
    # Saved connection
    connection_id:  Optional[int] = None
    # ── optional per-source data-quality gates, same shape as Direct Ingest ──
    quality_connection_id: int | None = None
    quality_config: dict | None = None
    quality_on_fail: str = "warn"
    df_quality_config: dict | None = None
    df_quality_on_fail: str = "warn"
    custom_schema: dict | None = None          # optional {"column": "type"} to enforce a user-defined schema (type in integer|float|boolean|date|timestamp|text|json) instead of auto-detected types

class MultiSourcePipelineRequest(BaseModel):
    pipeline_name: str
    table_name:    str
    option:        str          = "1"   # for first source. Subsequent sources will always append (option "1") to avoid overwriting.
    schedule:      str          = "*/5 * * * *"
    timezone:      Optional[str] = "Asia/Kolkata"
    sync_mode:     str          = "full"
    incremental_column: Optional[str] = None
    sources:       List[SourceConfig]  # ← multiple sources
    # ── Destination (where ALL sources load into) — one table, one
    # destination for the whole pipeline. See backend/destinations/.
    destination_type:           str = "postgres"           # postgres | mysql | oracle | mongodb | snowflake
    destination_connection_id:  Optional[int] = None         # saved_connections id (takes priority over destination_config)
    destination_config:         Optional[dict] = None        # inline config — used when destination_connection_id is not supplied

def _resolve_source_connection(source: SourceConfig) -> dict:
    """Fetch connection config for a single source and merge with request fields."""
    if not source.connection_id:
        return source.model_dump()

    ensure_connections_table()
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        SELECT config, source_type FROM saved_connections WHERE id = %s
    """, (source.connection_id,))
    row = cur.fetchone()
    cur.close()
    conn.close()

    if not row:
        raise HTTPException(status_code=404, detail=f"Connection with id {source.connection_id} not found")

    config, source_type = row
    expected_source_type = CONNECTOR_TYPE_MAP.get(source.connector_type)
    if source_type != expected_source_type:
        raise HTTPException(status_code=400, detail=f"Connection type '{source_type}' does not match connector type '{source.connector_type}'")

    config = config if isinstance(config, dict) else json.loads(config)
    merged = source.model_dump()

    if source.connector_type == "postgres":
        merged["src_pg_host"] = config.get("host", "")
        merged["src_pg_db"] = config.get("database", "")
        merged["src_pg_user"] = config.get("user", "")
        merged["src_pg_password"] = config.get("password", "")
        merged["src_pg_port"] = config.get("port", "5432")
    elif source.connector_type == "mysql":
        merged["src_my_host"] = config.get("host", "")
        merged["src_my_db"] = config.get("database", "")
        merged["src_my_user"] = config.get("user", "")
        merged["src_my_password"] = config.get("password", "")
        merged["src_my_port"] = config.get("port", "3306")
    elif source.connector_type == "oracle":
        merged["src_ora_host"] = config.get("host", "")
        merged["src_ora_db"] = config.get("database", "")
        merged["src_ora_user"] = config.get("user", "")
        merged["src_ora_password"] = config.get("password", "")
        merged["src_ora_port"] = config.get("port", "1521")
    elif source.connector_type == "mongodb":
        merged["src_mongo_host"] = config.get("host", "")
        merged["src_mongo_db"] = config.get("database", "")
        merged["src_mongo_user"] = config.get("user", "")
        merged["src_mongo_password"] = config.get("password", "")
        merged["src_mongo_port"] = config.get("port", "27017")
        merged["src_mongo_connection_string"] = config.get("connection_string", "")
        merged["mongo_collection"] = merged.get("mongo_collection") or config.get("collection", "")
    elif source.connector_type == "s3":
        merged["s3_bucket"] = config.get("bucket", "")
        merged["s3_key"] = config.get("prefix", "")
        merged["s3_file_type"] = config.get("file_type", "csv")
        merged["s3_access_key"] = config.get("access_key", "")
        merged["s3_secret_key"] = config.get("secret_key", "")
    elif source.connector_type == "snowflake":
        merged["sf_account"] = config.get("account", "")
        merged["sf_user"] = config.get("user", "")
        merged["sf_password"] = config.get("password", "")
        merged["sf_warehouse"] = config.get("warehouse", "")
        merged["sf_database"] = config.get("database", "")
        merged["sf_schema"] = config.get("schema", "PUBLIC")
        merged["sf_role"] = config.get("role", "")
    elif source.connector_type == "api":
        merged["api_url"] = config.get("base_url", "")

        resolved_api_config: dict = {
            "method":    config.get("method", "GET"),
            "auth_type": config.get("auth_type", "none"),
        }
        auth_type = config.get("auth_type", "none")
        if auth_type == "bearer":
            resolved_api_config["bearer_token"]  = config.get("api_key", "")
            resolved_api_config["bearer_prefix"] = config.get("bearer_prefix", "Bearer")
        elif auth_type == "api_key_header":
            resolved_api_config["api_key"]     = config.get("api_key", "")
            resolved_api_config["header_name"] = config.get("header_name", "Authorization")
        elif auth_type == "basic":
            resolved_api_config["basic_user"]     = config.get("user", "")
            resolved_api_config["basic_password"] = config.get("password", "")
        elif auth_type == "api_key_query":
            resolved_api_config["api_key"]           = config.get("api_key", "")
            resolved_api_config["query_param_name"]  = config.get("query_param_name", "api_key")

        if isinstance(config.get("api_advanced"), dict):
            resolved_api_config.update(config["api_advanced"])

        if merged.get("api_config"):
            resolved_api_config.update(merged["api_config"])

        merged["api_config"] = resolved_api_config
    elif source.connector_type == "google_sheets":
        merged["sheet_url"] = config.get("sheet_url", "")
    elif source.connector_type in ("csv", "excel"):
        merged["folder_path"] = config.get("base_path", "")
        merged["s3_file_type"] = config.get("file_type", "csv")
    elif source.connector_type == "salesforce":
        merged["sf_crm_access_token"] = config.get("access_token", "")
        merged["sf_crm_instance_url"] = config.get("instance_url", "")
        merged["sf_crm_login_url"] = config.get("login_url", "https://login.salesforce.com")
        merged["sf_crm_client_id"] = config.get("client_id", "")
        merged["sf_crm_client_secret"] = config.get("client_secret", "")
        merged["sf_crm_username"] = config.get("username", "")
        merged["sf_crm_password"] = config.get("password", "")
        merged["sf_crm_security_token"] = config.get("security_token", "")
    elif source.connector_type == "hubspot":
        merged["hs_access_token"] = config.get("access_token", "")
    elif source.connector_type == "zoho":
        merged["zoho_access_token"] = config.get("access_token", "")
        merged["zoho_refresh_token"] = config.get("refresh_token", "")
        merged["zoho_client_id"] = config.get("client_id", "")
        merged["zoho_client_secret"] = config.get("client_secret", "")
        merged["zoho_accounts_url"] = config.get("accounts_url", "https://accounts.zoho.com")
        merged["zoho_api_domain"] = config.get("api_domain", "https://www.zohoapis.com")

    return merged


@app.post("/create_multi_pipeline")
def create_multi_pipeline(req: MultiSourcePipelineRequest):
    if not req.sources:
        raise HTTPException(status_code=400, detail="At least one source required.")

    for i, src in enumerate(req.sources):
        if src.api_config is not None:
            try:
                json.dumps(src.api_config)
            except (TypeError, ValueError):
                raise HTTPException(status_code=400, detail=f"Source {i+1}: api_config must be JSON-serializable")

    from utils.multi_dag_generator import create_multi_dag_file
    payload = req.model_dump()
    payload["sources"] = [_resolve_source_connection(src) for src in req.sources]
    result = create_multi_dag_file(payload)

    if result.get("status") == "FAILED":
        raise HTTPException(status_code=400, detail=result)

    return result




# ────────────────────────────────────────────
# Edit existing pipeline
# ────────────────────────────────────────────

from utils.dag_generator import (
    create_dag_file, delete_dag_file, list_dag_files, edit_dag_file,
    get_dag_config, get_dag_raw_content, restore_dag_raw_content,
    get_dag_source_credentials,
    _safe_id as _safe_pipeline_id,
)
from utils import history_store

class EditPipelineRequest(BaseModel):
    # source config
    folder_path:        Optional[str] = None
    file_path:          Optional[str] = None
    sheet_url:          Optional[str] = None
    api_url:            Optional[str] = None
    # scheduling
    schedule:           Optional[str] = None
    timezone:           Optional[str] = None
    # load config
    option:             Optional[str] = None
    after_first_run:    Optional[str] = None
    table_name:         Optional[str] = None
    # sync
    sync_mode:          Optional[str] = None
    incremental_column: Optional[str] = None
    # postgres
    src_pg_host:        Optional[str] = None
    src_pg_db:          Optional[str] = None
    src_pg_user:        Optional[str] = None
    src_pg_password:    Optional[str] = None
    src_pg_port:        Optional[str] = None
    pg_query:           Optional[str] = None
    # mysql
    src_my_host:        Optional[str] = None
    src_my_db:          Optional[str] = None
    src_my_user:        Optional[str] = None
    src_my_password:    Optional[str] = None
    src_my_port:        Optional[str] = None
    my_query:           Optional[str] = None
    # oracle
    src_ora_host:        Optional[str] = None
    src_ora_db:          Optional[str] = None
    src_ora_user:        Optional[str] = None
    src_ora_password:    Optional[str] = None
    src_ora_port:        Optional[str] = None
    ora_query:           Optional[str] = None
    # mongodb
    src_mongo_host:              Optional[str] = None
    src_mongo_db:                Optional[str] = None
    src_mongo_user:              Optional[str] = None
    src_mongo_password:          Optional[str] = None
    src_mongo_port:              Optional[str] = None
    src_mongo_connection_string: Optional[str] = None
    mongo_collection:            Optional[str] = None
    mongo_query:                 Optional[str] = None
    # s3
    s3_bucket:          Optional[str] = None
    s3_key:             Optional[str] = None
    s3_file_type:       Optional[str] = None
    s3_access_key:      Optional[str] = None
    s3_secret_key:      Optional[str] = None
    # snowflake
    sf_account:         Optional[str] = None
    sf_user:            Optional[str] = None
    sf_password:        Optional[str] = None
    sf_warehouse:       Optional[str] = None
    sf_database:        Optional[str] = None
    sf_schema:          Optional[str] = None
    sf_query:           Optional[str] = None
    sf_role:            Optional[str] = None
    # salesforce (crm)
    sf_crm_access_token:    Optional[str] = None
    sf_crm_instance_url:    Optional[str] = None
    sf_crm_login_url:       Optional[str] = None
    sf_crm_client_id:       Optional[str] = None
    sf_crm_client_secret:   Optional[str] = None
    sf_crm_username:        Optional[str] = None
    sf_crm_password:        Optional[str] = None
    sf_crm_security_token:  Optional[str] = None
    sf_crm_object_name:     Optional[str] = None
    sf_crm_fields:           Optional[list] = None
    sf_crm_soql_query:      Optional[str] = None
    # hubspot
    hs_access_token: Optional[str] = None
    hs_object_type:  Optional[str] = None
    hs_properties:   Optional[list] = None
    # zoho
    zoho_access_token:   Optional[str] = None
    zoho_refresh_token:  Optional[str] = None
    zoho_client_id:      Optional[str] = None
    zoho_client_secret:  Optional[str] = None
    zoho_accounts_url:   Optional[str] = None
    zoho_api_domain:     Optional[str] = None
    zoho_module:         Optional[str] = None
    zoho_fields:         Optional[list] = None
    zoho_criteria:       Optional[str] = None
    # data quality — pre-ingest dataframe checks (dtype, nulls, ranges, etc.)
    # edit_dag_file() already knows how to write DF_QUALITY_CONFIG /
    # DF_QUALITY_ON_FAIL; this model just never exposed them for editing.
    df_quality_config:   Optional[dict] = None
    df_quality_on_fail:  Optional[str] = None
    # BUGFIX: custom_schema was never exposed on the edit model at all, so
    # edit_pipeline() could never change (or clear) a pipeline's schema
    # override even after edit_dag_file() learned how to write it.
    custom_schema:       Optional[dict] = None



@app.patch("/edit_pipeline/{pipeline_name}")
def edit_pipeline(pipeline_name: str, req: EditPipelineRequest):
    # NOTE: df_quality_config/df_quality_on_fail/custom_schema are always
    # sent by the frontend on every save (even as null, meaning "no checks
    # configured" / "no schema override"). A blanket "drop every None"
    # filter silently swallows that intent — the field never reaches
    # edit_dag_file(), so the DAG file variable is never touched and the
    # OLD value sticks around forever, even though the save appeared to
    # succeed. Carve these fields out of the generic None-filter so an
    # explicit null still gets applied.
    raw = req.model_dump()
    always_include = {"df_quality_config", "df_quality_on_fail", "custom_schema"}
    updates = {
        k: v for k, v in raw.items()
        if v is not None or k in always_include
    }

    if not updates:
        raise HTTPException(status_code=400, detail="At least one field required for update.")

    if "option" in updates and updates["option"] not in ("1", "2", "3"):
        raise HTTPException(status_code=400, detail="option '1' (append), '2' (overwrite), and '3' (create only) are valid.")

    if "sync_mode" in updates and updates["sync_mode"] not in ("full", "incremental"):
        raise HTTPException(status_code=400, detail="sync_mode 'full' or 'incremental' is required.")

    # ── Snapshot the pipeline as it is RIGHT NOW, before the regex edit ──────
    # edit_dag_file() only ever sees the partial `updates` dict, never the
    # pre-edit whole file — so the "what it looked like before" snapshot has
    # to be built here, from the live file, not from `updates`.
    pre_edit_config = get_dag_config(pipeline_name)
    pre_edit_raw = get_dag_raw_content(pipeline_name)
    if pre_edit_config is not None:
        changed_fields = ", ".join(sorted(updates.keys()))
        history_store.push_history(
            entity_type="pipeline",
            entity_id=_safe_pipeline_id(pipeline_name),
            config=pre_edit_config,
            raw_content=pre_edit_raw,
            label=f"Edited: {changed_fields}",
        )

    result = edit_dag_file(pipeline_name, updates)

    if result.get("status") == "FAILED":
        raise HTTPException(status_code=404, detail=result)

    try:
        dag_id = f"pipeline_{pipeline_name}" if not pipeline_name.startswith("pipeline_") else pipeline_name
        conn = get_conn()
        cur  = conn.cursor()
        cur.execute("""
            UPDATE airflow_pipeline_runs
            SET    schedule      = COALESCE(%s, schedule),
                   table_name    = COALESCE(%s, table_name),
                   operation     = COALESCE(%s, operation)
            WHERE  dag_id = %s
        """, (updates.get("schedule"), updates.get("table_name"), updates.get("option"), dag_id))
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        print(f"DB update failed (non-critical): {e}")

    return result

# ── Pipeline version history ─────────────────────────────────────────────────

@app.get("/pipeline/{pipeline_name}/history")
def get_pipeline_history(pipeline_name: str):
    pipeline_id = _safe_pipeline_id(pipeline_name)
    return {"history": history_store.list_history("pipeline", pipeline_id)}


# ── Last-run data quality snapshot ───────────────────────────────────────
# Structured version of what utils/ingest_runner.py already writes to plain-
# text pipeline logs after every run: the df_quality (pre-ingest) and/or
# quality (post-load) gate result, each failed check already carrying a
# rule-based fix_suggestion (quality/fix_suggestions.py). Lets the Pipelines
# page render this with QualityGateSummary instead of the person having to
# read raw log text to find out why a run was blocked and what to do about it.
@app.get("/pipeline/{pipeline_name}/quality-latest")
def get_pipeline_quality_latest(pipeline_name: str):
    from quality.pipeline_quality_store import get_latest_quality_snapshot

    # Matches the PIPELINE_ID convention used by utils/dag_static_body.py
    # and utils/ingest_runner.py (see get_pipeline_logs_latest above for
    # the same normalization) — the stored pipeline_id is always
    # "pipeline_"-prefixed, but the name in the URL usually isn't.
    pipeline_id = (
        pipeline_name if pipeline_name.startswith("pipeline_")
        else f"pipeline_{pipeline_name}"
    )
    snapshot = get_latest_quality_snapshot(pipeline_id)
    if not snapshot:
        return {"pipeline": pipeline_id, "has_snapshot": False}
    return {"pipeline": pipeline_id, "has_snapshot": True, **snapshot}


# ── Source table list — powers the "pick a table" edit UI ───────────────────
# So a non-technical user editing a Postgres/Snowflake pipeline can choose a
# table from a dropdown instead of writing/reading raw SQL. Credentials are
# read server-side from the pipeline's own DAG file and never sent to the
# browser — only the resulting table names are returned.

@app.get("/pipeline/{pipeline_name}/source_tables")
def get_pipeline_source_tables(pipeline_name: str):
    creds = get_dag_source_credentials(pipeline_name)
    if creds is None:
        raise HTTPException(status_code=404, detail="Pipeline not found")

    connector_type = creds.get("connector_type")

    if connector_type == "postgres":
        if not (creds.get("src_pg_host") and creds.get("src_pg_db") and creds.get("src_pg_user")):
            raise HTTPException(status_code=400, detail="This pipeline has no Postgres credentials saved yet.")
        try:
            conn = psycopg2.connect(
                host=creds["src_pg_host"], dbname=creds["src_pg_db"],
                user=creds["src_pg_user"], password=creds.get("src_pg_password"),
                port=creds.get("src_pg_port") or "5432",
            )
            cur = conn.cursor()
            cur.execute("""
                SELECT table_name FROM information_schema.tables
                WHERE table_schema NOT IN ('pg_catalog', 'information_schema')
                ORDER BY table_name
            """)
            tables = [r[0] for r in cur.fetchall()]
            cur.close(); conn.close()
        except Exception as e:
            raise HTTPException(status_code=502, detail=f"Couldn't connect to the source database: {e}")
        return {"connector_type": connector_type, "tables": tables}

    if connector_type == "snowflake":
        if not (creds.get("sf_account") and creds.get("sf_user") and creds.get("sf_database")):
            raise HTTPException(status_code=400, detail="This pipeline has no Snowflake credentials saved yet.")
        try:
            import snowflake.connector
            conn = snowflake.connector.connect(
                account=creds["sf_account"], user=creds["sf_user"], password=creds.get("sf_password"),
                warehouse=creds.get("sf_warehouse"), database=creds.get("sf_database"),
                schema=creds.get("sf_schema") or "PUBLIC", role=creds.get("sf_role") or None,
            )
            cur = conn.cursor()
            cur.execute("SELECT table_name FROM information_schema.tables WHERE table_schema = %s ORDER BY table_name", (creds.get("sf_schema") or "PUBLIC",))
            tables = [r[0] for r in cur.fetchall()]
            cur.close(); conn.close()
        except Exception as e:
            raise HTTPException(status_code=502, detail=f"Couldn't connect to Snowflake: {e}")
        return {"connector_type": connector_type, "tables": tables}

    raise HTTPException(status_code=400, detail=f"Table listing isn't supported for '{connector_type}' pipelines yet — use custom SQL.")


@app.post("/pipeline/{pipeline_name}/restore/{version_id}")
def restore_pipeline_version(pipeline_name: str, version_id: int):
    """
    Restore = write the snapshotted .py file back verbatim (NOT a re-render
    from JSON config — config snapshots never contain passwords, see
    get_dag_config's docstring). The version being restored, and anything
    saved after it, is then dropped from history — same "no redo" rule as
    dashboard restore.
    """
    pipeline_id = _safe_pipeline_id(pipeline_name)
    version = history_store.get_version("pipeline", pipeline_id, version_id)
    if not version:
        raise HTTPException(status_code=404, detail="History version not found.")
    if not version.get("raw_content"):
        raise HTTPException(status_code=409, detail="This version has no recoverable file content.")

    result = restore_dag_raw_content(pipeline_name, version["raw_content"])
    if result.get("status") == "FAILED":
        raise HTTPException(status_code=404, detail=result)

    history_store.discard_from("pipeline", pipeline_id, version_id)
    return {"status": "SUCCESS", "restored_label": version.get("label"), "dag": result}


# ── DELETE /delete_pipeline/{pipeline_name} ──────────────────────────────────


@app.delete("/delete_pipeline/{pipeline_name}")
def delete_pipeline(pipeline_name: str):
    result = delete_dag_file(pipeline_name)

    if result.get("status") == "FAILED":
        raise HTTPException(status_code=404, detail=result)

    return result

# ── GET /pipelines ────────────────────────────────────────────────────────────

@app.get("/pipelines")
def list_pipelines():
    """
    List of all generated pipeline files.
    """
    return {
        "status":    "SUCCESS",
        "pipelines": list_dag_files()
    }

@app.get("/tables")
def list_preview_tables():
    """
    List every table in the app's own Postgres (public schema) that
    /table/{table_name} can preview. Frontend's table dropdown calls this
    instead of asking the user to type a table name from memory.
    """
    conn = get_conn()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT table_name FROM information_schema.tables
            WHERE table_schema = 'public'
            ORDER BY table_name
        """)
        tables = [row[0] for row in cursor.fetchall()]
        return {"tables": tables}
    finally:
        conn.close()


@app.get("/table/{table_name}/columns")
def list_table_columns(table_name: str):
    """
    List the columns of one table, so the frontend's filter-column dropdown
    can offer exact, valid names instead of free-text (which was the main
    cause of 'filter_col not found' errors from typos/casing mismatches).
    """
    if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', table_name):
        raise HTTPException(status_code=400, detail=f"Invalid table name '{table_name}'.")
    conn = get_conn()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT column_name, data_type FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = %s
            ORDER BY ordinal_position
        """, (table_name,))
        rows = cursor.fetchall()
        if not rows:
            raise HTTPException(status_code=404, detail=f"Table '{table_name}' not found.")
        return {"table": table_name, "columns": [{"name": r[0], "type": r[1]} for r in rows]}
    except HTTPException:
        raise
    finally:
        conn.close()


@app.get("/table/{table_name}/columns/{column_name}/values")
def list_column_values(table_name: str, column_name: str, limit: int = Query(500, ge=1, le=2000)):
    """
    Distinct values of one column, so the frontend's filter-value field can
    be a dropdown of values that actually exist — the user picks a real
    value instead of typing one, which is why filtering can just always be
    an exact match (no separate 'contains' mode needed).
    """
    if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', table_name):
        raise HTTPException(status_code=400, detail=f"Invalid table name '{table_name}'.")

    conn = get_conn()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT column_name FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = %s
        """, (table_name,))
        valid_columns = {row[0] for row in cursor.fetchall()}
        if not valid_columns:
            raise HTTPException(status_code=404, detail=f"Table '{table_name}' not found.")

        resolved_column = {c.lower(): c for c in valid_columns}.get(column_name.lower())
        if not resolved_column:
            raise HTTPException(status_code=400, detail=f"Column '{column_name}' not found in '{table_name}'.")

        query = sql.SQL("""
            SELECT DISTINCT CAST({col} AS TEXT) AS v FROM {table}
            WHERE {col} IS NOT NULL
            ORDER BY v
            LIMIT %s
        """).format(col=sql.Identifier(resolved_column), table=sql.Identifier(table_name))
        cursor.execute(query, [limit])
        values = [row[0] for row in cursor.fetchall()]
        return {"table": table_name, "column": resolved_column, "values": values}
    except HTTPException:
        raise
    finally:
        conn.close()


@app.get("/table/{table_name}")
def get_table_data(
    table_name: str,
    limit:  int            = Query(50,   ge=1, le=1000),
    offset: int            = Query(0,    ge=0),
    sort_by: Optional[str] = Query(None),
    order:   str           = Query("asc", pattern="^(asc|desc)$"),
    filter_col: List[str]  = Query([], description="Repeatable — one entry per filter, paired by position with filter_val"),
    filter_val: List[str]  = Query([], description="Repeatable — one entry per filter, paired by position with filter_col"),
):
    conn   = get_conn()
    cursor = conn.cursor()

    try:
        # ── 1. Validate table name ─────────────────────────────────────
        if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', table_name):
            raise HTTPException(status_code=400, detail=f"Invalid table name '{table_name}'.")

        cursor.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables
                WHERE table_schema = 'public' AND table_name = %s
            )
        """, (table_name,))
        if not cursor.fetchone()[0]:
            raise HTTPException(status_code=404, detail=f"Table '{table_name}' not found.")

        # ── 2. Validate sort_by / filter_col (case-insensitive lookup —
        #    a user or dropdown may send 'Status' while Postgres stores
        #    'status'; resolve to the real, correctly-cased column name so
        #    a harmless casing mismatch doesn't silently produce a 400 or,
        #    worse, get passed uncorrected into sql.Identifier) ───────────
        cursor.execute("""
            SELECT column_name FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = %s
        """, (table_name,))
        valid_columns = {row[0] for row in cursor.fetchall()}
        columns_by_lower = {c.lower(): c for c in valid_columns}

        if sort_by:
            resolved_sort = columns_by_lower.get(sort_by.lower())
            if not resolved_sort:
                raise HTTPException(status_code=400, detail=f"sort_by column '{sort_by}' not found in table.")
            sort_by = resolved_sort

        if len(filter_col) != len(filter_val):
            raise HTTPException(
                status_code=400,
                detail="filter_col and filter_val must have the same number of entries (one filter_val per filter_col).",
            )

        # ── 3. Build base query — one AND'ed condition per (filter_col,
        #    filter_val) pair. Values come from the /columns/{col}/values
        #    dropdown, i.e. they're real values already, so this is always
        #    an exact match — no separate 'contains' mode needed. Still
        #    case-insensitive (ILIKE without wildcards) so a value typed
        #    directly via the API doesn't fail on casing alone. filter_val
        #    is always passed as a bound parameter — never interpolated. ──
        where_parts = []
        params: List[Any] = []
        resolved_filters = []

        for col, val in zip(filter_col, filter_val):
            resolved_col = columns_by_lower.get(col.lower())
            if not resolved_col:
                raise HTTPException(status_code=400, detail=f"filter_col '{col}' not found in table.")
            where_parts.append(sql.SQL("CAST({c} AS TEXT) ILIKE %s").format(c=sql.Identifier(resolved_col)))
            params.append(val)
            resolved_filters.append({"col": resolved_col, "val": val})

        where_clause = sql.SQL("")
        if where_parts:
            where_clause = sql.SQL("WHERE ") + sql.SQL(" AND ").join(where_parts)

        count_params = list(params)
        data_params  = list(params)

        # ── 4. Total count (for pagination metadata) ───────────────────
        count_query = sql.SQL("SELECT COUNT(*) FROM {table} {where}").format(
            table=sql.Identifier(table_name),
            where=where_clause,
        )
        cursor.execute(count_query, count_params)
        total = cursor.fetchone()[0]

        # ── 5. Main data query with sort + limit + offset ──────────────
        order_clause = sql.SQL("ORDER BY {col} {dir}").format(
            col=sql.Identifier(sort_by) if sort_by else sql.Identifier(list(valid_columns)[0]),
            dir=sql.SQL("DESC" if order == "desc" else "ASC"),
        ) if sort_by else sql.SQL("")

        data_query = sql.SQL(
            "SELECT * FROM {table} {where} {order} LIMIT %s OFFSET %s"
        ).format(
            table=sql.Identifier(table_name),
            where=where_clause,
            order=order_clause,
        )
        data_params.extend([limit, offset])
        cursor.execute(data_query, data_params)

        rows = cursor.fetchall()
        cols = [desc[0] for desc in cursor.description]
        data = [dict(zip(cols, row)) for row in rows]

        # ── 6. Response with pagination metadata ───────────────────────
        return {
            "table":      table_name,
            "columns":    sorted(valid_columns),
            "pagination": {
                "total":    total,
                "limit":    limit,
                "offset":   offset,
                "has_more": (offset + limit) < total,
                "page":     (offset // limit) + 1,
                "pages":    -(-total // limit),   # ceiling division
            },
            "filters": resolved_filters,
            "sort": {
                "col":   sort_by,
                "order": order,
            },
            "row_count": len(data),
            "data":      data,
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()

# ─────────────────────────────────────────────────────────────────────────────
# DAG PAUSE / UNPAUSE
# ─────────────────────────────────────────────────────────────────────────────


@app.patch("/pipeline/{pipeline_name}/pause")
def pause_pipeline(pipeline_name: str):
    dag_id = pipeline_name if pipeline_name.startswith("pipeline_") else f"pipeline_{pipeline_name}"
    url = f"{AIRFLOW_BASE}/{dag_id}"
    res = requests.patch(url, json={"is_paused": True}, auth=AIRFLOW_AUTH)
    data = res.json()

    if res.status_code != 200:
        raise HTTPException(status_code=res.status_code, detail=data)

    return {"status": "PAUSED", "dag_id": dag_id, "message": f"Pipeline '{dag_id}' paused."}




@app.patch("/pipeline/{pipeline_name}/unpause")
def unpause_pipeline(pipeline_name: str):
    dag_id = pipeline_name if pipeline_name.startswith("pipeline_") else f"pipeline_{pipeline_name}"
    url = f"{AIRFLOW_BASE}/{dag_id}"
    res = requests.patch(url, json={"is_paused": False}, auth=AIRFLOW_AUTH)
    data = res.json()

    if res.status_code != 200:
        raise HTTPException(status_code=res.status_code, detail=data)

    return {"status": "ACTIVE", "dag_id": dag_id, "message": f"Pipeline '{dag_id}' is active."}



@app.get("/pipeline/{pipeline_name}/status")
def pipeline_status(pipeline_name: str):
    """
    DAG  current status  — paused / active.
    Example: GET /pipeline/hr_analytics_testing/status
    """
    dag_id = pipeline_name if pipeline_name.startswith("pipeline_") else f"pipeline_{pipeline_name}"

    url    = f"{AIRFLOW_BASE}/{dag_id}"

    res  = requests.get(url, auth=AIRFLOW_AUTH)
    data = res.json()

    if res.status_code != 200:
        raise HTTPException(status_code=res.status_code, detail=data)

    return {
        "dag_id":    dag_id,
        "is_paused": data.get("is_paused"),
        "status":    "PAUSED" if data.get("is_paused") else "ACTIVE",
        "next_run":  data.get("next_dagrun"),
    }

##### these are helper functions for the connectors and should ideally be in their respective files, but keeping here for now to avoid merge conflicts with recent edits in connectors/google_sheets_connector.py

@app.get("/pipeline/{pipeline_name}/runs")
def get_pipeline_runs(
    pipeline_name: str,
    limit: int = 20,
    offset: int = 0,
    status: Optional[str] = None,       # filter by: success, failed, running
):
    """
    Get all historical runs for a specific pipeline.

    Examples:
        GET /pipeline/hr_data_csv/runs
        GET /pipeline/hr_data_csv/runs?limit=10&offset=0
        GET /pipeline/hr_data_csv/runs?status=failed
    """
    dag_id = pipeline_name if pipeline_name.startswith("pipeline_") else f"pipeline_{pipeline_name}"

    conn = get_conn()
    cur  = conn.cursor()

    try:
        # Build query with optional status filter
        base_query = """
            SELECT
                id,
                dag_id,
                dag_run_id,
                pipeline_name,
                connector_type,
                file_path,
                folder_path,
                sheet_url,
                api_url,
                operation,
                table_name,
                schedule,
                status,
                triggered_by,
                execution_date,
                created_at
            FROM airflow_pipeline_runs
            WHERE dag_id = %s
        """
        params = [dag_id]

        if status:
            base_query += " AND UPPER(status) = %s"
            params.append(status.upper())

        base_query += " ORDER BY created_at DESC LIMIT %s OFFSET %s"
        params.extend([limit, offset])

        cur.execute(base_query, params)
        rows = cur.fetchall()
        cols = [desc[0] for desc in cur.description]

        # Total count (for pagination)
        count_query = "SELECT COUNT(*) FROM airflow_pipeline_runs WHERE dag_id = %s"
        count_params = [dag_id]
        if status:
            count_query += " AND UPPER(status) = %s"
            count_params.append(status.upper())

        cur.execute(count_query, count_params)
        total = cur.fetchone()[0]

        runs = [dict(zip(cols, row)) for row in rows]

        # Summary stats
        cur.execute("""
            SELECT
                COUNT(*)                                         AS total_runs,
                COUNT(*) FILTER (WHERE UPPER(status) = 'SUCCESS') AS success_count,
                COUNT(*) FILTER (WHERE UPPER(status) = 'FAILED')  AS failed_count,
                COUNT(*) FILTER (WHERE UPPER(status) = 'RUNNING') AS running_count,
                MAX(created_at)                                  AS last_run_at
            FROM airflow_pipeline_runs
            WHERE dag_id = %s
        """, [dag_id])

        stats_row = cur.fetchone()
        stats = {
            "total_runs":    stats_row[0],
            "success_count": stats_row[1],
            "failed_count":  stats_row[2],
            "running_count": stats_row[3],
            "last_run_at":   stats_row[4].isoformat() if stats_row[4] else None,
        }

        return {
            "pipeline":   dag_id,
            "stats":      stats,
            "pagination": {
                "total":   total,
                "limit":   limit,
                "offset":  offset,
                "has_more": (offset + limit) < total,
            },
            "runs": runs,
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    finally:
        cur.close()
        conn.close()

import glob as _glob

def _read_log_from_filesystem(pipeline_id: str, dag_run_id: str = None) -> dict:
    """
    Fallback — read log directly from Airflow log files
    when DB has no entry yet (e.g. run still in progress).
    """
    if dag_run_id:
        # specific run
        pattern = (
            f"E:\\Universal_data_connector_system\\airflow\\logs\\"
            f"dag_id={pipeline_id}\\run_id={dag_run_id}"
            f"\\task_id=run_connector\\attempt=*.log"
        )
    else:
        # latest run — wildcard on run_id
        pattern = (
            f"E:\\Universal_data_connector_system\\airflow\\logs\\"
            f"dag_id={pipeline_id}\\run_id=*"
            f"\\task_id=run_connector\\attempt=*.log"
        )

    log_files = sorted(_glob.glob(pattern))
    if not log_files:
        return {"source": "filesystem", "log_content": None, "log_file_path": None}

    latest = log_files[-1]
    try:
        with open(latest, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()
        return {"source": "filesystem", "log_content": content, "log_file_path": latest}
    except Exception as e:
        return {"source": "filesystem", "log_content": f"Could not read: {e}", "log_file_path": latest}


@app.get("/pipeline/{pipeline_name}/logs")
def get_pipeline_logs_latest(pipeline_name: str, limit: int = Query(10, ge=1, le=100)):
    """
    Get the most recent `limit` log entries for a pipeline.
    Tries DB first, falls back to filesystem (single entry) if DB has none.
 
    Example: GET /pipeline/hr_data_csv/logs?limit=20
    """
    pipeline_id = (
        pipeline_name
        if pipeline_name.startswith("pipeline_")
        else f"pipeline_{pipeline_name}"
    )
 
    conn = get_conn()
    cur  = conn.cursor()
 
    try:
        cur.execute("""
            SELECT
                l.id, l.pipeline_id, l.dag_run_id, l.task_id,
                l.status, l.log_content, l.log_file_path, l.created_at
            FROM pipeline_dag_logs l
            WHERE l.pipeline_id = %s
            ORDER BY l.created_at DESC
            LIMIT %s
        """, (pipeline_id, limit))
 
        rows = cur.fetchall()
 
        if rows:
            cols = [desc[0] for desc in cur.description]
            logs_list = [dict(zip(cols, row)) for row in rows]
            return {
                "pipeline":  pipeline_id,
                "source":    "db",
                "count":     len(logs_list),
                "logs": [
                    {
                        "dag_run_id": entry["dag_run_id"],
                        "status":     entry["status"],
                        "log_file":   entry["log_file_path"],
                        "log":        entry["log_content"],
                        "logged_at":  entry["created_at"],
                    }
                    for entry in logs_list
                ],
            }
 
        # fallback to filesystem — only one entry available this way
        fs = _read_log_from_filesystem(pipeline_id)
        if fs["log_content"]:
            return {
                "pipeline": pipeline_id,
                "source":   "filesystem",
                "count":    1,
                "logs": [
                    {
                        "dag_run_id": None,
                        "status":     None,
                        "log_file":   fs["log_file_path"],
                        "log":        fs["log_content"],
                        "logged_at":  None,
                    }
                ],
            }
 
        raise HTTPException(
            status_code=404,
            detail=f"No logs found for pipeline '{pipeline_id}'. Has it run yet?"
        )
 
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        cur.close()
        conn.close()
# ─────────────────────────────────────────────
# GET /pipeline/{name}/logs/{dag_run_id}
# Returns logs for a specific run
# ─────────────────────────────────────────────

@app.get("/pipeline/{pipeline_name}/logs/{dag_run_id:path}")
def get_pipeline_logs_by_run(pipeline_name: str, dag_run_id: str):
    """
    Get logs of a specific run by dag_run_id.
    Tries DB first, falls back to filesystem.

    Example: GET /pipeline/hr_data_csv/logs/run__pipeline_hr_data_csv__20260324_103000
    """
    pipeline_id = (
        pipeline_name
        if pipeline_name.startswith("pipeline_")
        else f"pipeline_{pipeline_name}"
    )

    conn = get_conn()
    cur  = conn.cursor()

    try:
        cur.execute("""
            SELECT
                l.id, l.pipeline_id, l.dag_run_id, l.task_id,
                l.status, l.log_content, l.log_file_path, l.created_at
            FROM pipeline_dag_logs l
            WHERE l.pipeline_id = %s
              AND l.dag_run_id   = %s
            ORDER BY l.created_at DESC
            LIMIT 1
        """, (pipeline_id, dag_run_id))

        row = cur.fetchone()

        if row:
            cols = [desc[0] for desc in cur.description]
            data = dict(zip(cols, row))
            return {
                "pipeline":  pipeline_id,
                "source":    "db",
                "dag_run_id": data["dag_run_id"],
                "status":    data["status"],
                "log_file":  data["log_file_path"],
                "log":       data["log_content"],
                "logged_at": data["created_at"],
            }

        # fallback to filesystem
        fs = _read_log_from_filesystem(pipeline_id, dag_run_id)
        if fs["log_content"]:
            return {
                "pipeline":  pipeline_id,
                "source":    "filesystem",
                "dag_run_id": dag_run_id,
                "status":    None,
                "log_file":  fs["log_file_path"],
                "log":       fs["log_content"],
                "logged_at": None,
            }

        raise HTTPException(
            status_code=404,
            detail=f"No logs found for run '{dag_run_id}' in pipeline '{pipeline_id}'."
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        cur.close()
        conn.close()

# metrics endpoint to get historical performance data for a pipeline

@app.get("/metrics/{pipeline_id}")
def get_pipeline_metrics(pipeline_id: str, limit: int = 20):
    """Latest N runs metrics for a pipeline."""
    conn = get_conn()
    cur  = conn.cursor()

    pipeline_id = pipeline_id if pipeline_id.startswith("pipeline_") \
                  else f"pipeline_{pipeline_id}"

    cur.execute("""
        SELECT
            status,
            rows_inserted,
            rows_skipped,
            duration_sec,
            evolved_columns,
            match_pct,
            file_name,
            error_message,
            logged_at
        FROM pipeline_metrics
        WHERE pipeline_id = %s
        ORDER BY logged_at DESC
        LIMIT %s
    """, (pipeline_id, limit))

    rows = cur.fetchall()
    cols = [d[0] for d in cur.description]
    conn.close()

    return {"pipeline": pipeline_id, "runs": [dict(zip(cols, r)) for r in rows]}

# aggregated metrics summary for all pipelines
@app.get("/metrics/summary/all")
def get_all_metrics_summary():
    """All pipelines aggregated summary."""
    conn = get_conn()
    cur  = conn.cursor()

    cur.execute("""
        SELECT
            pipeline_id,
            connector_type,
            COUNT(*)                                            AS total_runs,
            SUM(rows_inserted)                                  AS total_rows,
            ROUND(AVG(duration_sec)::numeric, 2)               AS avg_duration_sec,
            COUNT(*) FILTER (WHERE status = 'SUCCESS')          AS success_count,
            COUNT(*) FILTER (WHERE status = 'FAILED')           AS failed_count,
            ROUND(AVG(match_pct)::numeric, 1)                  AS avg_match_pct,
            MAX(logged_at)                                      AS last_run_at
        FROM pipeline_metrics
        GROUP BY pipeline_id, connector_type
        ORDER BY last_run_at DESC
    """)

    rows = cur.fetchall()
    cols = [d[0] for d in cur.description]
    conn.close()

    return {"summary": [dict(zip(cols, r)) for r in rows]}

@app.get("/dashboard/summary")
def dashboard_summary():
    conn = get_conn()
    cur  = conn.cursor()

    try:
        # ── 1. Metric cards (last 24h) ────────────────────────────
        cur.execute("""
            SELECT
                COUNT(*)                                              AS total_runs,
                COUNT(*) FILTER (WHERE status = 'SUCCESS')           AS success,
                COUNT(*) FILTER (WHERE status = 'FAILED')            AS failed,
                COUNT(*) FILTER (WHERE status = 'SKIPPED')           AS skipped,
                COALESCE(SUM(rows_inserted), 0)                      AS total_rows,
                ROUND(AVG(duration_sec)::numeric, 2)                 AS avg_duration,
                ROUND(
                    COUNT(*) FILTER (WHERE status = 'SUCCESS') * 100.0
                    / NULLIF(COUNT(*), 0), 1
                )                                                     AS success_rate_pct
            FROM pipeline_metrics
            WHERE logged_at >= NOW() - INTERVAL '7 days'
        """)
        metrics = dict(zip([d[0] for d in cur.description], cur.fetchone()))

        # ── 2. System health ──────────────────────────────────────
        cur.execute("""
            SELECT
                CASE
                    WHEN COUNT(*) FILTER (WHERE status = 'FAILED'
                         AND logged_at >= NOW() - INTERVAL '1 hour') > 0
                    THEN 'DEGRADED'
                    WHEN COUNT(*) FILTER (WHERE status = 'FAILED'
                         AND logged_at >= NOW() - INTERVAL '7 days') > 3
                    THEN 'WARNING'
                    ELSE 'HEALTHY'
                END AS system_health
            FROM pipeline_metrics
        """)
        health = cur.fetchone()[0]

        # ── 3. Last 7 days daily breakdown ────────────────────────
        cur.execute("""
            SELECT
                DATE(logged_at)                                       AS day,
                COUNT(*) FILTER (WHERE status = 'SUCCESS')           AS success,
                COUNT(*) FILTER (WHERE status = 'FAILED')            AS failed,
                COUNT(*) FILTER (WHERE status = 'SKIPPED')           AS skipped,
                COALESCE(SUM(rows_inserted), 0)                      AS rows
            FROM pipeline_metrics
            WHERE logged_at >= NOW() - INTERVAL '7 days'
            GROUP BY DATE(logged_at)
            ORDER BY day
        """)
        rows = cur.fetchall()
        cols = [d[0] for d in cur.description]
        daily = [dict(zip(cols, r)) for r in rows]

        # ── 4. Hourly trend (last 24h) ────────────────────────────
        cur.execute("""
            SELECT
                DATE_TRUNC('hour', logged_at)                        AS hour,
                COUNT(*)                                             AS total,
                COUNT(*) FILTER (WHERE status = 'SUCCESS')           AS success,
                COUNT(*) FILTER (WHERE status = 'FAILED')            AS failed,
                COALESCE(SUM(rows_inserted), 0)                      AS rows
            FROM pipeline_metrics
            WHERE logged_at >= NOW() - INTERVAL '24 hours'
            GROUP BY DATE_TRUNC('hour', logged_at)
            ORDER BY hour
        """)
        rows = cur.fetchall()
        cols = [d[0] for d in cur.description]
        hourly = [dict(zip(cols, r)) for r in rows]

        # ── 5. Connector breakdown ────────────────────────────────
        cur.execute("""
            SELECT
                connector_type,
                COUNT(*)                                             AS runs,
                ROUND(AVG(duration_sec)::numeric, 2)                AS avg_dur,
                COALESCE(SUM(rows_inserted), 0)                     AS total_rows,
                ROUND(
                    COUNT(*) FILTER (WHERE status = 'SUCCESS') * 100.0
                    / NULLIF(COUNT(*), 0), 1
                )                                                    AS success_rate
            FROM pipeline_metrics
            GROUP BY connector_type
            ORDER BY runs DESC
        """)
        rows = cur.fetchall()
        cols = [d[0] for d in cur.description]
        connectors = [dict(zip(cols, r)) for r in rows]

        # ── 6. Per pipeline health ────────────────────────────────
        cur.execute("""
            SELECT
                pipeline_id,
                connector_type,
                COUNT(*)                                             AS total_runs,
                COUNT(*) FILTER (WHERE status = 'SUCCESS')          AS success,
                COUNT(*) FILTER (WHERE status = 'FAILED')           AS failed,
                ROUND(
                    COUNT(*) FILTER (WHERE status = 'SUCCESS') * 100.0
                    / NULLIF(COUNT(*), 0), 1
                )                                                    AS success_rate,
                ROUND(AVG(duration_sec)::numeric, 2)                AS avg_duration,
                (ARRAY_AGG(status ORDER BY logged_at DESC))[1]      AS last_status,
                MAX(logged_at)                                       AS last_run_at
            FROM pipeline_metrics
            GROUP BY pipeline_id, connector_type
            ORDER BY last_run_at DESC
        """)
        rows = cur.fetchall()
        cols = [d[0] for d in cur.description]
        pipeline_health = [dict(zip(cols, r)) for r in rows]

        # ── 7. Top failing pipelines ──────────────────────────────
        cur.execute("""
            SELECT
                pipeline_id,
                COUNT(*)                                             AS fail_count,
                MAX(error_message)                                   AS last_error,
                MAX(logged_at)                                       AS last_failed_at
            FROM pipeline_metrics
            WHERE status = 'FAILED'
              AND logged_at >= NOW() - INTERVAL '7 days'
            GROUP BY pipeline_id
            ORDER BY fail_count DESC
            LIMIT 5
        """)
        rows = cur.fetchall()
        cols = [d[0] for d in cur.description]
        top_failing = [dict(zip(cols, r)) for r in rows]

        # ── 8. Data volume trend (last 30 days) ───────────────────
        cur.execute("""
            SELECT
                DATE(logged_at)                                      AS day,
                COALESCE(SUM(rows_inserted), 0)                     AS total_rows,
                COUNT(*)                                             AS runs
            FROM pipeline_metrics
            WHERE logged_at >= NOW() - INTERVAL '30 days'
              AND status = 'SUCCESS'
            GROUP BY DATE(logged_at)
            ORDER BY day
        """)
        rows = cur.fetchall()
        cols = [d[0] for d in cur.description]
        volume_trend = [dict(zip(cols, r)) for r in rows]

        # ── 9. Recent runs ────────────────────────────────────────
        cur.execute("""
            SELECT
                pipeline_id,
                connector_type,
                status,
                rows_inserted,
                duration_sec,
                error_message,
                logged_at
            FROM pipeline_metrics
            ORDER BY logged_at DESC
            LIMIT 20
        """)
        rows = cur.fetchall()
        cols = [d[0] for d in cur.description]
        recent = [dict(zip(cols, r)) for r in rows]

        return {
            "system_health":   health,           # HEALTHY / WARNING / DEGRADED
            "metrics":         metrics,           # 24h summary + success_rate_pct
            "daily":           daily,             # last 7 days
            "hourly":          hourly,            # last 24h hour by hour
            "connectors":      connectors,        # per connector breakdown
            "pipeline_health": pipeline_health,   # per pipeline success rate
            "top_failing":     top_failing,       # worst 5 pipelines
            "volume_trend":    volume_trend,      # 30 day row volume
            "recent_runs":     recent,            # last 20 runs
        }

    finally:
        cur.close()
        conn.close()

@app.get("/health")
def health_check():
    try:
        conn = get_conn()
        conn.close()
        db_status = "ok"
    except:
        db_status = "unreachable"

    return {
        "status":    "ok" if db_status == "ok" else "degraded",
        "database":  db_status,
        "timestamp": datetime.now().isoformat(),
        "version":   "1.7"
    }

# ─────────────────────────────────────────────────────────────────────────────
# CHATBOT ENDPOINT
# ─────────────────────────────────────────────────────────────────────────────

DEFAULT_OPENROUTER_KEY   = os.getenv("OPENROUTER_KEY", "")
DEFAULT_OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "")

class ChatMessage(BaseModel):
    role:    str   # "user" or "assistant"
    content: str
class ChatRequest(BaseModel):
    messages:       List[ChatMessage]
    openrouter_key: Optional[str] = None   # falls back to DEFAULT_OPENROUTER_KEY if not sent
    model:          Optional[str] = None   # falls back to DEFAULT_OPENROUTER_MODEL if not sent
    pipeline_name:  Optional[str] = None

# ─────────────────────────────────────────────────────────────────────────────
# 1. Question-type detection — simple keyword based, no LLM call needed
# ─────────────────────────────────────────────────────────────────────────────
 
def _extract_pipeline_name_from_text(question: str) -> Optional[str]:
    """
    Fallback extractor: if the user mentions a pipeline name directly in
    their question (e.g. "pipeline_fright", "pipeline_user_csv pipeline"),
    pull it out so _build_db_context can scope to it even when the
    dedicated pipeline_name field wasn't set.
    """
    # Matches "pipeline_xxx" or "pipeline xxx" (word chars/underscores after)
    match = re.search(r'pipeline[_\s]+([a-zA-Z0-9_]+)', question, re.IGNORECASE)
    if match:
        name = match.group(1).strip()
        # avoid capturing trailing words like "pipeline_xxx pipeline runs"
        # by stripping a trailing standalone "pipeline" if it got captured
        return name
    return None
 
 
def _detect_question_type(question: str) -> set:
    """
    Look at the user's question text and decide which context sections are
    actually relevant, so we skip unnecessary DB queries.
 
    Returns a set of any combination of: {"counts", "errors", "general"}.
    Defaults to {"counts", "errors", "general"} if nothing specific is
    detected, so ambiguous questions still get full context.
    """
    q = question.lower()
    types = set()
 
    count_words  = ["how many", "how often", "count", "total", "success rate",
                    "average", "avg", "sum", "rows inserted", "duration"]
    error_words  = ["error", "fail", "failed", "failing", "why did", "wrong",
                    "broke", "broken", "issue", "problem", "traceback", "exception"]
    general_words = ["status", "health", "running", "active", "schedule",
                      "recent", "latest", "overview", "summary"]
 
    if any(w in q for w in count_words):
        types.add("counts")
    if any(w in q for w in error_words):
        types.add("errors")
    if any(w in q for w in general_words):
        types.add("general")
 
    if not types:
        # ambiguous question — safer to include everything than to miss context
        types = {"counts", "errors", "general"}
 
    return types
 
 
# ─────────────────────────────────────────────────────────────────────────────
# 2. _build_db_context() — full replacement, now question-aware
# ─────────────────────────────────────────────────────────────────────────────
 
def _build_db_context(pipeline_name: Optional[str] = None, question: str = "") -> str:
    """
    Build context for the LLM, but only run the DB queries relevant to the
    kind of question being asked — keeps context small and queries fast.
    """
    parts = []
    conn  = get_conn()
    cur   = conn.cursor()
 
    qtypes = _detect_question_type(question) if question else {"counts", "errors", "general"}
 
    try:
        pid = None
        if pipeline_name:
            pid = pipeline_name if pipeline_name.startswith("pipeline_") else f"pipeline_{pipeline_name}"
 
        # ── COUNTS: exact totals, no LIMIT truncation ──────────────────────────
        if "counts" in qtypes:
            if pid:
                cur.execute("""
                    SELECT
                        COUNT(*)                                              AS total_runs,
                        COUNT(*) FILTER (WHERE UPPER(status) = 'SUCCESS')    AS success_count,
                        COUNT(*) FILTER (WHERE UPPER(status) = 'FAILED')     AS failed_count,
                        COUNT(*) FILTER (WHERE UPPER(status) = 'RUNNING')    AS running_count,
                        COUNT(*) FILTER (WHERE UPPER(status) = 'SKIPPED')    AS skipped_count,
                        MIN(created_at)                                       AS first_run_at,
                        MAX(created_at)                                       AS last_run_at
                    FROM airflow_pipeline_runs
                    WHERE dag_id = %s
                """, (pid,))
                row = cur.fetchone()
                if row and row[0]:
                    parts.append("\n".join([
                        f"=== EXACT STATS for {pid} (full history, not limited) ===",
                        f"Total runs : {row[0]}",
                        f"Success    : {row[1]}",
                        f"Failed     : {row[2]}",
                        f"Running    : {row[3]}",
                        f"Skipped    : {row[4]}",
                        f"First run  : {row[5]}",
                        f"Last run   : {row[6]}",
                    ]))
                else:
                    parts.append(f"=== EXACT STATS for {pid} ===\nNo runs found for this pipeline yet.")
 
                cur.execute("""
                    SELECT
                        COUNT(*)                                              AS total_runs,
                        COALESCE(SUM(rows_inserted), 0)                       AS total_rows_inserted,
                        ROUND(AVG(duration_sec)::numeric, 2)                  AS avg_duration_sec
                    FROM pipeline_metrics
                    WHERE pipeline_id = %s
                """, (pid,))
                row2 = cur.fetchone()
                if row2 and row2[0]:
                    parts.append("\n".join([
                        f"=== EXACT METRICS for {pid} (full history, not limited) ===",
                        f"Total runs logged   : {row2[0]}",
                        f"Total rows inserted : {row2[1]:,}",
                        f"Avg duration (sec)  : {row2[2]}",
                    ]))
            else:
                cur.execute("""
                    SELECT
                        dag_id,
                        COUNT(*)                                              AS total_runs,
                        COUNT(*) FILTER (WHERE UPPER(status) = 'SUCCESS')    AS success_count,
                        COUNT(*) FILTER (WHERE UPPER(status) = 'FAILED')     AS failed_count
                    FROM airflow_pipeline_runs
                    GROUP BY dag_id
                    ORDER BY total_runs DESC
                """)
                rows = cur.fetchall()
                if rows:
                    lines = ["=== EXACT PER-PIPELINE RUN COUNTS (all pipelines, full history) ==="]
                    for r in rows:
                        lines.append(f"{r[0]}: total={r[1]} | success={r[2]} | failed={r[3]}")
                    parts.append("\n".join(lines))
 
        # ── ERRORS: full raw log content for recent failures ───────────────────
        if "errors" in qtypes:
            if pid:
                cur.execute("""
                    SELECT dag_run_id, status, log_content, created_at
                    FROM pipeline_dag_logs
                    WHERE pipeline_id = %s AND UPPER(status) = 'FAILED'
                    ORDER BY created_at DESC
                    LIMIT 3
                """, (pid,))
                failed_logs = cur.fetchall()
                if failed_logs:
                    lines = [f"=== MOST RECENT FAILED RUN LOGS for {pid} (full raw content) ==="]
                    for dag_run_id, status, log_content, created_at in failed_logs:
                        lines.append(f"\n--- Run: {dag_run_id} | {created_at} ---")
                        lines.append(str(log_content or "")[:3000])
                    parts.append("\n".join(lines))
                else:
                    cur.execute("""
                        SELECT dag_run_id, error_message, created_at
                        FROM airflow_pipeline_runs
                        WHERE dag_id = %s AND error_message IS NOT NULL AND error_message != ''
                        ORDER BY created_at DESC
                        LIMIT 3
                    """, (pid,))
                    err_rows = cur.fetchall()
                    if err_rows:
                        lines = [f"=== RECENT ERROR MESSAGES for {pid} ==="]
                        for dag_run_id, error_message, created_at in err_rows:
                            lines.append(f"\n--- Run: {dag_run_id} | {created_at} ---")
                            lines.append(str(error_message))
                        parts.append("\n".join(lines))
                    else:
                        parts.append(f"=== ERRORS for {pid} ===\nNo failed runs or error messages found.")
            else:
                cur.execute("""
                    SELECT dag_id, dag_run_id, error_message, created_at
                    FROM airflow_pipeline_runs
                    WHERE error_message IS NOT NULL AND error_message != ''
                    ORDER BY created_at DESC
                    LIMIT 10
                """)
                err_rows = cur.fetchall()
                if err_rows:
                    lines = ["=== RECENT ERRORS ACROSS ALL PIPELINES (last 10) ==="]
                    for dag_id, dag_run_id, error_message, created_at in err_rows:
                        lines.append(f"\n--- {dag_id} | run={dag_run_id} | {created_at} ---")
                        lines.append(str(error_message)[:300])
                    parts.append("\n".join(lines))
 
        # ── GENERAL: recent activity / status, only when relevant ──────────────
        if "general" in qtypes:
            if pid:
                cur.execute("""
                    SELECT dag_run_id, status, created_at
                    FROM airflow_pipeline_runs
                    WHERE dag_id = %s
                    ORDER BY created_at DESC
                    LIMIT 5
                """, (pid,))
                recent = cur.fetchall()
                if recent:
                    lines = [f"=== LAST 5 RUNS for {pid} ==="]
                    for dag_run_id, status, created_at in recent:
                        lines.append(f"{created_at} | {status} | run={dag_run_id}")
                    parts.append("\n".join(lines))
            else:
                cur.execute("""
                    SELECT
                        COUNT(*)                                              AS total_runs,
                        COUNT(*) FILTER (WHERE status = 'SUCCESS')           AS success,
                        COUNT(*) FILTER (WHERE status = 'FAILED')            AS failed,
                        ROUND(
                            COUNT(*) FILTER (WHERE status = 'SUCCESS') * 100.0
                            / NULLIF(COUNT(*), 0), 1
                        )                                                     AS success_rate
                    FROM pipeline_metrics
                    WHERE logged_at >= NOW() - INTERVAL '24 hours'
                """)
                row = cur.fetchone()
                if row and row[0]:
                    parts.append("\n".join([
                        "=== SYSTEM SUMMARY (Last 24h) ===",
                        f"Total Runs   : {row[0]}",
                        f"Success      : {row[1]}",
                        f"Failed       : {row[2]}",
                        f"Success Rate : {row[3]}%",
                    ]))
 
        if not parts:
            parts.append("No relevant data found in the database for this question.")
 
    except Exception as e:
        parts.append(f"=== DB FETCH ERROR: {e} ===")
    finally:
        cur.close()
        conn.close()
 
    return "\n\n".join(parts)
 
 
# ─────────────────────────────────────────────────────────────────────────────
# 3. SYSTEM_PROMPT — full replacement
# ─────────────────────────────────────────────────────────────────────────────
 
SYSTEM_PROMPT = """
        You are the Pipeline Assistant for SparkBrains Universal Data Connector.
 
        Your role:
        Help users understand and debug their data pipelines using the live database context provided to you.
        The context given to you has already been filtered to match the kind of question asked — trust it.
 
        Tone:
        - Conversational, friendly, and clear, like a helpful teammate
        - Keep it concise but natural
 
        Context sections you may see:
        - "EXACT STATS" / "EXACT METRICS" / "EXACT PER-PIPELINE RUN COUNTS": precomputed counts covering the
          FULL run history with no row limit — authoritative for any counting question.
        - "MOST RECENT FAILED RUN LOGS": full raw Airflow log text for the latest failed run(s). Quote the
          specific error line directly when explaining what went wrong.
        - "RECENT ERRORS" / "LAST N RUNS": recent activity samples.
        - "SYSTEM SUMMARY": last-24h system-wide snapshot.
 
        CRITICAL RULES:
        1. For counting/totals questions: use ONLY the "EXACT STATS" / "EXACT METRICS" / "EXACT PER-PIPELINE
           RUN COUNTS" sections if present. Never estimate from a sample.
        2. For "why did it fail" questions: quote the specific error line from the raw log text directly, then
           explain in plain terms what it means and how to fix it, using your own reasoning about the error.
        3. If the context says no data was found, say so plainly: "I couldn't find any data for this — try
           running the pipeline first." Do not guess.
 
        Response Style:
        - Start with a direct answer to the question (1–2 lines)
        - Add structure only if it helps: ✅ status, ⚠️ error (quoted), 💡 suggested fix
        - Use bullet points over long paragraphs
        - Format numbers cleanly (10,000 rows, 25 sec, 92.3%)
 
        Length: 100–250 words, longer only if quoting a real error and explaining a fix.
 
        Goal: Feel like a teammate who already looked at the exact data — not a generic chatbot guessing.
        """
 
@app.post("/chatbot")
async def chatbot(req: ChatRequest):
    """
    Ask questions about your data pipelines and get insights.
    Fetches only the DB context relevant to the question type, then asks
    OpenRouter to answer using that context.
 
    OpenRouter key/model resolution order:
      1. Value sent in the request (frontend field) — always wins if present
      2. DEFAULT_OPENROUTER_KEY / DEFAULT_OPENROUTER_MODEL from backend .env
      3. If no key is available anywhere, returns a clear 400 error
    """
    effective_key   = req.openrouter_key or DEFAULT_OPENROUTER_KEY
    effective_model = req.model or DEFAULT_OPENROUTER_MODEL
 
    if not effective_key:
        raise HTTPException(
            status_code=400,
            detail=(
                "No OpenRouter API key available. Provide one in the request, "
                "or set OPENROUTER_KEY in the backend .env for a shared default."
            )
        )
 
    # Find the latest user message to use for both question-type detection
    # and context injection
    last_user_message = ""
    for msg in reversed(req.messages):
        if msg.role == "user":
            last_user_message = msg.content
            break
 
    # Fall back to extracting a pipeline name from the question text itself
    # if the dedicated pipeline_name field wasn't set. First check the
    # latest message; if it doesn't mention one, scan recent history too —
    # this keeps short follow-ups like "why it fails" working after an
    # earlier message in the same conversation named the pipeline.
    effective_pipeline_name = req.pipeline_name or _extract_pipeline_name_from_text(last_user_message)
    if not effective_pipeline_name:
        for msg in reversed(req.messages[:-1]):  # skip the message already checked above
            if msg.role == "user":
                found = _extract_pipeline_name_from_text(msg.content)
                if found:
                    effective_pipeline_name = found
                    break
 
    try:
        db_context = _build_db_context(effective_pipeline_name, last_user_message)
    except Exception as e:
        db_context = f"DB context fetch failed: {e}"
 
    messages_for_llm = [{"role": "system", "content": SYSTEM_PROMPT}]
 
    history = req.messages[-8:]
    for i, msg in enumerate(history):
        if i == len(history) - 1 and msg.role == "user":
            messages_for_llm.append({
                "role": "user",
                "content": f"""User's question: {msg.content}
 
--- DATABASE CONTEXT (Live Data from PostgreSQL) ---
{db_context}
--- END CONTEXT ---
Answer clearly and concisely based on the live data provided above.
If the context doesn't have the answer, say "Data not found in context" instead of making assumptions."""
            })
        else:
            messages_for_llm.append({"role": msg.role, "content": msg.content})
 
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {effective_key}",
                    "Content-Type":  "application/json",
                    "HTTP-Referer":  "http://localhost:8000",
                    "X-Title":       "SparkBrains Pipeline Assistant",
                },
                json={
                    "model":       effective_model,
                    "messages":    messages_for_llm,
                    "max_tokens":  1200,
                    "temperature": 0.3,
                },
            )
 
        if response.status_code == 200:
            data   = response.json()
            answer = data["choices"][0]["message"]["content"]
            return {
                "status":  "SUCCESS",
                "answer":  answer,
                "model":   effective_model,
                "context_length": len(db_context),
            }
        elif response.status_code == 401:
            raise HTTPException(status_code=401, detail="Invalid OpenRouter API key.")
        elif response.status_code == 429:
            raise HTTPException(status_code=429, detail="OpenRouter rate limit. Wait.")
        else:
            raise HTTPException(
                status_code=response.status_code,
                detail=f"OpenRouter error: {response.text[:300]}"
            )
 
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="OpenRouter request timeout.")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Chatbot error: {str(e)}")

# ─────────────────────────────────────────────────────────────────────────────
# frontend can show whether a backend
# default is configured, without exposing the actual key value.
# Add this anywhere after the /chatbot endpoint.
# ─────────────────────────────────────────────────────────────────────────────
 
@app.get("/chatbot/config")
def get_chatbot_config():
    """
    Lets the frontend know whether a backend-side default key/model is
    configured, WITHOUT ever exposing the actual key value.
    """
    return {
        "has_backend_key": bool(DEFAULT_OPENROUTER_KEY),
        "default_model":   DEFAULT_OPENROUTER_MODEL,
    }


# ── Simple context-only endpoint (without LLM ) ───────────────────────────────

@app.get("/chatbot/context")
def get_chatbot_context(pipeline_name: Optional[str] = None):
    """
    Debug  — See what context is available.
    GET /chatbot/context
    GET /chatbot/context?pipeline_name=spark1
    """
    try:
        context = _build_db_context(pipeline_name)
        return {
            "status":         "SUCCESS",
            "pipeline_name":  pipeline_name,
            "context_length": len(context),
            "context":        context,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
    # app.include_router(agent_router)



# ── Allowed tables — whitelist to prevent arbitrary table access ────────────
LOGS_TABLE_MAP = {
    "pipeline_logs":         {"order_by": "log_time",   "default_desc": True},
    "pipeline_runs":         {"order_by": "start_time", "default_desc": True},
    "airflow_pipeline_runs": {"order_by": "created_at", "default_desc": True},
    "pipeline_dag_logs":     {"order_by": "created_at", "default_desc": True},
    "pipeline_metrics":      {"order_by": "logged_at",  "default_desc": True},
}
 
 
@app.get("/logs_tables")
def list_logs_tables():
    """
    List the available log/metrics tables that /logs_table/{table_name} supports.
    Frontend dropdown should call this to populate options.
    """
    return {"tables": list(LOGS_TABLE_MAP.keys())}
 
 
@app.get("/logs_table/{table_name}")
def get_logs_table(
    table_name: str,
    limit:  int             = Query(50, ge=1, le=1000),
    offset: int             = Query(0,  ge=0),
    sort_by: Optional[str]  = Query(None),
    order:   str            = Query("desc", pattern="^(asc|desc)$"),
    filter_col: Optional[str] = Query(None),
    filter_val: Optional[str] = Query(None),
    pipeline_id: Optional[str] = Query(None),  # convenience filter, see below
):
    """
    Generic, safe viewer for any of the known log/metrics tables.
 
    Examples:
        GET /logs_table/pipeline_metrics
        GET /logs_table/airflow_pipeline_runs?limit=20&order=desc
        GET /logs_table/pipeline_dag_logs?pipeline_id=pipeline_sales_csv
        GET /logs_table/pipeline_runs?filter_col=status&filter_val=FAILED
    """
    if table_name not in LOGS_TABLE_MAP:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid table '{table_name}'. Valid: {list(LOGS_TABLE_MAP.keys())}"
        )
 
    table_cfg   = LOGS_TABLE_MAP[table_name]
    default_col = table_cfg["order_by"]
 
    conn   = get_conn()
    cursor = conn.cursor()
 
    try:
        # ── 1. Validate table actually exists in DB (defensive) ─────────────
        cursor.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables
                WHERE table_schema = 'public' AND table_name = %s
            )
        """, (table_name,))
        if not cursor.fetchone()[0]:
            raise HTTPException(status_code=404, detail=f"Table '{table_name}' not found in database.")
 
        # ── 2. Get valid columns for this table ─────────────────────────────
        cursor.execute("""
            SELECT column_name FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = %s
        """, (table_name,))
        valid_columns = {row[0] for row in cursor.fetchall()}
 
        if sort_by and sort_by not in valid_columns:
            raise HTTPException(status_code=400, detail=f"sort_by column '{sort_by}' not found in '{table_name}'.")
 
        if filter_col and filter_col not in valid_columns:
            raise HTTPException(status_code=400, detail=f"filter_col '{filter_col}' not found in '{table_name}'.")
 
        sort_col = sort_by or (default_col if default_col in valid_columns else None)
 
        # ── 3. Build WHERE clause — supports generic filter + convenience pipeline_id filter ─
        where_parts  = []
        count_params = []
        data_params  = []
 
        if pipeline_id:
            # pipeline_id convenience filter — works across tables that have
            # either 'pipeline_id' or 'dag_id' as the relevant column
            pid_col = "pipeline_id" if "pipeline_id" in valid_columns else (
                      "dag_id" if "dag_id" in valid_columns else None)
            if pid_col:
                normalized_pid = pipeline_id if pipeline_id.startswith("pipeline_") else f"pipeline_{pipeline_id}"
                where_parts.append(sql.SQL("{col} = %s").format(col=sql.Identifier(pid_col)))
                count_params.append(normalized_pid)
                data_params.append(normalized_pid)
 
        if filter_col and filter_val is not None:
            where_parts.append(sql.SQL("CAST({col} AS TEXT) ILIKE %s").format(col=sql.Identifier(filter_col)))
            like_val = f"%{filter_val}%"
            count_params.append(like_val)
            data_params.append(like_val)
 
        where_clause = sql.SQL("")
        if where_parts:
            where_clause = sql.SQL("WHERE ") + sql.SQL(" AND ").join(where_parts)
 
        # ── 4. Total count (pagination) ──────────────────────────────────────
        count_query = sql.SQL("SELECT COUNT(*) FROM {table} {where}").format(
            table=sql.Identifier(table_name),
            where=where_clause,
        )
        cursor.execute(count_query, count_params)
        total = cursor.fetchone()[0]
 
        # ── 5. Main data query ────────────────────────────────────────────────
        order_clause = sql.SQL("")
        if sort_col:
            order_clause = sql.SQL("ORDER BY {col} {dir}").format(
                col=sql.Identifier(sort_col),
                dir=sql.SQL("DESC" if order == "desc" else "ASC"),
            )
 
        data_query = sql.SQL(
            "SELECT * FROM {table} {where} {order} LIMIT %s OFFSET %s"
        ).format(
            table=sql.Identifier(table_name),
            where=where_clause,
            order=order_clause,
        )
        data_params.extend([limit, offset])
        cursor.execute(data_query, data_params)
 
        rows = cursor.fetchall()
        cols = [desc[0] for desc in cursor.description]
        data = [dict(zip(cols, row)) for row in rows]
 
        return {
            "table":      table_name,
            "columns":    sorted(valid_columns),
            "pagination": {
                "total":    total,
                "limit":    limit,
                "offset":   offset,
                "has_more": (offset + limit) < total,
                "page":     (offset // limit) + 1,
                "pages":    -(-total // limit) if total else 0,
            },
            "filter": {"col": filter_col, "val": filter_val, "pipeline_id": pipeline_id},
            "sort":   {"col": sort_col, "order": order},
            "row_count": len(data),
            "data":      data,
        }
 
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()



#### testing ####

import shutil
from fastapi import UploadFile, File

# UPLOAD_BASE_DIR = "/app/data/uploads"   # shared with Airflow via ./data host mount
UPLOAD_BASE_DIR = os.getenv("UPLOAD_BASE_DIR", str(Path(__file__).parent / "uploads"))
os.makedirs(UPLOAD_BASE_DIR, exist_ok=True)


def _safe_folder_name(name: str) -> str:
    """Sanitize a user-supplied folder name — letters, numbers, underscore, hyphen only."""
    name = (name or "").strip()
    name = re.sub(r"[^a-zA-Z0-9_\-]", "_", name)
    name = re.sub(r"_+", "_", name).strip("_")
    if not name:
        raise HTTPException(status_code=400, detail="Invalid folder name")
    return name


# ─────────────────────────────────────────────
# LIST existing upload folders
# ─────────────────────────────────────────────

@app.get("/upload_folders")
def list_upload_folders():
    """
    Lists user-created folders under /app/data/uploads/, along with the
    files currently inside each — so the frontend can show a dropdown of
    reusable folders and let the user pick one to add more files into.
    """
    if not os.path.exists(UPLOAD_BASE_DIR):
        return {"folders": []}

    folders = []
    for entry in sorted(os.listdir(UPLOAD_BASE_DIR)):
        full_path = os.path.join(UPLOAD_BASE_DIR, entry)
        if os.path.isdir(full_path):
            files = [f for f in os.listdir(full_path) if not f.startswith(".")]
            folders.append({
                "folder_name": entry,
                "folder_path": full_path,          # backend-container path — usable directly as folder_path
                "file_count":  len(files),
                "files":       sorted(files),
            })
    return {"folders": folders}


# ─────────────────────────────────────────────
# UPLOAD a file into a (new or existing) user folder
# ─────────────────────────────────────────────

@app.post("/upload_file")
async def upload_file(
    file: UploadFile = File(...),
    folder_name: str = Query(..., description="User-chosen folder name — created if it doesn't exist yet"),
):
    safe_folder = _safe_folder_name(folder_name)
    folder_path = os.path.join(UPLOAD_BASE_DIR, safe_folder)
    os.makedirs(folder_path, exist_ok=True)
    os.chmod(folder_path, 0o777)          # ← NEW — ensure Airflow container can write/delete inside this folder too

    safe_name = os.path.basename(file.filename or "")
    if not safe_name:
        raise HTTPException(status_code=400, detail="Invalid filename")

    ext = os.path.splitext(safe_name)[1].lower()
    if ext not in (".csv", ".xlsx", ".xls"):
        raise HTTPException(status_code=400, detail=f"Unsupported file type '{ext}'. Only .csv, .xlsx, .xls allowed.")

    dest_path = os.path.join(folder_path, safe_name)

    if os.path.exists(dest_path):
        name, extension = os.path.splitext(safe_name)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_name = f"{name}_{ts}{extension}"
        dest_path = os.path.join(folder_path, safe_name)

    try:
        with open(dest_path, "wb") as f:
            shutil.copyfileobj(file.file, f)
        os.chmod(dest_path, 0o666)         # ← NEW — file itself also readable/writable/deletable by any container user
    finally:
        file.file.close()

    return {
        "status":       "SUCCESS",
        "folder_name":  safe_folder,
        "folder_path":  folder_path,
        "file_name":    safe_name,
        "file_path":    dest_path,
        "size_kb":      round(os.path.getsize(dest_path) / 1024, 1),
    }

# ─────────────────────────────────────────────
# PREVIEW a CSV/Excel file — sample rows + per-column type guess, so the
# UI can show "does this look right?" and let a non-technical user build
# quality checks by clicking on real columns, instead of typing config.
# Runs BEFORE ingest — nothing is written to any table here.
# ─────────────────────────────────────────────

_TYPE_GUESS_MAP = {
    "numeric": ("Int8", "Int16", "Int32", "Int64", "UInt8", "UInt16", "UInt32", "UInt64", "Float32", "Float64"),
    "date":    ("Date", "Datetime", "Time"),
    "boolean": ("Boolean",),
}

def _guess_simple_type(polars_dtype_str: str) -> str:
    for simple, dtypes in _TYPE_GUESS_MAP.items():
        if any(polars_dtype_str.startswith(d) for d in dtypes):
            return simple
    return "text"


@app.get("/preview_file")
def preview_file(
    file_path: str = Query(...),
    connector: str = Query("csv", description="csv or excel"),
    sample_rows: int = Query(15, ge=1, le=200),
):
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found")

    try:
        if connector == "excel":
            df = excel_connector(file_path)
        else:
            df = csv_connector(file_path)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Couldn't read this file: {e}")

    total_rows = df.height
    sample = df.head(sample_rows)

    columns = []
    for col in df.columns:
        series = df[col]
        null_count = int(series.null_count())
        columns.append({
            "name": col,
            "type": _guess_simple_type(str(series.dtype)),
            "null_pct": round((null_count / total_rows) * 100, 1) if total_rows else 0.0,
            "sample_unique": int(series.n_unique()) <= sample_rows or None,  # rough hint only
        })

    # JSON-safe row dicts (dates/NaN etc. become plain strings)
    rows = []
    for row in sample.iter_rows(named=True):
        rows.append({k: ("" if v is None else str(v)) for k, v in row.items()})

    return {
        "columns": columns,
        "rows": rows,
        "total_rows": total_rows,
        "sample_row_count": len(rows),
    }

# ─────────────────────────────────────────────
# LIST the CSV/Excel files inside an arbitrary folder — used by the
# pipeline builder to show a pickable file list for quality checks, both
# for a freshly-typed folder path AND for a saved connection's base_path
# (which is just as much a real folder on disk, it just didn't come from
# the /upload_folders flow). This is deliberately NOT scoped to
# UPLOAD_BASE_DIR the way /upload_folders is, since saved connections can
# point anywhere on disk.
# ─────────────────────────────────────────────

@app.get("/list_folder_files")
def list_folder_files(folder_path: str = Query(...)):
    if not folder_path or not os.path.isdir(folder_path):
        raise HTTPException(status_code=404, detail="Folder not found")

    try:
        entries = sorted(os.listdir(folder_path))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Couldn't read folder: {e}")

    files = [
        f for f in entries
        if not f.startswith(".")
        and os.path.isfile(os.path.join(folder_path, f))
        and os.path.splitext(f)[1].lower() in (".csv", ".xlsx", ".xls")
    ]
    return {"folder_path": folder_path, "files": files}

# ─────────────────────────────────────────────
# PREVIEW any connector's data (not just CSV/Excel) — same response shape
# as /preview_file — so the friendly, per-column quality-check builder in
# CreatePipeline works for every connector, whether the credentials came
# from a brand-new connection or a saved one (via connection_id).
# Only pulls a small sample; never used for the actual ingest.
# ─────────────────────────────────────────────

class PreviewSourceRequest(BaseModel):
    connector_type: str
    connection_id: Optional[int] = None
    sample_rows: int = 15

    # csv / excel
    file_path: Optional[str] = None
    # BUGFIX: folder-based CSV/Excel pipelines (folder_path set, no single
    # file_path) had no way to preview at all — preview_source() only knew
    # about file_path, so DataQualityBuilder/SchemaBuilder always got
    # params=null for these pipelines and silently rendered nothing (see
    # SchemaBuilder.tsx's `if (!params) return null`).
    folder_path: Optional[str] = None

    # google sheets
    sheet_url: Optional[str] = None

    # api
    api_url: Optional[str] = None
    api_config: Optional[dict] = None

    # postgres
    src_pg_host: Optional[str] = None
    src_pg_db: Optional[str] = None
    src_pg_user: Optional[str] = None
    src_pg_password: Optional[str] = None
    src_pg_port: Optional[str] = "5432"
    pg_query: Optional[str] = None

    # mysql
    src_my_host: Optional[str] = None
    src_my_db: Optional[str] = None
    src_my_user: Optional[str] = None
    src_my_password: Optional[str] = None
    src_my_port: Optional[str] = "3306"
    my_query: Optional[str] = None

    # oracle
    src_ora_host: Optional[str] = None
    src_ora_db: Optional[str] = None
    src_ora_user: Optional[str] = None
    src_ora_password: Optional[str] = None
    src_ora_port: Optional[str] = "1521"
    ora_query: Optional[str] = None

    # mongodb
    src_mongo_host: Optional[str] = None
    src_mongo_db: Optional[str] = None
    src_mongo_user: Optional[str] = None
    src_mongo_password: Optional[str] = None
    src_mongo_port: Optional[str] = "27017"
    src_mongo_connection_string: Optional[str] = None
    mongo_collection: Optional[str] = None
    mongo_query: Optional[str] = None

    # s3
    s3_bucket: Optional[str] = None
    s3_key: Optional[str] = None
    s3_file_type: Optional[str] = "csv"
    s3_access_key: Optional[str] = None
    s3_secret_key: Optional[str] = None

    # snowflake
    sf_account: Optional[str] = None
    sf_user: Optional[str] = None
    sf_password: Optional[str] = None
    sf_warehouse: Optional[str] = None
    sf_database: Optional[str] = None
    sf_schema: Optional[str] = "PUBLIC"
    sf_query: Optional[str] = None
    sf_role: Optional[str] = None


def _resolve_preview_config(req: "PreviewSourceRequest") -> dict:
    """Same merge rule as _resolve_connection_config, just for the
    lightweight preview payload instead of the full CreatePipelineRequest."""
    merged = req.model_dump()
    if not req.connection_id:
        return merged

    ensure_connections_table()
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT config, source_type FROM saved_connections WHERE id = %s", (req.connection_id,))
    row = cur.fetchone()
    cur.close()
    conn.close()

    if not row:
        raise HTTPException(status_code=404, detail="Connection not found")

    config, _source_type = row
    config = config if isinstance(config, dict) else json.loads(config)

    if req.connector_type == "postgres":
        merged["src_pg_host"] = config.get("host", "")
        merged["src_pg_db"] = config.get("database", "")
        merged["src_pg_user"] = config.get("user", "")
        merged["src_pg_password"] = config.get("password", "")
        merged["src_pg_port"] = config.get("port", "5432")
    elif req.connector_type == "mysql":
        merged["src_my_host"] = config.get("host", "")
        merged["src_my_db"] = config.get("database", "")
        merged["src_my_user"] = config.get("user", "")
        merged["src_my_password"] = config.get("password", "")
        merged["src_my_port"] = config.get("port", "3306")
    elif req.connector_type == "oracle":
        merged["src_ora_host"] = config.get("host", "")
        merged["src_ora_db"] = config.get("database", "")
        merged["src_ora_user"] = config.get("user", "")
        merged["src_ora_password"] = config.get("password", "")
        merged["src_ora_port"] = config.get("port", "1521")
    elif req.connector_type == "mongodb":
        merged["src_mongo_host"] = config.get("host", "")
        merged["src_mongo_db"] = config.get("database", "")
        merged["src_mongo_user"] = config.get("user", "")
        merged["src_mongo_password"] = config.get("password", "")
        merged["src_mongo_port"] = config.get("port", "27017")
        merged["src_mongo_connection_string"] = config.get("connection_string", "")
        merged["mongo_collection"] = merged.get("mongo_collection") or config.get("collection", "")
    elif req.connector_type == "s3":
        merged["s3_bucket"] = config.get("bucket", "")
        merged["s3_key"] = config.get("prefix", "")
        merged["s3_file_type"] = config.get("file_type", "csv")
        merged["s3_access_key"] = config.get("access_key", "")
        merged["s3_secret_key"] = config.get("secret_key", "")
    elif req.connector_type == "snowflake":
        merged["sf_account"] = config.get("account", "")
        merged["sf_user"] = config.get("user", "")
        merged["sf_password"] = config.get("password", "")
        merged["sf_warehouse"] = config.get("warehouse", "")
        merged["sf_database"] = config.get("database", "")
        merged["sf_schema"] = config.get("schema", "PUBLIC")
        merged["sf_role"] = config.get("role", "")
    elif req.connector_type == "api":
        merged["api_url"] = config.get("base_url", "")
        resolved_api_config: dict = {
            "method": config.get("method", "GET"),
            "auth_type": config.get("auth_type", "none"),
        }
        auth_type = config.get("auth_type", "none")
        if auth_type == "bearer":
            resolved_api_config["bearer_token"] = config.get("api_key", "")
            resolved_api_config["bearer_prefix"] = config.get("bearer_prefix", "Bearer")
        elif auth_type == "api_key_header":
            resolved_api_config["api_key"] = config.get("api_key", "")
            resolved_api_config["header_name"] = config.get("header_name", "Authorization")
        elif auth_type == "basic":
            resolved_api_config["basic_user"] = config.get("user", "")
            resolved_api_config["basic_password"] = config.get("password", "")
        elif auth_type == "api_key_query":
            resolved_api_config["api_key"] = config.get("api_key", "")
            resolved_api_config["query_param_name"] = config.get("query_param_name", "api_key")
        if isinstance(config.get("api_advanced"), dict):
            resolved_api_config.update(config["api_advanced"])
        if merged.get("api_config"):
            resolved_api_config.update(merged["api_config"])
        merged["api_config"] = resolved_api_config
    elif req.connector_type == "google_sheets":
        merged["sheet_url"] = config.get("sheet_url", "")
    elif req.connector_type in ("csv", "excel"):
        # Saved csv/excel connections resolve to a folder, not a single
        # file — the caller lists the folder (/list_folder_files) and
        # picks a file first, then previews that file_path directly.
        pass

    return merged


@app.post("/preview_source")
def preview_source(req: PreviewSourceRequest):
    sample_rows = max(1, min(req.sample_rows or 15, 200))
    cfg = _resolve_preview_config(req)
    connector_type = req.connector_type

    try:
        if connector_type in ("csv", "excel"):
            file_path = cfg.get("file_path")
            # BUGFIX: folder-based pipelines only ever had folder_path set —
            # file_path was always empty, so preview_source used to 400 on
            # every one of them. Fall back to the first matching file in the
            # folder, same extension rule /list_folder_files uses, so the
            # quality/schema builders have something real to preview against.
            if not file_path:
                folder_path = cfg.get("folder_path")
                if folder_path and os.path.isdir(folder_path):
                    ext_filter = (".csv",) if connector_type == "csv" else (".xlsx", ".xls")
                    candidates = sorted(
                        f for f in os.listdir(folder_path)
                        if not f.startswith(".")
                        and os.path.isfile(os.path.join(folder_path, f))
                        and os.path.splitext(f)[1].lower() in ext_filter
                    )
                    if candidates:
                        file_path = os.path.join(folder_path, candidates[0])
            if not file_path:
                raise HTTPException(status_code=400, detail="Select a file to preview.")
            if not os.path.exists(file_path):
                raise HTTPException(status_code=404, detail="File not found")
            df = excel_connector(file_path) if connector_type == "excel" else csv_connector(file_path)

        elif connector_type == "postgres":
            base_query = (cfg.get("pg_query") or "").strip()
            if not base_query:
                raise HTTPException(status_code=400, detail="Provide a table name or SQL query.")
            preview_query = f"SELECT * FROM ({base_query.rstrip(';')}) AS _preview_src LIMIT {sample_rows}"
            df = postgres_connector(
                host=cfg.get("src_pg_host"), database=cfg.get("src_pg_db"),
                user=cfg.get("src_pg_user"), password=cfg.get("src_pg_password"),
                port=cfg.get("src_pg_port"), query=preview_query,
            )

        elif connector_type == "mysql":
            base_query = (cfg.get("my_query") or "").strip()
            if not base_query:
                raise HTTPException(status_code=400, detail="Provide a table name or SQL query.")
            preview_query = f"SELECT * FROM ({base_query.rstrip(';')}) AS _preview_src LIMIT {sample_rows}"
            df = mysql_connector(
                host=cfg.get("src_my_host"), database=cfg.get("src_my_db"),
                user=cfg.get("src_my_user"), password=cfg.get("src_my_password"),
                port=cfg.get("src_my_port"), query=preview_query,
            )

        elif connector_type == "oracle":
            base_query = (cfg.get("ora_query") or "").strip()
            if not base_query:
                raise HTTPException(status_code=400, detail="Provide a table name or SQL query.")
            # Oracle table aliases can't use the AS keyword, and ROWNUM is the
            # portable way to cap rows without requiring 12c+ FETCH FIRST.
            preview_query = f"SELECT * FROM ({base_query.rstrip(';')}) _preview_src WHERE ROWNUM <= {sample_rows}"
            df = oracle_connector(
                host=cfg.get("src_ora_host"), database=cfg.get("src_ora_db"),
                user=cfg.get("src_ora_user"), password=cfg.get("src_ora_password"),
                port=cfg.get("src_ora_port"), query=preview_query,
            )

        elif connector_type == "mongodb":
            collection = cfg.get("mongo_collection")
            if not collection:
                raise HTTPException(status_code=400, detail="Provide a collection name.")
            df = mongodb_connector(
                host=cfg.get("src_mongo_host"), database=cfg.get("src_mongo_db"),
                user=cfg.get("src_mongo_user"), password=cfg.get("src_mongo_password"),
                port=cfg.get("src_mongo_port"), collection=collection,
                query=cfg.get("mongo_query"), connection_string=cfg.get("src_mongo_connection_string"),
                limit=sample_rows,
            )

        elif connector_type == "snowflake":
            base_query = (cfg.get("sf_query") or "").strip()
            if not base_query:
                raise HTTPException(status_code=400, detail="Provide a table name or SQL query.")
            preview_query = f"SELECT * FROM ({base_query.rstrip(';')}) AS _preview_src LIMIT {sample_rows}"
            raw = snowflake_connector(
                account=cfg.get("sf_account"), user=cfg.get("sf_user"), password=cfg.get("sf_password"),
                warehouse=cfg.get("sf_warehouse"), database=cfg.get("sf_database"),
                schema=cfg.get("sf_schema"), query=preview_query, role=cfg.get("sf_role"),
            )
            df = raw if isinstance(raw, pl.DataFrame) else pl.from_pandas(raw)

        elif connector_type == "s3":
            if not cfg.get("s3_bucket") or not cfg.get("s3_key"):
                raise HTTPException(status_code=400, detail="Bucket and key are required.")
            df = s3_connector(
                bucket=cfg.get("s3_bucket"), key=cfg.get("s3_key"),
                file_type=cfg.get("s3_file_type") or "csv",
                access_key=cfg.get("s3_access_key"), secret_key=cfg.get("s3_secret_key"),
            )

        elif connector_type == "google_sheets":
            if not cfg.get("sheet_url"):
                raise HTTPException(status_code=400, detail="Sheet URL is required.")
            raw = google_sheet_connector(cfg.get("sheet_url"), engine="polars")
            df = raw if isinstance(raw, pl.DataFrame) else pl.from_pandas(raw)

        elif connector_type == "api":
            if not cfg.get("api_url"):
                raise HTTPException(status_code=400, detail="API URL is required.")
            api_cfg = cfg.get("api_config") or {}
            raw = api_connector(cfg.get("api_url"), **api_cfg)
            df = raw if isinstance(raw, pl.DataFrame) else pl.from_pandas(raw)

        else:
            raise HTTPException(status_code=400, detail=f"Preview not supported for '{connector_type}'.")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Couldn't preview this source: {e}")

    total_rows = df.height
    sample = df.head(sample_rows)

    columns = []
    for col in df.columns:
        series = df[col]
        null_count = int(series.null_count())
        columns.append({
            "name": col,
            "type": _guess_simple_type(str(series.dtype)),
            "null_pct": round((null_count / total_rows) * 100, 1) if total_rows else 0.0,
        })

    rows = []
    for row in sample.iter_rows(named=True):
        rows.append({k: ("" if v is None else str(v)) for k, v in row.items()})

    return {
        "columns": columns,
        "rows": rows,
        "total_rows": total_rows,
        "sample_row_count": len(rows),
    }


# ── Live table list for the CREATE flow (pipeline doesn't exist yet) ────────
# GET /pipeline/{pipeline_name}/source_tables (above) only works for a
# pipeline that's already been saved, because it reads credentials back out
# of that pipeline's DAG file. Create Pipeline / Multi-Source / Direct
# Ingest need the same "pick a table" dropdown *before* anything is saved,
# so this takes credentials (or a saved connection_id) straight from the
# form instead — reusing the same _resolve_preview_config merge that
# /preview_source uses, so "table name" mode always sees the same source
# preview mode would read from.

@app.post("/list_source_tables")
def list_source_tables_live(req: PreviewSourceRequest):
    cfg = _resolve_preview_config(req)
    connector_type = req.connector_type

    if connector_type == "postgres":
        host, db, user = cfg.get("src_pg_host"), cfg.get("src_pg_db"), cfg.get("src_pg_user")
        if not (host and db and user):
            raise HTTPException(status_code=400, detail="Enter host, database, and user first.")
        try:
            conn = psycopg2.connect(
                host=host, dbname=db, user=user,
                password=cfg.get("src_pg_password"), port=cfg.get("src_pg_port") or "5432",
            )
            cur = conn.cursor()
            cur.execute("""
                SELECT table_name FROM information_schema.tables
                WHERE table_schema NOT IN ('pg_catalog', 'information_schema')
                ORDER BY table_name
            """)
            tables = [r[0] for r in cur.fetchall()]
            cur.close(); conn.close()
        except Exception as e:
            raise HTTPException(status_code=502, detail=f"Couldn't connect to the source database: {e}")
        return {"connector_type": connector_type, "tables": tables}

    if connector_type == "mysql":
        host, db, user = cfg.get("src_my_host"), cfg.get("src_my_db"), cfg.get("src_my_user")
        if not (host and db and user):
            raise HTTPException(status_code=400, detail="Enter host, database, and user first.")
        try:
            import pymysql
            conn = pymysql.connect(
                host=host, database=db, user=user,
                password=cfg.get("src_my_password") or "",
                port=int(cfg.get("src_my_port") or 3306),
            )
            cur = conn.cursor()
            cur.execute("SHOW TABLES")
            tables = [r[0] for r in cur.fetchall()]
            cur.close(); conn.close()
        except Exception as e:
            raise HTTPException(status_code=502, detail=f"Couldn't connect to MySQL: {e}")
        return {"connector_type": connector_type, "tables": tables}

    if connector_type == "oracle":
        host, user = cfg.get("src_ora_host"), cfg.get("src_ora_user")
        db = cfg.get("src_ora_db")
        if not (host and user):
            raise HTTPException(status_code=400, detail="Enter host and user first.")
        try:
            import oracledb
            dsn = oracledb.makedsn(host, int(cfg.get("src_ora_port") or 1521), service_name=db) if db else host
            conn = oracledb.connect(user=user, password=cfg.get("src_ora_password"), dsn=dsn)
            cur = conn.cursor()
            cur.execute("SELECT table_name FROM user_tables ORDER BY table_name")
            tables = [r[0] for r in cur.fetchall()]
            cur.close(); conn.close()
        except Exception as e:
            raise HTTPException(status_code=502, detail=f"Couldn't connect to Oracle: {e}")
        return {"connector_type": connector_type, "tables": tables}

    if connector_type == "snowflake":
        if not (cfg.get("sf_account") and cfg.get("sf_user") and cfg.get("sf_database")):
            raise HTTPException(status_code=400, detail="Enter account, user, and database first.")
        try:
            import snowflake.connector
            conn = snowflake.connector.connect(
                account=cfg["sf_account"], user=cfg["sf_user"], password=cfg.get("sf_password"),
                warehouse=cfg.get("sf_warehouse"), database=cfg.get("sf_database"),
                schema=cfg.get("sf_schema") or "PUBLIC", role=cfg.get("sf_role") or None,
            )
            cur = conn.cursor()
            cur.execute(
                "SELECT table_name FROM information_schema.tables WHERE table_schema = %s ORDER BY table_name",
                (cfg.get("sf_schema") or "PUBLIC",),
            )
            tables = [r[0] for r in cur.fetchall()]
            cur.close(); conn.close()
        except Exception as e:
            raise HTTPException(status_code=502, detail=f"Couldn't connect to Snowflake: {e}")
        return {"connector_type": connector_type, "tables": tables}

    raise HTTPException(status_code=400, detail=f"Table listing isn't supported for '{connector_type}' yet — use custom SQL.")


# ─────────────────────────────────────────────
# DELETE a file from a user folder (optional cleanup)
# ─────────────────────────────────────────────

@app.delete("/upload_folders/{folder_name}/{file_name}")
def delete_uploaded_file(folder_name: str, file_name: str):
    safe_folder = _safe_folder_name(folder_name)
    safe_file   = os.path.basename(file_name)
    file_path   = os.path.join(UPLOAD_BASE_DIR, safe_folder, safe_file)

    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found")

    os.remove(file_path)
    return {"status": "SUCCESS", "message": f"{safe_file} deleted from {safe_folder}"}

# ─────────────────────────────────────────────
# DELETE an entire user folder (and everything inside it)
# ─────────────────────────────────────────────

@app.delete("/upload_folders/{folder_name}")
def delete_upload_folder(folder_name: str):
    """
    Deletes an entire user-created upload folder and all files inside it.
    Use with caution — this is irreversible.
    """
    safe_folder = _safe_folder_name(folder_name)
    folder_path = os.path.join(UPLOAD_BASE_DIR, safe_folder)

    if not os.path.exists(folder_path):
        raise HTTPException(status_code=404, detail=f"Folder '{safe_folder}' not found")

    if not os.path.isdir(folder_path):
        raise HTTPException(status_code=400, detail=f"'{safe_folder}' is not a folder")

    file_count = len([f for f in os.listdir(folder_path) if not f.startswith(".")])

    try:
        shutil.rmtree(folder_path)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete folder '{safe_folder}': {e}")

    return {
        "status": "SUCCESS",
        "message": f"Folder '{safe_folder}' and its {file_count} file(s) deleted.",
    }