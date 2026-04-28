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
from agent.tools.report_tools import (get_report_html, export_pdf,
                                       list_reports)

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

@router.post("/agent/analyze")
def analyze(body: AnalyzeRequest):
    logger.info("POST /agent/analyze → source=%s, pipeline=%s, request='%s'",
                body.source_type, body.pipeline_name, body.request)
    try:
        result = pipeline_graph.invoke({
            "source_type":   body.source_type,
            "pipeline_name": body.pipeline_name,
            "file_path":     body.file_path,
            "sheet_url":     body.sheet_url,
            "table_name":    body.table_name,
            "s3_path":       body.s3_path,
            "api_url":       body.api_url,
            "user_request":  body.request,
            # initialise empty state
            "data": {}, "null_result": {}, "dup_result": {},
            "stats_result": {}, "outlier_result": {}, "corr_result": {},
            "health_result": {}, "quality_result": {}, "charts": {},
            "report": {}, "ai_summary": "", "error": None,
        })
        logger.info("POST /agent/analyze complete → report_id=%s",
                     result.get("report", {}).get("report_id"))
        return result
    except Exception as e:
        logger.error("POST /agent/analyze failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/reports")
def get_reports():
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
