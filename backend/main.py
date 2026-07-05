

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

from fastapi import FastAPI
from agent.agent_router import router as agent_router

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
    # Check and regenerate business context if schema changed
    try:
        # Add path to text-sql module
        text_sql_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "text-sql")
        sys.path.insert(0, text_sql_path)
        from schema_manager import check_schema_changes
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
    "snowflake":     "dynamic_connector_dag",  # ADDED
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


def _sanitize_config(config: dict) -> dict:
    """Remove sensitive information from config before returning to client."""
    safe = dict(config)
    sensitive_keys = {
        "password", "secret", "token", "access_key", "secret_key",
        "private_key", "passphrase", "api_key", "bearer_token",
        "basic_password", "client_secret", "refresh_token"
    }
    for key in list(safe.keys()):
        if any(s in key.lower() for s in sensitive_keys):
            safe[key] = "********"
    return safe


def _test_snowflake(config: dict, test_write: bool = False) -> dict:
    """Test Snowflake connection."""
    try:
        import snowflake.connector
    except ImportError:
        return {"success": False, "message": "snowflake-connector-python not installed", "category": "connectivity", "details": {}}

    required = ["account", "user", "password", "warehouse", "database"]
    missing = [f for f in required if not config.get(f)]
    if missing:
        return {"success": False, "message": f"Missing required fields: {', '.join(missing)}", "category": "connectivity", "details": _sanitize_config(config)}

    conn = None
    try:
        conn_params = {
            "account": config["account"],
            "user": config["user"],
            "password": config["password"],
            "warehouse": config["warehouse"],
            "database": config["database"],
            "schema": config.get("schema", "PUBLIC"),
            "login_timeout": 10,
            "network_timeout": 10,
        }
        if config.get("role"):
            conn_params["role"] = config["role"]

        conn = snowflake.connector.connect(**conn_params)
        cursor = conn.cursor()
        cursor.execute("SELECT CURRENT_VERSION()")
        version = cursor.fetchone()[0]
        
        # Verify database exists
        database = config["database"]
        cursor.execute(f"""SELECT DATABASE_NAME FROM INFORMATION_SCHEMA.DATABASES WHERE DATABASE_NAME = '{database}'""")
        db_result = cursor.fetchone()
        if not db_result:
            conn.close()
            return {"success": False, "message": f"Database '{database}' not found or not accessible", "category": "not_found", "details": _sanitize_config({"database": database})}
        
        # Verify schema exists in the database
        schema = config.get("schema", "PUBLIC")
        cursor.execute(f"""
    SELECT SCHEMA_NAME
    FROM {database}.INFORMATION_SCHEMA.SCHEMATA
    WHERE SCHEMA_NAME = '{schema}'
      AND CATALOG_NAME = '{database}'
""")
        schema_result = cursor.fetchone()
        if not schema_result:
            conn.close()
            return {"success": False, "message": f"Schema '{schema}' not found in database '{database}'", "category": "not_found", "details": _sanitize_config({"database": database, "schema": schema})}
        
        cursor.close()
        conn.close()
        conn = None

        return {"success": True, "message": f"Connected to Snowflake {version}. Database '{database}' and schema '{schema}' are accessible.", "category": "success", "details": _sanitize_config({"version": version, "database": database, "schema": schema})}
    except Exception as e:
        error_msg = str(e).lower()
        if "network" in error_msg or "timeout" in error_msg:
            category = "connectivity"
        elif "authentication" in error_msg or "password" in error_msg or "invalid credentials" in error_msg:
            category = "auth"
        else:
            category = "connectivity"
        return {"success": False, "message": str(e), "category": category, "details": _sanitize_config(config)}
    finally:
        if conn:
            try:
                conn.close()
            except Exception:
                pass


def _test_postgres(config: dict, test_write: bool = False) -> dict:
    """Test PostgreSQL connection."""
    required = ["host", "database", "user", "password"]
    missing = [f for f in required if not config.get(f)]
    if missing:
        return {"success": False, "message": f"Missing required fields: {', '.join(missing)}", "category": "connectivity", "details": _sanitize_config(config)}

    conn = None
    try:
        conn_params = {
            "host": config["host"],
            "port": config.get("port", 5432),
            "database": config["database"],
            "user": config["user"],
            "password": config["password"],
            "connect_timeout": 5,
        }
        if config.get("sslmode"):
            conn_params["sslmode"] = config["sslmode"]

        conn = psycopg2.connect(**conn_params)
        cursor = conn.cursor()
        cursor.execute("SELECT 1")
        cursor.fetchone()
        
        # Verify schema exists if specified
        schema = config.get("schema")
        if schema:
            cursor.execute("SELECT schema_name FROM information_schema.schemata WHERE schema_name = %s", (schema,))
            schema_result = cursor.fetchone()
            if not schema_result:
                conn.close()
                return {"success": False, "message": f"Schema '{schema}' not found in database '{config['database']}'", "category": "not_found", "details": _sanitize_config({"schema": schema, "database": config["database"]})}
        
        cursor.close()
        conn.close()
        conn = None

        msg = f"Connected to PostgreSQL at {config['host']}/{config['database']}"
        if schema:
            msg += f". Schema '{schema}' is accessible."
        return {"success": True, "message": msg, "category": "success", "details": _sanitize_config({"host": config["host"], "database": config["database"], "schema": schema})}
    except Exception as e:
        error_msg = str(e).lower()
        if "could not connect" in error_msg or "connection refused" in error_msg:
            category = "connectivity"
        elif "authentication" in error_msg or "password" in error_msg:
            category = "auth"
        elif "does not exist" in error_msg:
            category = "not_found"
        else:
            category = "connectivity"
        return {"success": False, "message": str(e), "category": category, "details": _sanitize_config(config)}
    finally:
        if conn:
            try:
                conn.close()
            except Exception:
                pass


def _test_s3(config: dict, test_write: bool = False) -> dict:
    """Test S3 connection."""
    try:
        import boto3
        from botocore.exceptions import ClientError
    except ImportError:
        return {"success": False, "message": "boto3 not installed", "category": "connectivity", "details": {}}

    if not config.get("bucket"):
        return {"success": False, "message": "Missing required field: bucket", "category": "connectivity", "details": _sanitize_config(config)}

    try:
        client_kwargs = {
            "service_name": "s3",
            "region_name": config.get("region", "us-east-1"),
        }
        if config.get("access_key") and config.get("secret_key"):
            client_kwargs["aws_access_key_id"] = config["access_key"]
            client_kwargs["aws_secret_access_key"] = config["secret_key"]

        s3 = boto3.client(**client_kwargs)
        bucket = config["bucket"]
        prefix = config.get("prefix", "").rstrip("/")

        s3.head_bucket(Bucket=bucket)
        s3.list_objects_v2(Bucket=bucket, Prefix=prefix + "/" if prefix else "", MaxKeys=1)

        return {"success": True, "message": f"Connected to S3 bucket '{bucket}'. Read/list access confirmed.", "category": "success", "details": _sanitize_config({"bucket": bucket, "region": config.get("region", "us-east-1")})}
    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "")
        if error_code == "404":
            return {"success": False, "message": f"Bucket '{config.get('bucket')}' not found", "category": "not_found", "details": _sanitize_config(config)}
        elif error_code == "403":
            return {"success": False, "message": "Access denied. Check credentials and permissions.", "category": "auth", "details": _sanitize_config(config)}
        return {"success": False, "message": f"AWS error: {error_code}", "category": "permission", "details": _sanitize_config(config)}
    except Exception as e:
        return {"success": False, "message": str(e), "category": "connectivity", "details": _sanitize_config(config)}


def _test_api(config: dict, test_write: bool = False) -> dict:
    """Test API connection."""
    try:
        import httpx
    except ImportError:
        return {"success": False, "message": "httpx not installed", "category": "connectivity", "details": {}}

    if not config.get("base_url"):
        return {"success": False, "message": "Missing required field: base_url", "category": "connectivity", "details": _sanitize_config(config)}
    # test_endpoint is OPTIONAL — when blank, base_url itself is hit directly.
    # (Removed the old mandatory check that always failed the test when
    # someone left test_endpoint blank, which is the common/expected case.)

    auth_type = config.get("auth_type", "none").lower().strip()
    timeout = config.get("timeout", 10)
    method = (config.get("method") or "GET").upper()
    headers = {}
    params = {}
    auth = None

    if auth_type == "bearer":
        token = config.get("bearer_token") or config.get("api_key")
        if token:
            headers["Authorization"] = f"Bearer {token}"
    elif auth_type == "api_key_header":
        if config.get("api_key"):
            headers[config.get("header_name", "x-api-key")] = config["api_key"]
    elif auth_type == "basic":
        if config.get("basic_user") and config.get("basic_password"):
            auth = (config["basic_user"], config["basic_password"])
    elif auth_type == "query_param":
        if config.get("api_key"):
            params[config.get("query_param_name", "api_key")] = config["api_key"]
    

    
    # url = config["base_url"].strip().rstrip("/") + "/" + config["test_endpoint"].strip().lstrip("/")


    base_url = config["base_url"].strip()
    test_endpoint = config["test_endpoint"].strip()

    # If test_endpoint is empty, OR it's literally the same as base_url (which
    # happens when the frontend defaults test_endpoint = base_url for
    # convenience), just hit base_url directly — don't concatenate them,
    # or you get a doubled/invalid URL like ".../search/https://.../search".
    if not test_endpoint or test_endpoint == base_url:
        url = base_url
    elif test_endpoint.startswith("http://") or test_endpoint.startswith("https://"):
        # test_endpoint is itself a full URL (e.g. user pasted a different
        # complete URL) — use it as-is rather than appending to base_url.
        url = test_endpoint
    else:
        url = base_url.rstrip("/") + "/" + test_endpoint.lstrip("/")
    # url = config["base_url"].rstrip("/") + "/" + config["test_endpoint"].lstrip("/")

    try:
        with httpx.Client(timeout=timeout, auth=auth, follow_redirects=True) as client:
            response = client.request(method, url, headers=headers, params=params)

        if response.status_code in (200, 201, 204):
            return {"success": True, "message": f"API connected. Status: {response.status_code}", "category": "success", "details": _sanitize_config({"url": url})}
        elif response.status_code in (301, 302, 303, 307, 308):
            return {"success": True, "message": f"API connected (redirect). Final status: {response.status_code}", "category": "success", "details": _sanitize_config({"url": url})}
        elif response.status_code == 401:
            return {"success": False, "message": "Authentication failed: 401 Unauthorized", "category": "auth", "details": _sanitize_config(config)}
        elif response.status_code == 403:
            return {"success": False, "message": "Authorization failed: 403 Forbidden", "category": "auth", "details": _sanitize_config(config)}
        elif response.status_code >= 500:
            return {"success": False, "message": f"Server error: HTTP {response.status_code}", "category": "server_error", "details": {"status_code": response.status_code}}
        return {"success": False, "message": f"HTTP {response.status_code}", "category": "server_error", "details": {"status_code": response.status_code}}
    except httpx.TimeoutException:
        return {"success": False, "message": f"Request timed out after {timeout}s", "category": "connectivity", "details": _sanitize_config(config)}
    except httpx.ConnectError as e:
        return {"success": False, "message": f"Cannot connect to {url}", "category": "connectivity", "details": _sanitize_config(config)}
    except Exception as e:
        return {"success": False, "message": str(e), "category": "connectivity", "details": _sanitize_config(config)}


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
    - s3
    - api
    - local_folder
    - google_sheet
    - figma_design
    """
    import os
    
    source_type = req.source_type.lower().strip()
    
    tester_map = {
        "snowflake": "testers.snowflake",
        "postgres": "testers.postgres",
        "s3": "testers.s3",
        "api": "testers.api",
    }
    
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
                "details": {"base_path": base_path}
            }
        else:
            return {
                "success": False,
                "message": f"Directory does not exist or is not accessible: {base_path}",
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
    
    if source_type not in ["snowflake", "postgres", "s3", "api"]:
        return {
            "success": False,
            "message": f"Unknown source_type: {source_type}. Valid types: snowflake, postgres, s3, api, local_folder, google_sheet, figma_design",
            "category": "connectivity",
            "details": {}
        }
    
    try:
        if source_type == "snowflake":
            return _test_snowflake(req.config, req.test_write)
        elif source_type == "postgres":
            return _test_postgres(req.config, req.test_write)
        elif source_type == "s3":
            return _test_s3(req.config, req.test_write)
        elif source_type == "api":
            return _test_api(req.config, req.test_write)
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
# VALIDATION
# ─────────────────────────────────────────────

def validate_inputs(option, table_name):
    if option not in ["1", "2", "3"]:
        raise HTTPException(status_code=400, detail="Invalid option. Use 1, 2, or 3")
    if not table_name:
        raise HTTPException(status_code=400, detail="table_name is required")

# ─────────────────────────────────────────────
# CSV
# ─────────────────────────────────────────────

class CSVRequest(BaseModel):
    file_path: str
    option: str
    table_name: str | None = None
    sync_mode:  str        = "full"
    incremental_column: str | None = None

@app.post("/ingest_csv")
def ingest_csv(req: CSVRequest):
    validate_inputs(req.option, req.table_name)
    return run_ingestion(
        csv_connector,
        req.file_path,
        "CSVConnector",
        req.file_path,
        option=req.option,
        table_name=req.table_name,
        sync_mode          = req.sync_mode,
        incremental_column = req.incremental_column,
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

@app.post("/ingest_excel")
def ingest_excel(req: ExcelRequest):
    validate_inputs(req.option, req.table_name)
    return run_ingestion(
        excel_connector,
        req.file_path,
        "ExcelConnector",
        req.file_path,
        req.sheet_name,
        req.all_sheets,
        option=req.option,
        table_name=req.table_name,
        sync_mode          = req.sync_mode,
        incremental_column = req.incremental_column,
    )

# ─────────────────────────────────────────────
# GOOGLE SHEETS
# ─────────────────────────────────────────────

class GoogleSheetRequest(BaseModel):
    sheet_url: str
    option: str
    table_name: str | None = None
    sync_mode:  str        = "full"
    incremental_column: str | None = None

@app.post("/ingest_google_sheet")
def ingest_google_sheet(req: GoogleSheetRequest):
    validate_inputs(req.option, req.table_name)
    return run_ingestion(
        google_sheet_connector,
        req.sheet_url,
        "GoogleSheetsConnector",
        req.sheet_url,
        "pandas",
        option=req.option,
        table_name=req.table_name,
        sync_mode          = req.sync_mode,
        incremental_column = req.incremental_column,
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
        sync_mode          = req.sync_mode,
        incremental_column = req.incremental_column,
    )

# ─────────────────────────────────────────────
# API CONNECTOR
# ─────────────────────────────────────────────

# class APIRequest(BaseModel):
#     url: str
#     option: str
#     table_name: str | None = None
#     sync_mode:  str        = "full"
#     incremental_column: str | None = None

# @app.post("/ingest_api")
# def ingest_api(req: APIRequest):
#     validate_inputs(req.option, req.table_name)
#     return run_ingestion(
#         api_connector,
#         req.url,
#         "APIConnector",
#         req.url,
#         option=req.option,
#         table_name=req.table_name,
#         sync_mode          = req.sync_mode,
#         incremental_column = req.incremental_column,
#     )
class APIRequest(BaseModel):
    url: str
    method: str = "GET"
    option: str
    table_name: str | None = None
    sync_mode: str = "full"
    incremental_column: str | None = None

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
        exclude={"option", "table_name", "sync_mode", "incremental_column"}
    )

    return run_ingestion(
        api_connector,
        req.url,
        "APIConnector",
        **connector_kwargs,          # url, method, auth_type, body, custom_fields, pagination_* 
        option=req.option,
        table_name=req.table_name,
        sync_mode=req.sync_mode,
        incremental_column=req.incremental_column,
    )

# ─────────────────────────────────────────────
# POSTGRES CONNECTOR
# ────────────────────────────────────────────
from connectors.postgres_connector import postgres_connector

class PostgresRequest(BaseModel):
    host: str
    database: str
    user: str
    password: str
    port: str = "5432"
    query: str
    option: str
    table_name: str | None = None
    sync_mode:  str        = "full"
    incremental_column: str | None = None

@app.post("/ingest_postgres")
def ingest_postgres(req: PostgresRequest):
    validate_inputs(req.option, req.table_name)
    source = f"{req.host}/{req.database}"
    return run_ingestion(
        postgres_connector,
        source,
        "PostgresConnector",
        req.host,
        req.database,
        req.user,
        req.password,
        req.port,
        req.query,
        option=req.option,
        table_name=req.table_name,
        sync_mode          = req.sync_mode,
        incremental_column = req.incremental_column,
    )

# ─────────────────────────────────────────────
# S3 CONNECTOR
# ─────────────────────────────────────────────

class S3Request(BaseModel):
    bucket:       str
    key:          str           # e.g. "folder/sales.csv"
    file_type:    str = "csv"   # csv, xlsx, parquet, json
    access_key:   str | None = None
    secret_key:   str | None = None
    option:       str
    table_name:   str | None = None
    sync_mode:    str = "full"
    incremental_column: str | None = None

@app.post("/ingest_s3")
def ingest_s3(req: S3Request):
    validate_inputs(req.option, req.table_name)
    source = f"s3://{req.bucket}/{req.key}"
    return run_ingestion(
        s3_connector,
        source,
        "S3Connector",
        req.bucket,
        req.key,
        req.file_type,
        req.access_key,
        req.secret_key,
        option              = req.option,
        table_name          = req.table_name,
        sync_mode           = req.sync_mode,
        incremental_column  = req.incremental_column,
    )

# ─────────────────────────────────────────────
# SNOWFLAKE CONNECTOR
# ─────────────────────────────────────────────

class SnowflakeRequest(BaseModel):
    account: str
    user: str
    password: str
    warehouse: str
    database: str
    schema: str = "PUBLIC"
    query: str
    option: str
    table_name: str | None = None
    sync_mode: str = "full"
    incremental_column: str | None = None
    role: str | None = None

# @app.post("/ingest_snowflake")
# def ingest_snowflake(req: SnowflakeRequest):
#     validate_inputs(req.option, req.table_name)
#     source = f"snowflake://{req.account}/{req.database}/{req.schema}"
#     return run_ingestion(
#         snowflake_connector,
#         source,
#         "SnowflakeConnector",
#         req.account,
#         req.user,
#         req.password,
#         req.warehouse,
#         req.database,
#         req.schema,
#         req.query,
#         role=req.role,
#         option=req.option,
#         table_name=req.table_name,
#         sync_mode=req.sync_mode,
#         incremental_column=req.incremental_column,
#     )

@app.post("/ingest_snowflake")
def ingest_snowflake(req: SnowflakeRequest):
    validate_inputs(req.option, req.table_name)
    source = f"snowflake://{req.account}/{req.database}/{req.schema}"
    return run_ingestion(
        snowflake_connector,
        source,
        "SnowflakeConnector",
        req.account,
        req.user,
        req.password,
        req.warehouse,
        req.database,
        req.schema,
        req.query,
        req.role,
        option=req.option,
        table_name=req.table_name,
        sync_mode=req.sync_mode,
        incremental_column=req.incremental_column,
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

    # ── Postgres fields ──────────────────
    src_pg_host:     Optional[str] = None
    src_pg_db:       Optional[str] = None
    src_pg_user:     Optional[str] = None
    src_pg_password: Optional[str] = None
    src_pg_port:     Optional[str] = "5432"
    pg_query:        Optional[str] = None
    # ── S3 fields ────────────────────────
    s3_bucket:       Optional[str] = None
    s3_key:          Optional[str] = None
    s3_file_type:    Optional[str] = "csv"
    # ── Snowflake fields ─────────────────
    sf_account:      Optional[str] = None
    sf_user:         Optional[str] = None
    sf_password:     Optional[str] = None
    sf_warehouse:    Optional[str] = None
    sf_database:     Optional[str] = None
    sf_schema:       Optional[str] = "PUBLIC"
    sf_query:        Optional[str] = None
    sf_role:         Optional[str] = None
    # ─── Incremental fields ─────────────────────
    sync_mode:     Optional[str] = "full"   # "full" or "incremental"
    incremental_column:    Optional[str] = None     # required if load_type is "incremental"

CONNECTOR_TYPE_MAP = {
    "csv": "local_folder",
    "excel": "local_folder",
    "google_sheets": "google_sheet",
    "api": "api",
    "postgres": "postgres",
    "s3": "s3",
    "snowflake": "snowflake",
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

    return merged


@app.post("/create_pipeline")
def create_pipeline(req: CreatePipelineRequest):
    if req.api_config is not None:
        try:
            _json.dumps(req.api_config)
        except (TypeError, ValueError):
            raise HTTPException(status_code=400, detail="api_config must be JSON-serializable")

    payload = _resolve_connection_config(req)
    result = create_dag_file(payload)

    if result.get("status") == "FAILED":
        raise HTTPException(status_code=400, detail=result)

    # ✅ Log pipeline creation to DB
    dag_id = result.get("dag_id")
    insert_pipeline_log({
        "dag_id":         dag_id,
        "dag_run_id":     f"created__{dag_id}",   # placeholder — no real run yet
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
    src_pg_host:    Optional[str] = None
    src_pg_db:      Optional[str] = None
    src_pg_user:    Optional[str] = None
    src_pg_password:Optional[str] = None
    src_pg_port:    Optional[str] = "5432"
    pg_query:       Optional[str] = None
    # Snowflake fields
    sf_account:     Optional[str] = None
    sf_user:        Optional[str] = None
    sf_password:    Optional[str] = None
    sf_warehouse:   Optional[str] = None
    sf_database:    Optional[str] = None
    sf_schema:      Optional[str] = "PUBLIC"
    sf_query:       Optional[str] = None
    sf_role:        Optional[str] = None
    # Saved connection
    connection_id:  Optional[int] = None

class MultiSourcePipelineRequest(BaseModel):
    pipeline_name: str
    table_name:    str
    option:        str          = "1"   # for first source. Subsequent sources will always append (option "1") to avoid overwriting.
    schedule:      str          = "*/5 * * * *"
    timezone:      Optional[str] = "Asia/Kolkata"
    sync_mode:     str          = "full"
    incremental_column: Optional[str] = None
    sources:       List[SourceConfig]  # ← multiple sources

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
    elif source.connector_type == "s3":
        merged["s3_bucket"] = config.get("bucket", "")
        merged["s3_key"] = config.get("prefix", "")
        merged["s3_file_type"] = config.get("file_type", "csv")
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

# def create_multi_pipeline(req: MultiSourcePipelineRequest):
#     if not req.sources:
#         raise HTTPException(status_code=400, detail="At least one source required.")

#     for i, src in enumerate(req.sources):
#         if src.api_config is not None:
#             try:
#                 json.dumps(src.api_config)
#             except (TypeError, ValueError):
#                 raise HTTPException(status_code=400, detail=f"Source {i+1}: api_config must be JSON-serializable")

#     from utils.multi_dag_generator import create_multi_dag_file
#     payload = req.model_dump()
#     payload["sources"] = [_resolve_source_connection(src) for src in req.sources]
#     result = create_multi_dag_file(payload)

#     if result.get("status") == "FAILED":
#         raise HTTPException(status_code=400, detail=result)
    return result
# @app.post("/create_multi_pipeline")
# def create_multi_pipeline(req: MultiSourcePipelineRequest):
#     if not req.sources:
#         raise HTTPException(status_code=400, detail="At least one source required.")

#     resolved_sources = []
#     for source in req.sources:
#         resolved = _resolve_source_connection(source)
#         resolved_sources.append(resolved)

#     from utils.multi_dag_generator import create_multi_dag_file
#     payload = req.model_dump()
#     payload["sources"] = resolved_sources
#     result = create_multi_dag_file(payload)

#     if result.get("status") == "FAILED":
#         raise HTTPException(status_code=400, detail=result)

#     return result

# ────────────────────────────────────────────
# Edit existing pipeline
# ────────────────────────────────────────────

from utils.dag_generator import create_dag_file, delete_dag_file, list_dag_files, edit_dag_file

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
    # s3
    s3_bucket:          Optional[str] = None
    s3_key:             Optional[str] = None
    s3_file_type:       Optional[str] = None
    # snowflake
    sf_account:         Optional[str] = None
    sf_user:            Optional[str] = None
    sf_password:        Optional[str] = None
    sf_warehouse:       Optional[str] = None
    sf_database:        Optional[str] = None
    sf_schema:          Optional[str] = None
    sf_query:           Optional[str] = None
    sf_role:            Optional[str] = None

@app.patch("/edit_pipeline/{pipeline_name}")
def edit_pipeline(pipeline_name: str, req: EditPipelineRequest):
    """
    Update variables of an existing DAG file without regenerating the whole DAG.
    Only the fields you pass will be updated — rest remain unchanged.

    Example:
        PATCH /edit_pipeline/sales_data
        { "schedule": "0 */6 * * *", "option": "2" }
    """
    # Only non-None fields pass in edit function 
    updates = {k: v for k, v in req.model_dump().items() if v is not None}

    if not updates:
        raise HTTPException(
            status_code=400,
            detail="At least one field required for update."
        )

    # validate option if provided
    if "option" in updates and updates["option"] not in ("1", "2", "3"):
        raise HTTPException(
            status_code=400,
            detail="option '1' (append), '2' (overwrite), and '3' (create only) are valid."
        )

    # sync_mode validate if provided
    if "sync_mode" in updates and updates["sync_mode"] not in ("full", "incremental"):
        raise HTTPException(
            status_code=400,
            detail="sync_mode 'full' or 'incremental' is required."
        )

    result = edit_dag_file(pipeline_name, updates)

    if result.get("status") == "FAILED":
        raise HTTPException(status_code=404, detail=result)

    # Update DB record if schedule, table_name, or operation (option) changed
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
        """, (
            updates.get("schedule"),
            updates.get("table_name"),
            updates.get("option"),
            dag_id,
        ))
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        print(f"DB update failed (non-critical): {e}")

    return result

# ── DELETE /delete_pipeline/{pipeline_name} ──────────────────────────────────

@app.delete("/delete_pipeline/{pipeline_name}")
def delete_pipeline(pipeline_name: str):
    """
    Delete an existing DAG file.
    Example: DELETE /delete_pipeline/hr_data_csv
    """
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

@app.get("/table/{table_name}")
def get_table_data(
    table_name: str,
    limit:  int            = Query(50,   ge=1, le=1000),
    offset: int            = Query(0,    ge=0),
    sort_by: Optional[str] = Query(None),
    order:   str           = Query("asc", pattern="^(asc|desc)$"),
    filter_col: Optional[str] = Query(None),
    filter_val: Optional[str] = Query(None),
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

        # ── 2. Validate sort_by column (must exist in table) ───────────
        cursor.execute("""
            SELECT column_name FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = %s
        """, (table_name,))
        valid_columns = {row[0] for row in cursor.fetchall()}

        if sort_by and sort_by not in valid_columns:
            raise HTTPException(status_code=400, detail=f"sort_by column '{sort_by}' not found in table.")

        if filter_col and filter_col not in valid_columns:
            raise HTTPException(status_code=400, detail=f"filter_col '{filter_col}' not found in table.")

        # ── 3. Build base query with optional filter ───────────────────
        #    filter_val is passed as a parameter — never interpolated
        where_clause = sql.SQL("")
        count_params = []
        data_params  = []

        if filter_col and filter_val is not None:
            where_clause = sql.SQL("WHERE CAST({col} AS TEXT) ILIKE %s").format(
                col=sql.Identifier(filter_col)
            )
            like_val     = f"%{filter_val}%"
            count_params = [like_val]
            data_params  = [like_val]

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
            "filter": {
                "col": filter_col,
                "val": filter_val,
            },
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
    """
    DAG pause .
    Example: PATCH /pipeline/hr_analytics_testing/pause
    """
    dag_id = pipeline_name if pipeline_name.startswith("pipeline_") else f"pipeline_{pipeline_name}"

    url    = f"{AIRFLOW_BASE}/{dag_id}"

    res  = requests.patch(url, json={"is_paused": True}, auth=AIRFLOW_AUTH)
    data = res.json()

    if res.status_code != 200:
        raise HTTPException(status_code=res.status_code, detail=data)

    return {
        "status":  "PAUSED",
        "dag_id":  dag_id,
        "message": f"Pipeline '{dag_id}' paused."
    }

@app.patch("/pipeline/{pipeline_name}/unpause")
def unpause_pipeline(pipeline_name: str):
    """
    DAG unpause  (resume).
    Example: PATCH /pipeline/hr_analytics_testing/unpause
    """
    dag_id = pipeline_name if pipeline_name.startswith("pipeline_") else f"pipeline_{pipeline_name}"
    url    = f"{AIRFLOW_BASE}/{dag_id}"

    res  = requests.patch(url, json={"is_paused": False}, auth=AIRFLOW_AUTH)
    data = res.json()

    if res.status_code != 200:
        raise HTTPException(status_code=res.status_code, detail=data)

    return {
        "status":  "ACTIVE",
        "dag_id":  dag_id,
        "message": f"Pipeline '{dag_id}' is active ."
    }

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
    
    app.include_router(agent_router)



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

UPLOAD_BASE_DIR = "/app/data/uploads"   # shared with Airflow via ./data host mount
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