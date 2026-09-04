"""
Reverse ETL API surface.

Mounted in main.py with:
    from reverse_etl.router import router as reverse_etl_router
    app.include_router(reverse_etl_router)

Endpoints
---------
POST   /reverse_etl/sync                          run an ad-hoc sync right now (not saved)
POST   /reverse_etl/pipelines                      create + persist a pipeline, schedule its DAG
GET    /reverse_etl/pipelines                      list saved pipelines
GET    /reverse_etl/pipelines/{name}                get one
PUT    /reverse_etl/pipelines/{name}                update + regenerate DAG
DELETE /reverse_etl/pipelines/{name}                delete pipeline + its DAG file
POST   /reverse_etl/pipelines/{name}/run            trigger one run of a saved pipeline (also what the DAG calls)
GET    /reverse_etl/runs                            recent run history (reuses pipeline_runs)
GET    /reverse_etl/logs/{run_id}                   logs for one run (reuses pipeline_logs)
GET    /reverse_etl/destinations                    which destination types are supported
GET    /reverse_etl/destinations/{type}/fields      introspect destination fields for the mapping UI
"""

import json
from typing import Optional

import psycopg2
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from reverse_etl.db import (
    DB_CONFIG, ensure_reverse_etl_tables, get_conn, get_pipeline,
    resolve_destination_config,
)
from reverse_etl.dag_generator import create_reverse_dag_file, delete_reverse_dag_file
from reverse_etl.sync_runner import run_reverse_sync
from reverse_etl.writers import VALID_DESTINATIONS
from utils import history_store

# Fields that make up a pipeline's editable config — same set PUT accepts,
# and what gets snapshotted/restored. status and last_synced_value are
# operational state, not config, so they're left alone by history/restore.
_CONFIG_FIELDS = [
    "source_table", "source_query", "filter_sql",
    "destination_type", "connection_id", "destination_config", "destination_object",
    "field_mapping", "upsert_key", "write_mode", "batch_size",
    "sync_mode", "incremental_column", "schedule", "timezone",
]

router = APIRouter(prefix="/reverse_etl", tags=["Reverse ETL"])


# ─────────────────────────────────────────────
# Schemas
# ─────────────────────────────────────────────

class ReverseSyncRequest(BaseModel):
    pipeline_name:       str = "adhoc_sync"
    source_table:        Optional[str] = None
    source_query:        Optional[str] = None
    filter_sql:          Optional[str] = None
    destination_type:    str
    destination_object:  str
    connection_id:       Optional[int] = None
    destination_config:  Optional[dict] = None
    field_mapping:       Optional[dict] = None
    upsert_key:          Optional[str] = None
    write_mode:          str = "upsert"          # insert | upsert | update
    batch_size:          int = 200
    sync_mode:           str = "full"             # full | incremental
    incremental_column:  Optional[str] = None


class ReverseEtlPipelineRequest(BaseModel):
    pipeline_name:       str
    source_table:        Optional[str] = None
    source_query:        Optional[str] = None
    filter_sql:          Optional[str] = None
    destination_type:    str
    destination_object:  str
    connection_id:       Optional[int] = None
    destination_config:  Optional[dict] = None
    field_mapping:       Optional[dict] = None
    upsert_key:          Optional[str] = None
    write_mode:          str = "upsert"
    batch_size:          int = 200
    sync_mode:           str = "full"
    incremental_column:  Optional[str] = None
    schedule:            str = "*/15 * * * *"
    timezone:            str = "Asia/Kolkata"


def _row_to_dict(cur, row):
    cols = [d[0] for d in cur.description]
    return dict(zip(cols, row))


def _validate_destination(destination_type: str):
    if destination_type not in VALID_DESTINATIONS:
        raise HTTPException(status_code=400, detail=f"Unknown destination_type '{destination_type}'. Valid: {sorted(VALID_DESTINATIONS)}")


# ─────────────────────────────────────────────
# Ad-hoc sync — run once, don't persist a pipeline
# ─────────────────────────────────────────────

@router.post("/sync")
def sync_now(req: ReverseSyncRequest):
    _validate_destination(req.destination_type)
    if not req.source_table and not req.source_query:
        raise HTTPException(status_code=400, detail="source_table or source_query is required")

    result = run_reverse_sync(
        pipeline_name=req.pipeline_name,
        destination_type=req.destination_type,
        destination_object=req.destination_object,
        source_table=req.source_table,
        source_query=req.source_query,
        filter_sql=req.filter_sql,
        connection_id=req.connection_id,
        destination_config=req.destination_config,
        field_mapping=req.field_mapping,
        upsert_key=req.upsert_key,
        write_mode=req.write_mode,
        batch_size=req.batch_size,
        sync_mode=req.sync_mode,
        incremental_column=req.incremental_column,
    )
    if result.get("status") == "FAILED":
        raise HTTPException(status_code=400, detail=result)
    return result


# ─────────────────────────────────────────────
# Saved / scheduled pipelines
# ─────────────────────────────────────────────

@router.post("/pipelines")
def create_pipeline(req: ReverseEtlPipelineRequest):
    _validate_destination(req.destination_type)
    if not req.source_table and not req.source_query:
        raise HTTPException(status_code=400, detail="source_table or source_query is required")
    if req.sync_mode == "incremental" and not req.incremental_column:
        raise HTTPException(status_code=400, detail="incremental_column is required when sync_mode='incremental'")

    ensure_reverse_etl_tables()
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute("""
            INSERT INTO reverse_etl_pipelines (
                pipeline_name, source_table, source_query, filter_sql,
                destination_type, connection_id, destination_config, destination_object,
                field_mapping, upsert_key, write_mode, batch_size,
                sync_mode, incremental_column, schedule, timezone, status
            ) VALUES (%s,%s,%s,%s, %s,%s,%s::jsonb,%s, %s::jsonb,%s,%s,%s, %s,%s,%s,%s,'created')
            RETURNING id
        """, (
            req.pipeline_name, req.source_table, req.source_query, req.filter_sql,
            req.destination_type, req.connection_id, json.dumps(req.destination_config or {}), req.destination_object,
            json.dumps(req.field_mapping or {}), req.upsert_key, req.write_mode, req.batch_size,
            req.sync_mode, req.incremental_column, req.schedule, req.timezone,
        ))
        conn.commit()
    except psycopg2.errors.UniqueViolation:
        conn.rollback()
        raise HTTPException(status_code=409, detail=f"Pipeline '{req.pipeline_name}' already exists")
    finally:
        cur.close()
        conn.close()

    dag_result = create_reverse_dag_file(req.pipeline_name, req.schedule, req.timezone)
    return {"status": "SUCCESS", "pipeline_name": req.pipeline_name, "dag": dag_result}


@router.get("/pipelines")
def list_pipelines():
    ensure_reverse_etl_tables()
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM reverse_etl_pipelines ORDER BY updated_at DESC")
    rows = [_row_to_dict(cur, r) for r in cur.fetchall()]
    cur.close(); conn.close()
    return {"pipelines": rows}


@router.get("/pipelines/{pipeline_name}")
def get_pipeline_detail(pipeline_name: str):
    pipeline = get_pipeline(pipeline_name)
    if not pipeline:
        raise HTTPException(status_code=404, detail="Pipeline not found")
    return pipeline


@router.put("/pipelines/{pipeline_name}")
def update_pipeline(pipeline_name: str, req: ReverseEtlPipelineRequest):
    _validate_destination(req.destination_type)
    existing = get_pipeline(pipeline_name)
    if not existing:
        raise HTTPException(status_code=404, detail="Pipeline not found")

    # Snapshot the config being replaced, before the UPDATE overwrites it.
    history_store.push_history(
        entity_type="reverse_etl",
        entity_id=pipeline_name,
        config={k: existing.get(k) for k in _CONFIG_FIELDS},
        label="Edited pipeline config",
    )

    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        UPDATE reverse_etl_pipelines SET
            source_table = %s, source_query = %s, filter_sql = %s,
            destination_type = %s, connection_id = %s, destination_config = %s::jsonb, destination_object = %s,
            field_mapping = %s::jsonb, upsert_key = %s, write_mode = %s, batch_size = %s,
            sync_mode = %s, incremental_column = %s, schedule = %s, timezone = %s, updated_at = NOW()
        WHERE pipeline_name = %s
    """, (
        req.source_table, req.source_query, req.filter_sql,
        req.destination_type, req.connection_id, json.dumps(req.destination_config or {}), req.destination_object,
        json.dumps(req.field_mapping or {}), req.upsert_key, req.write_mode, req.batch_size,
        req.sync_mode, req.incremental_column, req.schedule, req.timezone,
        pipeline_name,
    ))
    conn.commit()
    cur.close(); conn.close()

    dag_result = create_reverse_dag_file(pipeline_name, req.schedule, req.timezone)
    return {"status": "SUCCESS", "dag": dag_result}


@router.get("/pipelines/{pipeline_name}/history")
def get_pipeline_history(pipeline_name: str):
    return {"history": history_store.list_history("reverse_etl", pipeline_name)}


@router.post("/pipelines/{pipeline_name}/restore/{version_id}")
def restore_pipeline_version(pipeline_name: str, version_id: int):
    """Restore = UPDATE the row back to the snapshotted config, then
    regenerate the DAG (same as PUT does) since schedule/timezone may have
    changed. The restored version and anything newer than it is then
    dropped from history — no redo, same rule as pipelines/dashboards."""
    existing = get_pipeline(pipeline_name)
    if not existing:
        raise HTTPException(status_code=404, detail="Pipeline not found")

    version = history_store.get_version("reverse_etl", pipeline_name, version_id)
    if not version:
        raise HTTPException(status_code=404, detail="History version not found.")

    cfg = version["config"]

    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        UPDATE reverse_etl_pipelines SET
            source_table = %s, source_query = %s, filter_sql = %s,
            destination_type = %s, connection_id = %s, destination_config = %s::jsonb, destination_object = %s,
            field_mapping = %s::jsonb, upsert_key = %s, write_mode = %s, batch_size = %s,
            sync_mode = %s, incremental_column = %s, schedule = %s, timezone = %s, updated_at = NOW()
        WHERE pipeline_name = %s
    """, (
        cfg.get("source_table"), cfg.get("source_query"), cfg.get("filter_sql"),
        cfg.get("destination_type"), cfg.get("connection_id"),
        json.dumps(cfg.get("destination_config") or {}), cfg.get("destination_object"),
        json.dumps(cfg.get("field_mapping") or {}), cfg.get("upsert_key"),
        cfg.get("write_mode"), cfg.get("batch_size"),
        cfg.get("sync_mode"), cfg.get("incremental_column"),
        cfg.get("schedule"), cfg.get("timezone"),
        pipeline_name,
    ))
    conn.commit()
    cur.close(); conn.close()

    dag_result = create_reverse_dag_file(pipeline_name, cfg.get("schedule"), cfg.get("timezone"))
    history_store.discard_from("reverse_etl", pipeline_name, version_id)
    return {"status": "SUCCESS", "restored_label": version.get("label"), "dag": dag_result}


@router.delete("/pipelines/{pipeline_name}")
def delete_pipeline(pipeline_name: str):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("DELETE FROM reverse_etl_pipelines WHERE pipeline_name = %s RETURNING id", (pipeline_name,))
    deleted = cur.fetchone()
    conn.commit()
    cur.close(); conn.close()
    if not deleted:
        raise HTTPException(status_code=404, detail="Pipeline not found")
    delete_reverse_dag_file(pipeline_name)
    return {"status": "DELETED", "pipeline_name": pipeline_name}


@router.post("/pipelines/{pipeline_name}/run")
def run_pipeline_now(pipeline_name: str):
    """Triggers one run of a saved pipeline. This is the exact endpoint the
    generated Airflow DAG calls on its schedule — manually hitting it is
    equivalent to an Airflow-triggered run."""
    pipeline = get_pipeline(pipeline_name)
    if not pipeline:
        raise HTTPException(status_code=404, detail="Pipeline not found")

    result = run_reverse_sync(
        pipeline_name=pipeline["pipeline_name"],
        destination_type=pipeline["destination_type"],
        destination_object=pipeline["destination_object"],
        source_table=pipeline["source_table"],
        source_query=pipeline["source_query"],
        filter_sql=pipeline["filter_sql"],
        connection_id=pipeline["connection_id"],
        destination_config=pipeline["destination_config"] if isinstance(pipeline["destination_config"], dict) else json.loads(pipeline["destination_config"] or "{}"),
        field_mapping=pipeline["field_mapping"] if isinstance(pipeline["field_mapping"], dict) else json.loads(pipeline["field_mapping"] or "{}"),
        upsert_key=pipeline["upsert_key"],
        write_mode=pipeline["write_mode"],
        batch_size=pipeline["batch_size"],
        sync_mode=pipeline["sync_mode"],
        incremental_column=pipeline["incremental_column"],
        last_synced_value=pipeline["last_synced_value"],
    )
    if result.get("status") == "FAILED":
        raise HTTPException(status_code=400, detail=result)
    return result


# ─────────────────────────────────────────────
# Run history / logs (reuses the existing pipeline_runs / pipeline_logs
# tables — same ones the Logs/Metrics pages already read from)
# ─────────────────────────────────────────────

@router.get("/runs")
def list_runs(limit: int = 50):
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()
    cur.execute("""
        SELECT run_id, connector_name, source, start_time, end_time, status, records_count, error
        FROM pipeline_runs
        WHERE connector_name LIKE 'reverse_%%'
        ORDER BY start_time DESC
        LIMIT %s
    """, (limit,))
    rows = [_row_to_dict(cur, r) for r in cur.fetchall()]
    cur.close(); conn.close()
    return {"runs": rows}


@router.get("/logs/{run_id}")
def get_run_logs(run_id: int):
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()
    cur.execute("""
        SELECT id, run_id, log_time, level, message
        FROM pipeline_logs WHERE run_id = %s ORDER BY log_time ASC
    """, (run_id,))
    rows = [_row_to_dict(cur, r) for r in cur.fetchall()]
    cur.close(); conn.close()
    return {"logs": rows}


# ─────────────────────────────────────────────
# Destination metadata — powers the field-mapping UI
# ─────────────────────────────────────────────

@router.get("/destinations")
def list_destination_types():
    return {"destinations": sorted(VALID_DESTINATIONS)}


class FieldsRequest(BaseModel):
    connection_id: Optional[int] = None
    destination_config: Optional[dict] = None
    destination_object: str


@router.post("/destinations/{destination_type}/fields")
def get_destination_fields(destination_type: str, req: FieldsRequest):
    """Best-effort introspection of destination fields, so the frontend can
    render a source-column -> destination-field mapping dropdown instead of
    asking the user to type field names blind."""
    _validate_destination(destination_type)
    config = resolve_destination_config(req.connection_id, req.destination_config)

    if destination_type == "postgres":
        conn = psycopg2.connect(host=config.get("host"), database=config.get("database"),
                                 user=config.get("user"), password=config.get("password"),
                                 port=config.get("port", "5432"))
        cur = conn.cursor()
        cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name = %s", (req.destination_object,))
        fields = [r[0] for r in cur.fetchall()]
        cur.close(); conn.close()
        return {"fields": fields}

    if destination_type == "mysql":
        import pymysql
        conn = pymysql.connect(host=config.get("host"), db=config.get("database"),
                                user=config.get("user"), password=config.get("password"),
                                port=int(config.get("port", 3306)))
        cur = conn.cursor()
        cur.execute(f"SHOW COLUMNS FROM `{req.destination_object}`")
        fields = [r[0] for r in cur.fetchall()]
        cur.close(); conn.close()
        return {"fields": fields}

    if destination_type == "salesforce":
        import requests
        from reverse_etl.writers.salesforce_writer import _login, API_VERSION
        access_token, instance_url = _login(config)
        resp = requests.get(
            f"{instance_url}/services/data/{API_VERSION}/sobjects/{req.destination_object}/describe",
            headers={"Authorization": f"Bearer {access_token}"}, timeout=30,
        )
        resp.raise_for_status()
        fields = [f["name"] for f in resp.json().get("fields", [])]
        return {"fields": fields}

    if destination_type == "hubspot":
        import requests
        resp = requests.get(
            f"https://api.hubapi.com/crm/v3/properties/{req.destination_object}",
            headers={"Authorization": f"Bearer {config.get('access_token')}"}, timeout=30,
        )
        resp.raise_for_status()
        fields = [p["name"] for p in resp.json().get("results", [])]
        return {"fields": fields}

    if destination_type == "snowflake":
        import snowflake.connector
        conn = snowflake.connector.connect(
            account=config.get("account"), user=config.get("user"), password=config.get("password"),
            warehouse=config.get("warehouse"), database=config.get("database"),
            schema=config.get("schema", "PUBLIC"),
        )
        cur = conn.cursor()
        cur.execute(f'DESCRIBE TABLE "{req.destination_object}"')
        fields = [r[0] for r in cur.fetchall()]
        cur.close(); conn.close()
        return {"fields": fields}

    if destination_type == "oracle":
        import oracledb
        dsn = oracledb.makedsn(config.get("host"), int(config.get("port") or 1521), service_name=config.get("database"))
        conn = oracledb.connect(user=config.get("user"), password=config.get("password"), dsn=dsn)
        cur = conn.cursor()
        cur.execute("SELECT COLUMN_NAME FROM USER_TAB_COLUMNS WHERE TABLE_NAME = :1", [req.destination_object.upper()])
        fields = [r[0] for r in cur.fetchall()]
        cur.close(); conn.close()
        return {"fields": fields}

    if destination_type == "mongodb":
        from pymongo import MongoClient
        client = MongoClient(config.get("connection_string")) if config.get("connection_string") else MongoClient(
            host=config.get("host"), port=int(config.get("port") or 27017),
            username=config.get("user") or None, password=config.get("password") or None,
        )
        db = client[config.get("database")]
        sample = db[req.destination_object].find_one()
        client.close()
        return {"fields": list(sample.keys()) if sample else [], "note": "Inferred from one sample document — Mongo has no fixed schema."}

    if destination_type == "zoho":
        import requests
        access_token = config.get("access_token")
        api_domain = (config.get("api_domain") or "https://www.zohoapis.com").rstrip("/")
        resp = requests.get(
            f"{api_domain}/crm/v3/settings/fields", params={"module": req.destination_object},
            headers={"Authorization": f"Zoho-oauthtoken {access_token}"}, timeout=30,
        )
        resp.raise_for_status()
        fields = [f["api_name"] for f in resp.json().get("fields", [])]
        return {"fields": fields}

    # webhook / google_sheets / s3 have no fixed schema to introspect
    return {"fields": [], "note": f"{destination_type} destinations don't have introspectable fields — map manually."}
