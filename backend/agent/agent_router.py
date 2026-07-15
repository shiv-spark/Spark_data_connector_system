"""
agent_router.py
FastAPI routes that expose the agent and report endpoints.
"""

import traceback
from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse, FileResponse
from pydantic import BaseModel
import os

from agent.logger            import get_logger
from agent.graph.graph       import pipeline_graph
from agent.graph.onthefly    import generate_onthefly_chart
from agent.dashboard_store   import (save_dashboard, get_dashboard,
                                      list_dashboards, compute_data_hash)
from agent.tools.report_tools import (get_report_html, export_pdf, list_reports)
from agent.figma_design       import build_figma_context_from_connection
from fastapi.templating      import Jinja2Templates
from openai                  import OpenAI

_templates = Jinja2Templates(
    directory=os.path.join(os.path.dirname(__file__), "templates")
)
_chat_histories: dict = {}   # { dashboard_id: [ {role, content}, ... ] }

logger = get_logger(__name__)

router = APIRouter(prefix="/agent", tags=["Agent"])

REPORTS_DIR = os.path.join(os.path.dirname(__file__), "..", "agent", "reports")


def _json_safe(obj):
    """Recursively replace NaN / Infinity / numpy scalars with JSON-friendly values
    (None for non-finite floats, native Python types otherwise). FastAPI's default
    JSON encoder rejects NaN/Inf, which crashes /dashboard/{id}/data when CSVs
    contain empty cells."""
    import math
    try:
        import numpy as np  # type: ignore
    except Exception:
        np = None  # numpy is always available with pandas, but stay defensive

    if obj is None or isinstance(obj, (str, bool)):
        return obj
    if isinstance(obj, float):
        return obj if math.isfinite(obj) else None
    if isinstance(obj, int):
        return obj
    if np is not None and isinstance(obj, (np.floating,)):
        f = float(obj)
        return f if math.isfinite(f) else None
    if np is not None and isinstance(obj, (np.integer,)):
        return int(obj)
    if np is not None and isinstance(obj, (np.bool_,)):
        return bool(obj)
    if np is not None and isinstance(obj, np.ndarray):
        return [_json_safe(v) for v in obj.tolist()]
    if isinstance(obj, dict):
        return {str(k): _json_safe(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple, set)):
        return [_json_safe(v) for v in obj]
    return obj


# ─── Request Schema ───────────────────────────────────────────────────────────

from typing import Optional

class AnalyzeRequest(BaseModel):
    source_type:   str          # "csv", "excel", "postgres", "google_sheet", 
    connection_id: Optional[int] = None
    pipeline_name: Optional[str] = None   # only needed for postgres
    file_path:     Optional[str] = None   # for csv / excel
    sheet_url:     Optional[str] = None   # for google_sheet
    table_name:    Optional[str] = None   # for postgres
    s3_path:       Optional[str] = None   # for s3
    api_url:       Optional[str] = None   # for api
    api_headers:   Optional[dict] = None  # optional API auth headers
    sf_account:    Optional[str] = None
    sf_user:       Optional[str] = None
    sf_password:   Optional[str] = None
    sf_warehouse:  Optional[str] = None
    sf_database:   Optional[str] = None
    sf_schema:     Optional[str] = None
    sf_table:      Optional[str] = None
    sf_query:      Optional[str] = None
    sf_role:       Optional[str] = None
    figma_connection_id: Optional[int] = None
    request:       str = "full analysis with report"
    model:         Optional[str] = None  


# ─── Endpoints ────────────────────────────────────────────────────────────────

@router.get("/home", response_class=HTMLResponse)
def homepage():
    """Homepage — shows all session dashboards."""
    dashboards = list_dashboards()
    return HTMLResponse(_templates.get_template("home.html").render({
        "dashboards": dashboards,
    }))
    """List all generated reports."""
    logger.info("GET /reports")
    try:
        reports = list_reports()
        logger.info("Found %d reports", len(reports))
        return reports
    except Exception as e:
        logger.error("GET /reports failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/dashboards")
def dashboards_json():
    """List all AI-generated dashboards for the React app."""
    return {"dashboards": list_dashboards()}


@router.get("/reports/{report_id}", response_class=HTMLResponse)
def get_report(report_id: str):
    """View an HTML report in the browser."""
    logger.info("GET /reports/%s", report_id)
    try:
        html = get_report_html(report_id)
        return HTMLResponse(content=html)
    except FileNotFoundError:
        logger.error("Report not found: %s", report_id)
        raise HTTPException(status_code=404, detail=f"Report {report_id} not found")


@router.get("/reports/{report_id}/pdf")
def download_report_pdf(report_id: str):
    """Download a report as PDF."""
    logger.info("GET /reports/%s/pdf", report_id)
    try:
        pdf_path = export_pdf(report_id)
        logger.info("PDF exported: %s", pdf_path)
        return FileResponse(
            path=pdf_path,
            media_type="application/pdf",
            filename=f"report_{report_id}.pdf"
        )
    except FileNotFoundError:
        logger.error("Report not found for PDF export: %s", report_id)
        raise HTTPException(status_code=404, detail=f"Report {report_id} not found")
    except RuntimeError as e:
        logger.error("PDF export failed for %s: %s", report_id, e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ─── Analyze + create dashboard ──────────────────────────────────────────────
@router.post("/analyze")
def analyze(body: AnalyzeRequest):
    logger.info("POST /analyze → source=%s pipeline=%s", body.source_type, body.pipeline_name)
    try:
        display_name = body.pipeline_name or ""
        if body.file_path:
            display_name = os.path.splitext(os.path.basename(body.file_path))[0]

        # ── Resolve REAL credentials server-side from saved connection ──
        resolved_pg = {}
        resolved_sf = {}
        if body.connection_id:
            from agent.db import get_conn
            with get_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT config, source_type FROM saved_connections WHERE id = %s",
                        (body.connection_id,)
                    )
                    row = cur.fetchone()
            if row:
                cfg, source_type = row
                cfg = cfg if isinstance(cfg, dict) else json.loads(cfg)
                if source_type == "postgres":
                    resolved_pg = {
                        "pg_host":     cfg.get("host"),
                        "pg_port":     cfg.get("port", "5432"),
                        "pg_database": cfg.get("database"),
                        "pg_user":     cfg.get("user"),
                        "pg_password": cfg.get("password"),
                    }
                elif source_type == "snowflake":
                    resolved_sf = {
                        "sf_account":   cfg.get("account"),
                        "sf_user":      cfg.get("user"),
                        "sf_password":  cfg.get("password"),
                        "sf_warehouse": cfg.get("warehouse"),
                        "sf_database":  cfg.get("database"),
                        "sf_schema":    cfg.get("schema", "PUBLIC"),
                        "sf_role":      cfg.get("role"),
                    }
                else:
                    logger.warning("connection_id %s is source_type=%s, not postgres/snowflake",
                                   body.connection_id, source_type)
            else:
                logger.warning("connection_id %s not found", body.connection_id)

        user_request = body.request
        figma_context = None
        if body.figma_connection_id:
            try:
                figma_context = build_figma_context_from_connection(body.figma_connection_id)
                if figma_context:
                    user_request = f"""{body.request}

--- FIGMA DESIGN REFERENCE ---
{figma_context}
--- END FIGMA DESIGN REFERENCE ---

Design instruction:
Use the Figma reference as the visual blueprint for this dashboard. Match the design hierarchy, spacing, card structure, typography, color direction, and layout rhythm where practical while keeping charts readable and data-driven."""
            except Exception as ex:
                logger.warning("Figma design context failed: %s", ex)

        result = pipeline_graph.invoke({
            "source_type":   body.source_type,
            "pipeline_name": body.pipeline_name,
            "file_path":     body.file_path,
            "sheet_url":     body.sheet_url,
            "table_name":    body.table_name,
            "s3_path":       body.s3_path,
            "api_url":       body.api_url,
            "api_headers":   body.api_headers,
            "pg_host":       resolved_pg.get("pg_host"),
            "pg_port":       resolved_pg.get("pg_port"),
            "pg_database":   resolved_pg.get("pg_database"),
            "pg_user":       resolved_pg.get("pg_user"),
            "pg_password":   resolved_pg.get("pg_password"),
            "sf_account":    resolved_sf.get("sf_account")   or body.sf_account,
            "sf_user":       resolved_sf.get("sf_user")      or body.sf_user,
            "sf_password":   resolved_sf.get("sf_password")  or body.sf_password,
            "sf_warehouse":  resolved_sf.get("sf_warehouse") or body.sf_warehouse,
            "sf_database":   resolved_sf.get("sf_database")  or body.sf_database,
            "sf_schema":     resolved_sf.get("sf_schema")    or body.sf_schema,
            "sf_table":      body.sf_table,
            "sf_query":      body.sf_query,
            "sf_role":       resolved_sf.get("sf_role")      or body.sf_role,
            "model":         body.model,
            "user_request":  user_request,
            "data": {}, "null_result": {}, "dup_result": {},
            "stats_result": {}, "outlier_result": {}, "corr_result": {},
            "health_result": {}, "quality_result": {}, "charts": {},
            "chart_meta": [], "report": {}, "ai_summary": "", "error": None,
        })

        import uuid
        dashboard_id = str(uuid.uuid4())[:8]
        kpis = _build_kpis(result)

        save_dashboard(dashboard_id, {
            **result,
            "display_name":  display_name,
            "source_type":   body.source_type,
            "source_config": {
                "connection_id": body.connection_id,     # NEW — save for refresh later
                "file_path":     body.file_path,
                "sheet_url":     body.sheet_url,
                "pipeline_name": body.pipeline_name,
                "table_name":    body.table_name,
                "s3_path":       body.s3_path,
                "api_url":       body.api_url,
                "api_headers":   body.api_headers,
                "figma_connection_id": body.figma_connection_id,
                "figma_context":  figma_context,
                "model":          body.model,
            },
            "kpis":       kpis,
            "chart_meta": result.get("chart_meta", []),
            "data_hash":  compute_data_hash(result.get("data", {}).get("metrics", [])),
        })

        logger.info("Analyze complete → dashboard_id=%s", dashboard_id)
        return {
            "dashboard_id":  dashboard_id,
            "dashboard_url": f"/agent/dashboard/{dashboard_id}",
            "report_url":    result.get("report", {}).get("report_url"),
            "quality_score": result.get("quality_result", {}).get("quality_score"),
            "grade":         result.get("quality_result", {}).get("grade"),
            "error":         result.get("error"),
        }
    except Exception as e:
        logger.error("Analyze failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
# @router.post("/analyze")
# def analyze(body: AnalyzeRequest):
#     logger.info("POST /analyze → source=%s pipeline=%s", body.source_type, body.pipeline_name)
#     try:
#         display_name = body.pipeline_name or ""
#         if body.file_path:
#             display_name = os.path.splitext(os.path.basename(body.file_path))[0]

#         user_request = body.request
#         figma_context = None
#         if body.figma_connection_id:
#             try:
#                 figma_context = build_figma_context_from_connection(body.figma_connection_id)
#                 if figma_context:
#                     user_request = f"""{body.request}

# --- FIGMA DESIGN REFERENCE ---
# {figma_context}
# --- END FIGMA DESIGN REFERENCE ---

# Design instruction:
# Use the Figma reference as the visual blueprint for this dashboard. Match the design hierarchy, spacing, card structure, typography, color direction, and layout rhythm where practical while keeping charts readable and data-driven."""
#             except Exception as ex:
#                 logger.warning("Figma design context failed: %s", ex)

#         result = pipeline_graph.invoke({
#             "source_type":   body.source_type,
#             "pipeline_name": body.pipeline_name,
#             "file_path":     body.file_path,
#             "sheet_url":     body.sheet_url,
#             "table_name":    body.table_name,
#             "s3_path":       body.s3_path,
#             "api_url":       body.api_url,
#             "api_headers":   body.api_headers,
#             "sf_account":    body.sf_account,      
#             "sf_user":       body.sf_user,      
#             "sf_password":   body.sf_password,    
#             "sf_warehouse":  body.sf_warehouse,   
#             "sf_database":   body.sf_database,    
#             "sf_schema":     body.sf_schema,       
#             "sf_table":      body.sf_table,        
#             "sf_query":      body.sf_query,        
#             "sf_role":       body.sf_role,
#             "model":         body.model,
#             "user_request":  user_request,
#             "data": {}, "null_result": {}, "dup_result": {},
#             "stats_result": {}, "outlier_result": {}, "corr_result": {},
#             "health_result": {}, "quality_result": {}, "charts": {},
#             "chart_meta": [], "report": {}, "ai_summary": "", "error": None,
#         })

#         import uuid
#         dashboard_id = str(uuid.uuid4())[:8]
#         kpis = _build_kpis(result)

#         save_dashboard(dashboard_id, {
#             **result,
#             "display_name":  display_name,
#             "source_type":   body.source_type,
#             "source_config": {
#                 "file_path":     body.file_path,
#                 "sheet_url":     body.sheet_url,
#                 "pipeline_name": body.pipeline_name,
#                 "table_name":    body.table_name,
#                 "s3_path":       body.s3_path,
#                 "api_url":       body.api_url,
#                 "api_headers":   body.api_headers,
#                 "sf_account":    body.sf_account,       
#                 "sf_user":       body.sf_user,          
#                 "sf_password":   body.sf_password,      
#                 "sf_warehouse":  body.sf_warehouse,     
#                 "sf_database":   body.sf_database,      
#                 "sf_schema":     body.sf_schema,        
#                 "sf_table":      body.sf_table,         
#                 "sf_query":      body.sf_query,         
#                 "sf_role":       body.sf_role,
#                 "figma_connection_id": body.figma_connection_id,
#                 "figma_context":  figma_context,
#                 "model":          body.model,
#             },
#             "kpis":       kpis,
#             "chart_meta": result.get("chart_meta", []),
#             "data_hash":  compute_data_hash(result.get("data", {}).get("metrics", [])),
#         })

#         logger.info("Analyze complete → dashboard_id=%s", dashboard_id)
#         return {
#             "dashboard_id":  dashboard_id,
#             "dashboard_url": f"/agent/dashboard/{dashboard_id}",
#             "report_url":    result.get("report", {}).get("report_url"),
#             "quality_score": result.get("quality_result", {}).get("quality_score"),
#             "grade":         result.get("quality_result", {}).get("grade"),
#         }
#     except Exception as e:
#         logger.error("Analyze failed: %s", e, exc_info=True)
#         raise HTTPException(status_code=500, detail=str(e))


# ─── Dashboard endpoints ──────────────────────────────────────────────────────

class ChartRequest(BaseModel):
    request: str

class ChatRequest(BaseModel):
    message: str

class ChartApplyRequest(BaseModel):
    slot: Optional[int] = None
    chart: dict

class BoardCommandRequest(BaseModel):
    message: str
    slot: Optional[int] = None

class LayoutItem(BaseModel):
    slot: int
    x: int
    y: int
    w: int
    h: int

class LayoutUpdateRequest(BaseModel):
    layout: list[LayoutItem]


@router.get("/dashboard/{dashboard_id}", response_class=HTMLResponse)
def view_dashboard(dashboard_id: str):
    state = get_dashboard(dashboard_id)
    if not state:
        raise HTTPException(status_code=404, detail="Dashboard not found")
    from fastapi import Request
    return HTMLResponse(_templates.get_template("dashboard.html").render({
        "dashboard_id": dashboard_id,
        "display_name": state.get("display_name", dashboard_id),
        "source_type":  state.get("source_type", "unknown"),
    }))


@router.get("/dashboard/{dashboard_id}/data")
def get_dashboard_data(dashboard_id: str):
    state = get_dashboard(dashboard_id)
    if not state:
        raise HTTPException(status_code=404, detail="Dashboard not found")

    source_type   = state.get("source_type")
    source_config = state.get("source_config", {})
    current_hash  = state.get("data_hash")

    if source_type in ("google_sheet", "api", "postgres"):
        try:
            from agent.tools.data_tools import fetch_data_by_source
            fresh    = fetch_data_by_source(source_type, **source_config)
            new_hash = compute_data_hash(fresh)
            if new_hash != current_hash:
                logger.info("Dashboard %s data changed — re-running analysis", dashboard_id)
                result = pipeline_graph.invoke({
                    "source_type":   source_type,
                    "pipeline_name": source_config.get("pipeline_name"),
                    "file_path":     source_config.get("file_path"),
                    "sheet_url":     source_config.get("sheet_url"),
                    "table_name":    source_config.get("table_name"),
                    "s3_path":       source_config.get("s3_path"),
                    "api_url":       source_config.get("api_url"),
                    "api_headers":   source_config.get("api_headers"),
                    "user_request":  "full analysis",
                    "model":         source_config.get("model"),    
                    "data": {}, "null_result": {}, "dup_result": {},
                    "stats_result": {}, "outlier_result": {}, "corr_result": {},
                    "health_result": {}, "quality_result": {}, "charts": {},
                    "report": {}, "ai_summary": "", "error": None,
                })
                save_dashboard(dashboard_id, {
                    **state, **result,
                    "kpis": _build_kpis(result), "data_hash": new_hash,
                })
                state = get_dashboard(dashboard_id)
        except Exception as ex:
            logger.warning("Refresh failed for %s: %s", dashboard_id, ex)

    return _json_safe({
        "kpis":           state.get("kpis", []),
        "charts":         state.get("charts", {}),
        "chart_meta":     state.get("chart_meta", []),
        "ai_summary":     state.get("ai_summary", ""),
        "quality_result": state.get("quality_result", {}),
        "null_result":    state.get("null_result", {}),
        "dup_result":     state.get("dup_result", {}),
        "outlier_result": state.get("outlier_result", {}),
        "last_updated":   state.get("last_updated"),
        "data_hash":      state.get("data_hash"),
        "raw_data":       state.get("data", {}).get("metrics", [])[:50],  # first 50 rows for table
    })


class DashboardUpdateRequest(BaseModel):
    display_name: str


@router.patch("/dashboard/{dashboard_id}")
def update_dashboard(dashboard_id: str, body: DashboardUpdateRequest):
    state = get_dashboard(dashboard_id)
    if not state:
        raise HTTPException(status_code=404, detail="Dashboard not found")
    
    save_dashboard(dashboard_id, {**state, "display_name": body.display_name})
    return {"success": True, "display_name": body.display_name}


@router.get("/dashboard/{dashboard_id}/pipeline", response_class=HTMLResponse)
def live_pipeline(dashboard_id: str):
    """Live pipeline page — Airflow DAG runs from Postgres."""
    state = get_dashboard(dashboard_id)
    if not state:
        raise HTTPException(status_code=404, detail="Dashboard not found")
    return HTMLResponse(_templates.get_template("pipeline.html").render({
        "dashboard_id": dashboard_id,
        "display_name": state.get("display_name", dashboard_id),
    }))


@router.post("/dashboard/{dashboard_id}/chart")
def onthefly_chart(dashboard_id: str, body: ChartRequest):
    state = get_dashboard(dashboard_id)
    if not state:
        raise HTTPException(status_code=404, detail="Dashboard not found")
    try:
        data = state.get("data", {}).get("metrics", [])
        return generate_onthefly_chart(data, body.request)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


def _next_chart_slot(state: dict) -> int:
    charts = state.get("charts", {}) or {}
    used = []
    for key, value in charts.items():
        if value and key.startswith("chart_"):
            try:
                used.append(int(key.split("_", 1)[1]))
            except Exception:
                pass
    return max(used, default=0) + 1


def _save_chart_to_dashboard(dashboard_id: str, state: dict, chart_payload: dict, slot: Optional[int] = None):
    slot = slot or _next_chart_slot(state)
    charts = dict(state.get("charts", {}) or {})
    chart_meta = list(state.get("chart_meta", []) or [])

    charts[f"chart_{slot}"] = chart_payload.get("chart", "")
    chart_meta = [meta for meta in chart_meta if meta.get("slot") != slot]
    chart_meta.append({
        "slot": slot,
        "title": chart_payload.get("title", f"Chart {slot}"),
        "description": chart_payload.get("description", ""),
        "config": chart_payload.get("config", {}),
        "source": "user_prompt",
    })
    chart_meta.sort(key=lambda item: item.get("slot", 999))

    save_dashboard(dashboard_id, {
        **state,
        "charts": charts,
        "chart_meta": chart_meta,
    })
    return get_dashboard(dashboard_id), slot


@router.post("/dashboard/{dashboard_id}/chart/apply")
def apply_chart_to_dashboard(dashboard_id: str, body: ChartApplyRequest):
    state = get_dashboard(dashboard_id)
    if not state:
        raise HTTPException(status_code=404, detail="Dashboard not found")
    updated, slot = _save_chart_to_dashboard(dashboard_id, state, body.chart, body.slot)
    return {
        "status": "SUCCESS",
        "slot": slot,
        "chart_meta": updated.get("chart_meta", []),
    }


# @router.post("/dashboard/{dashboard_id}/command")
# def dashboard_command(dashboard_id: str, body: BoardCommandRequest):
#     """
#     Free-form dashboard command. Chart prompts add/replace graphs and persist them.
#     Other questions use the dashboard analyst chat.
#     """
#     state = get_dashboard(dashboard_id)
#     if not state:
#         raise HTTPException(status_code=404, detail="Dashboard not found")

#     text = body.message.strip()
#     lower = text.lower()
#     wants_chart = any(word in lower for word in [
#         "chart", "graph", "plot", "visual", "visualize", "trend",
#         "bar", "line", "pie", "scatter", "histogram", "replace", "add"
#     ])

#     if wants_chart:
#         data = state.get("data", {}).get("metrics", [])
#         # chart_payload = generate_onthefly_chart(data, text)
#         chart_payload = generate_onthefly_chart(data, text, model=state.get("model"))
#         if chart_payload.get("error"):
#             return {"status": "FAILED", "reply": chart_payload["error"], "error": chart_payload["error"]}

#         slot = body.slot
#         import re
#         match = re.search(r"(?:replace|update|change)\s+(?:chart|graph)?\s*(\d+)", lower)
#         if match:
#             slot = int(match.group(1))

#         updated, saved_slot = _save_chart_to_dashboard(dashboard_id, state, chart_payload, slot)
#         reply = f"Done. I {'replaced' if slot else 'added'} chart {saved_slot}: {chart_payload.get('title', 'Custom chart')}."
#         return {
#             "status": "SUCCESS",
#             "reply": reply,
#             "action": "chart_update",
#             "slot": saved_slot,
#             "chart": chart_payload,
#             "chart_meta": updated.get("chart_meta", []),
#         }

#     return dashboard_chat(dashboard_id, ChatRequest(message=text))
@router.post("/dashboard/{dashboard_id}/command")
def dashboard_command(dashboard_id: str, body: BoardCommandRequest):
    state = get_dashboard(dashboard_id)
    if not state:
        raise HTTPException(status_code=404, detail="Dashboard not found")

    try:
        text = body.message.strip()
        lower = text.lower()
        wants_chart = any(word in lower for word in [
            "chart", "graph", "plot", "visual", "visualize", "trend",
            "bar", "line", "pie", "scatter", "histogram", "replace", "add"
        ])

        if wants_chart:
            data = state.get("data", {}).get("metrics", [])
            existing_charts = state.get("chart_meta", [])
            chart_payload = generate_onthefly_chart(data, text, model=state.get("model"),existing_charts=existing_charts,)
            if chart_payload.get("error"):
                return {"status": "FAILED", "reply": chart_payload["error"], "error": chart_payload["error"]}

            slot = body.slot
            import re
            match = re.search(r"(?:replace|update|change)\s+(?:chart|graph)?\s*(\d+)", lower)
            if match:
                slot = int(match.group(1))

            updated, saved_slot = _save_chart_to_dashboard(dashboard_id, state, chart_payload, slot)
            reply = f"Done. I {'replaced' if slot else 'added'} chart {saved_slot}: {chart_payload.get('title', 'Custom chart')}."
            return {
                "status": "SUCCESS", "reply": reply, "action": "chart_update",
                "slot": saved_slot, "chart": chart_payload,
                "chart_meta": updated.get("chart_meta", []),
            }

        return dashboard_chat(dashboard_id, ChatRequest(message=text))

    except Exception as e:
        logger.error("dashboard_command failed for %s: %s", dashboard_id, e, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Command failed: {str(e)}")
    

@router.post("/dashboard/{dashboard_id}/chat")
def dashboard_chat(dashboard_id: str, body: ChatRequest):
    """
    Full conversational chatbot with memory.
    Has access to all analysis results — answers any question about the data.
    """
    state = get_dashboard(dashboard_id)
    if not state:
        raise HTTPException(status_code=404, detail="Dashboard not found")

    # build context from analysis results (once, as system prompt)
    null_r    = state.get("null_result",    {})
    dup_r     = state.get("dup_result",     {})
    stats_r   = state.get("stats_result",   {})
    outlier_r = state.get("outlier_result", {})
    corr_r    = state.get("corr_result",    {})
    quality_r = state.get("quality_result", {})
    health_r  = state.get("health_result",  {})
    summary   = state.get("ai_summary",     "")
    name      = state.get("display_name",   "dataset")
    columns   = list((state.get("data", {}).get("metrics") or [{}])[0].keys()) if state.get("data", {}).get("metrics") else []

    system_prompt = f"""You are a data analyst chatbot for the dataset "{name}".
You have full knowledge of the analysis results below. Answer questions clearly and specifically.
If the user asks for a chart or dashboard change, help them directly. The system can create or replace charts from chat.

DATASET INFO:
- Columns: {columns}
- Total rows: {null_r.get('total_rows', 'unknown')}
- Quality Score: {quality_r.get('quality_score')}/100 ({quality_r.get('grade')})

NULL ANALYSIS: {null_r.get('overall_interpretation', '')}
- Critical columns (>20% null): {null_r.get('critical_cols', [])}
- Warning columns (5-20% null): {null_r.get('warning_cols', [])}

DUPLICATES: {dup_r.get('interpretation', '')}

OUTLIERS: {outlier_r.get('overall_interpretation', '')}
- Columns with outliers: {outlier_r.get('cols_with_outliers', [])}

CORRELATIONS: {corr_r.get('overall_interpretation', '')}
- Strong pairs: {corr_r.get('strong_correlations', [])}

STATS: {stats_r.get('interpretation', '')}

PIPELINE HEALTH: {health_r}

FULL SUMMARY: {summary}

Answer concisely. Use bullet points for lists. Be specific with column names and numbers."""

    # get or init conversation history for this dashboard
    if dashboard_id not in _chat_histories:
        _chat_histories[dashboard_id] = []

    history = _chat_histories[dashboard_id]
    history.append({"role": "user", "content": body.message})

    # keep history to last 20 messages to avoid token overflow
    if len(history) > 20:
        history = history[-20:]
        _chat_histories[dashboard_id] = history

    # llm = OpenAI(
    #     base_url = "https://openrouter.ai/api/v1",
    #     api_key  = os.getenv("OPENROUTER_API_KEY"),
    # )
    # MODEL = os.getenv("OPENROUTER_MODEL", "meta-llama/llama-3.3-70b-instruct:free")

    groq_key = os.getenv("GROQ_API_KEY")
    or_key   = os.getenv("OPENROUTER_API_KEY")

    if groq_key:
        llm = OpenAI(base_url="https://api.groq.com/openai/v1", api_key=groq_key)
        MODEL = state.get("model") or os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
    elif or_key:
        llm = OpenAI(base_url="https://openrouter.ai/api/v1", api_key=or_key)
        MODEL = os.getenv("OPENROUTER_MODEL", "meta-llama/llama-3.3-70b-instruct:free")
    else:
        raise HTTPException(
            status_code=503,
            detail="No LLM API key configured. Set GROQ_API_KEY or OPENROUTER_API_KEY in .env and restart the backend."
        )

    response = llm.chat.completions.create(
        model    = MODEL,
        messages = [{"role": "system", "content": system_prompt}] + history,
        max_tokens = 600,
    )

    reply = response.choices[0].message.content
    history.append({"role": "assistant", "content": reply})

    return {
        "reply":   reply,
        "history": history,
    }


@router.delete("/dashboard/{dashboard_id}/chat")
def clear_chat(dashboard_id: str):
    """Clear conversation history for a dashboard."""
    _chat_histories.pop(dashboard_id, None)
    return {"cleared": True}


@router.post("/dashboard/{dashboard_id}/layout")
def save_layout(dashboard_id: str, body: LayoutUpdateRequest):
    """Persist drag-resize layout positions onto chart_meta entries."""
    state = get_dashboard(dashboard_id)
    if not state:
        raise HTTPException(status_code=404, detail="Dashboard not found")

    by_slot = {item.slot: item for item in body.layout}
    chart_meta = list(state.get("chart_meta", []) or [])
    for meta in chart_meta:
        item = by_slot.get(meta.get("slot"))
        if item:
            meta["layout"] = {"x": item.x, "y": item.y, "w": item.w, "h": item.h}

    save_dashboard(dashboard_id, {**state, "chart_meta": chart_meta})
    return {"status": "SUCCESS", "chart_meta": chart_meta}


@router.delete("/dashboard/{dashboard_id}/chart/{slot}")
def delete_chart(dashboard_id: str, slot: int):
    """Delete a chart slot from the dashboard."""
    state = get_dashboard(dashboard_id)
    if not state:
        raise HTTPException(status_code=404, detail="Dashboard not found")

    charts = dict(state.get("charts", {}) or {})
    chart_meta = [m for m in (state.get("chart_meta", []) or []) if m.get("slot") != slot]
    charts.pop(f"chart_{slot}", None)

    save_dashboard(dashboard_id, {**state, "charts": charts, "chart_meta": chart_meta})
    return {"status": "SUCCESS", "deleted_slot": slot, "chart_meta": chart_meta}


@router.get("/dashboard/{dashboard_id}/pipeline-data")
def get_pipeline_data(dashboard_id: str):
    """Returns live Postgres pipeline data for the pipeline page."""
    state = get_dashboard(dashboard_id)
    if not state:
        raise HTTPException(status_code=404, detail="Dashboard not found")
    try:
        from agent.tools.data_tools import (fetch_pipeline_runs, fetch_pipeline_logs,
                                             fetch_pipeline_metrics, fetch_airflow_runs)
        pname = state.get("source_config", {}).get("pipeline_name")
        return {
            "runs":    fetch_pipeline_runs(pname,    limit=50),
            "logs":    fetch_pipeline_logs(limit=100),
            "metrics": fetch_pipeline_metrics(pname, limit=50),
            "airflow": fetch_airflow_runs(pname,     limit=50),
        }
    except Exception as e:
        logger.error("pipeline-data failed: %s", e)
        return {"runs":[],"logs":[],"metrics":[],"airflow":[]}
    return list_dashboards()


# ─── KPI builder ─────────────────────────────────────────────────────────────

def _build_kpis(result: dict) -> list[dict]:
    kpis    = []
    quality = result.get("quality_result", {})
    nulls   = result.get("null_result",    {})
    dups    = result.get("dup_result",     {})
    health  = result.get("health_result",  {})
    metrics = result.get("data", {}).get("metrics", [])

    kpis.append({"label": "Quality Score",  "value": f"{quality.get('quality_score', 0)}/100"})
    kpis.append({"label": "Grade",          "value": quality.get("grade", "N/A")})
    kpis.append({"label": "Total Rows",     "value": f"{nulls.get('total_rows', len(metrics)):,}"})
    kpis.append({"label": "Total Columns",  "value": nulls.get("total_columns", 0)})
    kpis.append({"label": "Critical Nulls", "value": len(nulls.get("critical_cols", []))})
    kpis.append({"label": "Duplicate Rows", "value": f"{dups.get('duplicate_rows', 0):,}"})

    runs_info = health.get("runs", {})
    if runs_info:
        kpis.append({"label": "Pipeline Runs", "value": runs_info.get("total", 0)})
        kpis.append({"label": "Success Rate",  "value": f"{runs_info.get('success_rate', 0)}%"})

    m = health.get("metrics_summary", {})
    if m.get("rows_inserted"):
        kpis.append({"label": "Rows Inserted", "value": f"{int(m['rows_inserted']['total']):,}"})
    if m.get("rows_failed"):
        kpis.append({"label": "Rows Failed",   "value": f"{int(m['rows_failed']['total']):,}"})

    return kpis
