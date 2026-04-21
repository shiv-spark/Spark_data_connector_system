import re
import httpx
from pydantic import BaseModel
from typing import Optional, List
import httpx
import os
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
from dotenv import load_dotenv
from datetime import datetime
from connectors.postgres_connector import postgres_connector
from connectors.s3_connector import s3_connector


def _rows_to_dicts(cursor):
    """Convert psycopg2 cursor result to list of dictionaries"""
    columns = [desc[0] for desc in cursor.description]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]

load_dotenv()  # loads .env into environment

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
   {f'Error  : {error}' if status == "failed" else ''}

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
app = FastAPI()



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
    "google_sheets": "dynamic_connector_dag"
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

@app.post("/ingest_excel")
def ingest_excel(req: ExcelRequest):
    validate_inputs(req.option, req.table_name)
    return run_ingestion(
        excel_connector,
        req.file_path,
        "ExcelConnector",
        req.file_path,
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

class APIRequest(BaseModel):
    url: str
    option: str
    table_name: str | None = None
    sync_mode:  str        = "full"
    incremental_column: str | None = None

@app.post("/ingest_api")
def ingest_api(req: APIRequest):
    validate_inputs(req.option, req.table_name)
    return run_ingestion(
        api_connector,
        req.url,
        "APIConnector",
        req.url,
        option=req.option,
        table_name=req.table_name,
        sync_mode          = req.sync_mode,
        incremental_column = req.incremental_column,
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
    bucket:     str
    key:        str           # e.g. "folder/sales.csv"
    file_type:  str = "csv"   # csv, xlsx, parquet, json
    option:     str
    table_name: str | None = None
    sync_mode:  str        = "full"
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
        option     = req.option,
        table_name = req.table_name,
        sync_mode          = req.sync_mode,
        incremental_column = req.incremental_column,
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
    folder_path:     Optional[str] = None
    file_path:       Optional[str] = None
    sheet_url:       Optional[str] = None
    api_url:         Optional[str] = None

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
    # ─── Incremental fields ─────────────────────
    sync_mode:     Optional[str] = "full"   # "full" or "incremental"
    incremental_column:    Optional[str] = None     # required if load_type is "incremental"
 

 
@app.post("/create_pipeline")
def create_pipeline(req: CreatePipelineRequest):
    result = create_dag_file(req.model_dump())
 
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
    connector_type: str          # csv, excel, google_sheets, api, postgres, s3
    file_path:      Optional[str] = None
    folder_path:    Optional[str] = None
    sheet_url:      Optional[str] = None
    api_url:        Optional[str] = None
    s3_bucket:      Optional[str] = None
    s3_key:         Optional[str] = None
    s3_file_type:   Optional[str] = "csv"
    src_pg_host:    Optional[str] = None
    src_pg_db:      Optional[str] = None
    src_pg_user:    Optional[str] = None
    src_pg_password:Optional[str] = None
    src_pg_port:    Optional[str] = "5432"
    pg_query:       Optional[str] = None

class MultiSourcePipelineRequest(BaseModel):
    pipeline_name: str
    table_name:    str
    option:        str          = "1"   # for first source. Subsequent sources will always append (option "1") to avoid overwriting.
    schedule:      str          = "*/5 * * * *"
    sync_mode:     str          = "full"
    incremental_column: Optional[str] = None
    sources:       List[SourceConfig]  # ← multiple sources


@app.post("/create_multi_pipeline")
def create_multi_pipeline(req: MultiSourcePipelineRequest):
    if not req.sources:
        raise HTTPException(status_code=400, detail="At least one source required.")

    from utils.multi_dag_generator import create_multi_dag_file
    result = create_multi_dag_file(req.model_dump())

    if result.get("status") == "FAILED":
        raise HTTPException(status_code=400, detail=result)

    return result

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
    order:   str           = Query("asc", regex="^(asc|desc)$"),
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
 
 
# ─────────────────────────────────────────────
# GET /pipeline/{name}/logs
# Returns latest run's logs
# ─────────────────────────────────────────────
 
@app.get("/pipeline/{pipeline_name}/logs")
def get_pipeline_logs_latest(pipeline_name: str):
    """
    Get logs of the latest run of a pipeline.
    Tries DB first, falls back to filesystem.
 
    Example: GET /pipeline/hr_data_csv/logs
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
            LIMIT 1
        """, (pipeline_id,))
 
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
        fs = _read_log_from_filesystem(pipeline_id)
        if fs["log_content"]:
            return {
                "pipeline":  pipeline_id,
                "source":    "filesystem",
                "dag_run_id": None,
                "status":    None,
                "log_file":  fs["log_file_path"],
                "log":       fs["log_content"],
                "logged_at": None,
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

class ChatMessage(BaseModel):
    role:    str   # "user" ya "assistant"
    content: str


class ChatRequest(BaseModel):
    messages:      List[ChatMessage]
    openrouter_key: str
    model:         str = "mistralai/mistral-7b-instruct"
    pipeline_name: Optional[str] = None   # specific pipeline ke logs chahiye to


# ── DB context builder ────────────────────────────────────────────────────────

def _build_db_context(pipeline_name: Optional[str] = None) -> str:
    """
    Create a context string by fetching relevant data from the database.
    This context is provided to the LLM.
    """
    parts = []
    conn  = get_conn()
    cur   = conn.cursor()

    try:
        # ── 1. pipeline_runs — last 20 ───────────────────────────
        cur.execute("""
            SELECT run_id, connector_name, source, start_time, end_time,
                   status, records_count, error
            FROM pipeline_runs
            ORDER BY start_time DESC
            LIMIT 20
        """)
        rows = cur.fetchall()
        cols = [d[0] for d in cur.description]
        if rows:
            lines = ["=== pipeline_runs (Last 20) ==="]
            for r in rows:
                rd = dict(zip(cols, r))
                lines.append(
                    f"run_id={rd['run_id']} | connector={rd['connector_name']} | "
                    f"status={rd['status']} | rows={rd['records_count']} | "
                    f"error={str(rd['error'] or '')[:100]} | "
                    f"start={rd['start_time']} | end={rd['end_time']}"
                )
            parts.append("\n".join(lines))

        # ── 2. pipeline_metrics — last 30 ────────────────────────
        cur.execute("""
            SELECT pipeline_id, table_name, rows_inserted, rows_skipped,
                   rows_failed, duration_sec, evolved_columns, match_pct,
                   connector_type, option, status, error_message, logged_at
            FROM pipeline_metrics
            ORDER BY logged_at DESC
            LIMIT 30
        """)
        rows = cur.fetchall()
        cols = [d[0] for d in cur.description]
        if rows:
            lines = ["=== pipeline_metrics (Last 30) ==="]
            for r in rows:
                rd = dict(zip(cols, r))
                lines.append(
                    f"pipeline={rd['pipeline_id']} | status={rd['status']} | "
                    f"rows_inserted={rd['rows_inserted']} | "
                    f"duration={rd['duration_sec']}s | "
                    f"match_pct={rd['match_pct']}% | "
                    f"connector={rd['connector_type']} | "
                    f"evolved_cols={rd['evolved_columns']} | "
                    f"error={str(rd['error_message'] or '')[:100]} | "
                    f"time={rd['logged_at']}"
                )
            parts.append("\n".join(lines))

        # ── 3. airflow_pipeline_runs — last 20 ───────────────────
        cur.execute("""
            SELECT dag_id, dag_run_id, pipeline_name, connector_type,
                   operation, table_name, schedule, status,
                   triggered_by, error_message, created_at
            FROM airflow_pipeline_runs
            ORDER BY created_at DESC
            LIMIT 20
        """)
        rows = cur.fetchall()
        cols = [d[0] for d in cur.description]
        if rows:
            lines = ["=== airflow_pipeline_runs (Last 20) ==="]
            for r in rows:
                rd = dict(zip(cols, r))
                lines.append(
                    f"dag={rd['dag_id']} | status={rd['status']} | "
                    f"connector={rd['connector_type']} | "
                    f"schedule={rd['schedule']} | "
                    f"triggered_by={rd['triggered_by']} | "
                    f"error={str(rd['error_message'] or '')[:100]} | "
                    f"time={rd['created_at']}"
                )
            parts.append("\n".join(lines))

        # ── 4. pipeline_logs — recent errors ─────────────────────
        cur.execute("""
            SELECT pl.run_id, pl.log_time, pl.level, pl.message
            FROM pipeline_logs pl
            WHERE pl.level = 'ERROR'
            ORDER BY pl.log_time DESC
            LIMIT 15
        """)
        rows = cur.fetchall()
        cols = [d[0] for d in cur.description]
        if rows:
            lines = ["=== pipeline_logs (Recent ERRORS) ==="]
            for r in rows:
                rd = dict(zip(cols, r))
                lines.append(
                    f"run_id={rd['run_id']} | time={rd['log_time']} | "
                    f"{rd['message'][:150]}"
                )
            parts.append("\n".join(lines))

        # ── 5. pipeline_dag_logs — specific pipeline ya latest ───
        if pipeline_name:
            pid = pipeline_name if pipeline_name.startswith("pipeline_") else f"pipeline_{pipeline_name}"
            cur.execute("""
                SELECT pipeline_id, dag_run_id, task_id, status,
                       log_content, log_file_path, created_at
                FROM pipeline_dag_logs
                WHERE pipeline_id = %s
                ORDER BY created_at DESC
                LIMIT 3
            """, (pid,))
        else:
            cur.execute("""
                SELECT pipeline_id, dag_run_id, task_id, status,
                       log_content, log_file_path, created_at
                FROM pipeline_dag_logs
                ORDER BY created_at DESC
                LIMIT 5
            """)
        rows = cur.fetchall()
        cols = [d[0] for d in cur.description]
        if rows:
            lines = ["=== pipeline_dag_logs (Latest) ==="]
            for r in rows:
                rd = dict(zip(cols, r))
                # Log content truncate karo — too long hota hai
                log_snippet = str(rd['log_content'] or '')[:400]
                lines.append(
                    f"pipeline={rd['pipeline_id']} | "
                    f"run={rd['dag_run_id']} | "
                    f"status={rd['status']} | "
                    f"time={rd['created_at']}\n"
                    f"LOG_SNIPPET: {log_snippet}..."
                )
            parts.append("\n".join(lines))

        # ── 6. Summary stats ──────────────────────────────────────
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
                )                                                     AS success_rate
            FROM pipeline_metrics
            WHERE logged_at >= NOW() - INTERVAL '24 hours'
        """)
        row  = cur.fetchone()
        cols = [d[0] for d in cur.description]
        if row:
            rd = dict(zip(cols, row))
            parts.insert(0, f"""=== SYSTEM SUMMARY (Last 24h) ===
Total Runs   : {rd['total_runs']}
Success      : {rd['success']}
Failed       : {rd['failed']}
Skipped      : {rd['skipped']}
Success Rate : {rd['success_rate']}%
Total Rows   : {rd['total_rows']:,}
Avg Duration : {rd['avg_duration']}s
""")

    except Exception as e:
        parts.append(f"=== DB FETCH ERROR: {e} ===")
    finally:
        cur.close()
        conn.close()

    return "\n\n".join(parts)


SYSTEM_PROMPT = """
        You are the Pipeline Assistant for SparkBrains Universal Data Connector.

        Your role:
        Help users understand, debug, and monitor their data pipelines using the live database context.

        Tone:
        - Conversational, friendly, and clear (like a helpful teammate)
        - Avoid robotic or overly formal responses
        - Keep it concise but natural

        Context:
        You have access to:
        - pipeline_runs: run_id, connector_name, status, records_count, error, start_time, end_time
        - pipeline_logs: level (INFO/ERROR), message, timestamp, run_id
        - pipeline_metrics: rows_inserted, duration_sec, match_pct, evolved_columns, connector_type, status, error_message
        - airflow_pipeline_runs: dag_id, connector_type, schedule, status, triggered_by, error_message
        - pipeline_dag_logs: pipeline_id, log_content, log_file_path, status, created_at

        Guidelines:
        - Always base answers strictly on the DB context — don’t assume missing data
        - If no data is available, say clearly:
        → "I couldn’t find any data for this — try running the pipeline first."

        Response Style:
        - Start with a short, natural explanation (1–2 lines)
        - Then provide structured insights if needed:
        - ✅ Status summary
        - ⚠️ Issues (if any)
        - 💡 Suggested fix (practical and actionable)
        - Use bullet points, not long paragraphs
        - Avoid sounding like logs or raw SQL output

        Error Handling:
        - Clearly explain the root cause in simple terms
        - Suggest a fix like you would to a teammate (practical, not generic)

        Formatting:
        - Use Markdown (bold, bullets, small tables)
        - Format numbers cleanly (e.g., 10,000 rows, 25 sec)

        Length:
        - Keep responses short and useful (100–250 words preferred)

        Goal:
        Make the user feel like they are chatting with a smart engineer, not reading a system report.
        """


# ── Endpoint ──────────────────────────────────────────────────────────────────

@app.post("/chatbot")
async def chatbot(req: ChatRequest):
    """
    Ask questions about your data pipelines and get insights.
    It fetches live context from the database and generates answers using OpenRouter.

    Request:
        messages:       Chat history
        openrouter_key: API key
        model:          OpenRouter model name
        pipeline_name:  Optional — For specific pipeline logs
    """
    # ── DB context fetch karo ─────────────────────────────────────
    try:
        db_context = _build_db_context(req.pipeline_name)
    except Exception as e:
        db_context = f"DB context fetch failed: {e}"

    # ── Messages build  ───────────────────────────────────────
    # IN Last user message inject context  
    messages_for_llm = [{"role": "system", "content": SYSTEM_PROMPT}]

    # History add  (last 8 messages)
    history = req.messages[-8:]
    for i, msg in enumerate(history):
        if i == len(history) - 1 and msg.role == "user":
            # DB context inject in the last user message
            messages_for_llm.append({
                "role": "user",
                "content": f"""User ka sawaal: {msg.content}

--- DATABASE CONTEXT (Live Data from PostgreSQL) ---
{db_context}
--- END CONTEXT ---
Present your answer clearly and concisely based on the live data provided above. 
If the context doesn't have the answer, say "Data not found in context" instead of making assumptions."""
            })
        else:
            messages_for_llm.append({
                "role":    msg.role,
                "content": msg.content,
            })

    # ── OpenRouter call ───────────────────────────────────────────
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {req.openrouter_key}",
                    "Content-Type":  "application/json",
                    "HTTP-Referer":  "http://localhost:8000",
                    "X-Title":       "SparkBrains Pipeline Assistant",
                },
                json={
                    "model":       req.model,
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
                "model":   req.model,
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


# ── Simple context-only endpoint (bina LLM ke) ───────────────────────────────

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