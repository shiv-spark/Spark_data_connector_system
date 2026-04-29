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
from fastapi.templating      import Jinja2Templates
from openai                  import OpenAI

_templates = Jinja2Templates(
    directory=os.path.join(os.path.dirname(__file__), "templates")
)
_chat_histories: dict = {}   # { dashboard_id: [ {role, content}, ... ] }

logger = get_logger(__name__)

router = APIRouter(prefix="/agent", tags=["Agent"])

REPORTS_DIR = os.path.join(os.path.dirname(__file__), "..", "agent", "reports")


# ─── Request Schema ───────────────────────────────────────────────────────────

class AnalyzeRequest(BaseModel):
    source_type:   str          # "csv", "excel", "postgres", "google_sheet", 
                                # "s3", "api", "google_sheets_multi"
    pipeline_name: str = None   # only needed for postgres
    file_path:     str = None   # for csv / excel
    sheet_url:     str = None   # for google_sheet
    table_name:    str = None   # for postgres
    s3_path:       str = None   # for s3
    api_url:       str = None   # for api
    request:       str = "full analysis with report"


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

        result = pipeline_graph.invoke({
            "source_type":   body.source_type,
            "pipeline_name": body.pipeline_name,
            "file_path":     body.file_path,
            "sheet_url":     body.sheet_url,
            "table_name":    body.table_name,
            "s3_path":       body.s3_path,
            "api_url":       body.api_url,
            "user_request":  body.request,
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
                "file_path":     body.file_path,
                "sheet_url":     body.sheet_url,
                "pipeline_name": body.pipeline_name,
                "api_url":       body.api_url,
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
        }
    except Exception as e:
        logger.error("Analyze failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ─── Dashboard endpoints ──────────────────────────────────────────────────────

class ChartRequest(BaseModel):
    request: str

class ChatRequest(BaseModel):
    message: str


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
                    "api_url":       source_config.get("api_url"),
                    "user_request":  "full analysis",
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

    return {
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
    }


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
If the user asks for a chart, tell them to use the "Ask for a Chart" box above instead.

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

    llm = OpenAI(
        base_url = "https://openrouter.ai/api/v1",
        api_key  = os.getenv("OPENROUTER_API_KEY"),
    )
    MODEL = os.getenv("OPENROUTER_MODEL", "meta-llama/llama-3.3-70b-instruct:free")

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
