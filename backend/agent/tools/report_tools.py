"""
report_tools.py
Assembles analysis + charts into an HTML report using Jinja2.
Optionally exports to PDF using weasyprint.
"""

import os
import uuid
from datetime import datetime
from jinja2 import Environment, FileSystemLoader

from agent.logger import get_logger

logger = get_logger(__name__)


TEMPLATE_DIR = os.path.join(os.path.dirname(__file__), "..", "templates")
REPORTS_DIR  = os.path.join(os.path.dirname(__file__), "..", "reports")
os.makedirs(REPORTS_DIR, exist_ok=True)


def build_html_report(
    pipeline_name:  str,
    user_request:   str,
    ai_summary:     str,
    quality_result: dict,
    null_analysis:  dict,
    dup_analysis:   dict,
    stats_result:   dict,
    outlier_result: dict,
    runs:           list[dict],
    metrics:        list[dict],
    charts:         dict,
) -> dict:
    """
    Renders the Jinja2 HTML report and saves it to disk.
    Returns the report_id and file path.
    """
    logger.info("Building HTML report for pipeline '%s' …", pipeline_name)
# clean the name before passing to template
    display_name = os.path.splitext(os.path.basename(pipeline_name))[0]


    # ── KPIs from runs + metrics ──
    total_runs = len(runs)
    success_runs = sum(1 for r in runs if r.get("status") == "success")
    success_rate = round(success_runs / total_runs * 100, 1) if total_runs else 0

    rows_inserted = sum(
        int(m.get("rows_inserted") or 0) for m in metrics
    )
    rows_failed = sum(
        int(m.get("rows_failed") or 0) for m in metrics
    )

    kpis = {
        "total_runs":         total_runs,
        "success_rate":       success_rate,
        "total_rows_inserted": rows_inserted,
        "total_rows_failed":   rows_failed,
    }
    logger.debug("KPIs: %s", kpis)

    try:
        env      = Environment(loader=FileSystemLoader(TEMPLATE_DIR))
        template = env.get_template("report.html")

        html = template.render(
            pipeline_name  = display_name,
            user_request   = user_request,
            generated_at   = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"),
            ai_summary     = ai_summary,
            quality_score  = quality_result.get("quality_score", 0),
            grade          = quality_result.get("grade", "Unknown"),
            null_analysis  = null_analysis,
            dup_analysis   = dup_analysis,
            stats          = stats_result.get("stats", {}),
            outlier_result = outlier_result,
            recent_runs    = runs,
            kpis           = kpis,
            charts         = charts,
        )

        report_id   = str(uuid.uuid4())[:8]
        report_path = os.path.join(REPORTS_DIR, f"{report_id}.html")
        with open(report_path, "w", encoding="utf-8") as f:
            f.write(html)

        logger.info("HTML report saved → id=%s, path=%s", report_id, report_path)

        return {
            "report_id":   report_id,
            "report_path": report_path,
            "report_url":  f"/agent/reports/{report_id}",
            "pdf_url":     f"/agent/reports/{report_id}/pdf",
        }
    except Exception as e:
        logger.error("Failed to build HTML report: %s", e, exc_info=True)
        raise


def export_pdf(report_id: str) -> str:
    """Convert a saved HTML report to PDF using weasyprint."""
    logger.info("Exporting PDF for report %s …", report_id)
    try:
        from weasyprint import HTML

        html_path = os.path.join(REPORTS_DIR, f"{report_id}.html")
        pdf_path  = os.path.join(REPORTS_DIR, f"{report_id}.pdf")

        if not os.path.exists(html_path):
            logger.error("HTML report not found: %s", html_path)
            raise FileNotFoundError(f"Report {report_id} not found")

        HTML(filename=html_path).write_pdf(pdf_path)
        logger.info("PDF exported → %s", pdf_path)
        return pdf_path

    except ImportError:
        logger.error("weasyprint not installed — cannot export PDF")
        raise RuntimeError(
            "weasyprint not installed. Run: pip install weasyprint"
        )


def get_report_html(report_id: str) -> str:
    """Read and return HTML report content."""
    logger.info("Reading report %s …", report_id)
    path = os.path.join(REPORTS_DIR, f"{report_id}.html")
    if not os.path.exists(path):
        logger.error("Report not found: %s", path)
        raise FileNotFoundError(f"Report {report_id} not found")
    with open(path, encoding="utf-8") as f:
        return f.read()


def list_reports() -> list[dict]:
    """List all generated reports."""
    logger.info("Listing reports from %s", REPORTS_DIR)
    reports = []
    for fname in os.listdir(REPORTS_DIR):
        if fname.endswith(".html"):
            rid  = fname.replace(".html", "")
            path = os.path.join(REPORTS_DIR, fname)
            reports.append({
                "report_id":   rid,
                "report_url":  f"/agent/reports/{rid}",
                "pdf_url":     f"/agent/reports/{rid}/pdf",
                "created_at":  datetime.utcfromtimestamp(
                    os.path.getctime(path)
                ).strftime("%Y-%m-%d %H:%M UTC"),
            })
    logger.info("Found %d reports", len(reports))
    return sorted(reports, key=lambda r: r["created_at"], reverse=True)
