"""
chart_tools.py
Generates Plotly charts from analysis results.
Returns Plotly HTML div strings — embeddable directly in HTML reports.
No kaleido dependency needed.
"""

import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots

from agent.logger import get_logger

logger = get_logger(__name__)


def _fig_to_html(fig) -> str:
    """Convert a Plotly figure to an embeddable HTML div string."""
    return fig.to_html(full_html=False, include_plotlyjs=False)


# ─── 1. Null/Missing Bar Chart ────────────────────────────────────────────────

def generate_null_bar_chart(null_result: dict) -> str:
    """Bar chart of null % per column. Red = critical, yellow = warning."""
    logger.info("Generating null bar chart …")
    null_pct = null_result.get("null_pct", {})
    if not null_pct:
        logger.info("No null data — skipping null bar chart")
        return ""

    cols   = list(null_pct.keys())
    values = list(null_pct.values())
    colors = ["#ef4444" if v > 20 else "#f59e0b" if v > 5 else "#22c55e"
              for v in values]

    try:
        fig = go.Figure(go.Bar(
            x=cols, y=values,
            marker_color=colors,
            text=[f"{v}%" for v in values],
            textposition="outside"
        ))
        fig.update_layout(
            title="Null / Missing Values per Column (%)",
            xaxis_title="Column", yaxis_title="Null %",
            plot_bgcolor="#0f172a", paper_bgcolor="#0f172a",
            font=dict(color="#e2e8f0"),
            yaxis=dict(range=[0, 110]),
        )
        result = _fig_to_html(fig)
        logger.info("Null bar chart generated (%d columns)", len(cols))
        return result
    except Exception as e:
        logger.error("Failed to generate null bar chart: %s", e, exc_info=True)
        return ""


# ─── 2. Duplicate Pie Chart ───────────────────────────────────────────────────

def generate_duplicate_pie(dup_result: dict) -> str:
    """Pie chart showing duplicate vs unique rows."""
    logger.info("Generating duplicate pie chart …")
    total   = dup_result.get("total_rows", 0)
    dups    = dup_result.get("duplicate_rows", 0)
    unique  = total - dups

    try:
        fig = go.Figure(go.Pie(
            labels=["Unique Rows", "Duplicate Rows"],
            values=[unique, dups],
            marker_colors=["#22c55e", "#ef4444"],
            hole=0.4,
        ))
        fig.update_layout(
            title="Duplicate Row Distribution",
            plot_bgcolor="#0f172a", paper_bgcolor="#0f172a",
            font=dict(color="#e2e8f0"),
        )
        result = _fig_to_html(fig)
        logger.info("Duplicate pie chart generated (unique=%d, dups=%d)", unique, dups)
        return result
    except Exception as e:
        logger.error("Failed to generate duplicate pie chart: %s", e, exc_info=True)
        return ""


# ─── 3. Stats Bar Chart ───────────────────────────────────────────────────────

def generate_stats_chart(stats_result: dict) -> str:
    """Grouped bar: mean, median, std per numeric column."""
    logger.info("Generating stats chart …")
    stats = stats_result.get("stats", {})
    if not stats:
        logger.info("No stats data — skipping stats chart")
        return ""

    cols    = list(stats.keys())
    means   = [stats[c]["mean"]   for c in cols]
    medians = [stats[c]["median"] for c in cols]
    stds    = [stats[c]["std"]    for c in cols]

    try:
        fig = go.Figure()
        fig.add_trace(go.Bar(name="Mean",   x=cols, y=means,   marker_color="#3b82f6"))
        fig.add_trace(go.Bar(name="Median", x=cols, y=medians, marker_color="#8b5cf6"))
        fig.add_trace(go.Bar(name="Std Dev",x=cols, y=stds,    marker_color="#f59e0b"))

        fig.update_layout(
            title="Descriptive Statistics per Column",
            barmode="group",
            plot_bgcolor="#0f172a", paper_bgcolor="#0f172a",
            font=dict(color="#e2e8f0"),
        )
        result = _fig_to_html(fig)
        logger.info("Stats chart generated (%d columns)", len(cols))
        return result
    except Exception as e:
        logger.error("Failed to generate stats chart: %s", e, exc_info=True)
        return ""


# ─── 4. Outlier Box Plots ─────────────────────────────────────────────────────

def generate_outlier_boxplot(data: list[dict], columns: list[str] = None) -> str:
    """Box plot for numeric columns to visualise outlier spread."""
    logger.info("Generating outlier boxplot …")
    df = pd.DataFrame(data)
    if df.empty:
        logger.info("No data — skipping outlier boxplot")
        return ""

    numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
    if columns:
        numeric_cols = [c for c in columns if c in numeric_cols]
    if not numeric_cols:
        logger.info("No numeric columns — skipping outlier boxplot")
        return ""

    try:
        fig = go.Figure()
        for col in numeric_cols[:8]:   # max 8 columns
            fig.add_trace(go.Box(y=df[col].dropna(), name=col, boxpoints="outliers"))

        fig.update_layout(
            title="Outlier Distribution (Box Plot)",
            plot_bgcolor="#0f172a", paper_bgcolor="#0f172a",
            font=dict(color="#e2e8f0"),
        )
        result = _fig_to_html(fig)
        logger.info("Outlier boxplot generated (%d columns)", min(len(numeric_cols), 8))
        return result
    except Exception as e:
        logger.error("Failed to generate outlier boxplot: %s", e, exc_info=True)
        return ""


# ─── 5. Correlation Heatmap ───────────────────────────────────────────────────

def generate_correlation_heatmap(corr_result: dict) -> str:
    """Heatmap of the correlation matrix."""
    logger.info("Generating correlation heatmap …")
    matrix = corr_result.get("correlation_matrix", {})
    if not matrix:
        logger.info("No correlation data — skipping heatmap")
        return ""

    try:
        df   = pd.DataFrame(matrix)
        cols = df.columns.tolist()

        fig = go.Figure(go.Heatmap(
            z=df.values, x=cols, y=cols,
            colorscale="RdBu", zmid=0,
            text=df.round(2).values,
            texttemplate="%{text}",
        ))
        fig.update_layout(
            title="Correlation Matrix",
            plot_bgcolor="#0f172a", paper_bgcolor="#0f172a",
            font=dict(color="#e2e8f0"),
        )
        result = _fig_to_html(fig)
        logger.info("Correlation heatmap generated (%dx%d)", len(cols), len(cols))
        return result
    except Exception as e:
        logger.error("Failed to generate correlation heatmap: %s", e, exc_info=True)
        return ""


# ─── 6. Pipeline Run Status Timeline ─────────────────────────────────────────

def generate_run_status_chart(runs: list[dict]) -> str:
    """Bar chart of pipeline run statuses over time."""
    logger.info("Generating run status chart …")
    if not runs:
        logger.info("No run data — skipping run status chart")
        return ""

    df = pd.DataFrame(runs)
    if "status" not in df.columns:
        logger.info("No 'status' column — skipping run status chart")
        return ""

    try:
        status_counts = df["status"].value_counts().reset_index()
        status_counts.columns = ["status", "count"]

        color_map = {"success": "#22c55e", "failed": "#ef4444",
                     "running": "#3b82f6", "skipped": "#f59e0b"}
        colors = [color_map.get(s, "#94a3b8") for s in status_counts["status"]]

        fig = go.Figure(go.Bar(
            x=status_counts["status"], y=status_counts["count"],
            marker_color=colors,
            text=status_counts["count"], textposition="outside",
        ))
        fig.update_layout(
            title="Pipeline Run Status Breakdown",
            xaxis_title="Status", yaxis_title="Count",
            plot_bgcolor="#0f172a", paper_bgcolor="#0f172a",
            font=dict(color="#e2e8f0"),
        )
        result = _fig_to_html(fig)
        logger.info("Run status chart generated")
        return result
    except Exception as e:
        logger.error("Failed to generate run status chart: %s", e, exc_info=True)
        return ""


# ─── 7. Rows Inserted / Skipped / Failed Trend ───────────────────────────────

def generate_metrics_trend_chart(metrics: list[dict]) -> str:
    """Line chart of rows_inserted, rows_skipped, rows_failed over time."""
    logger.info("Generating metrics trend chart …")
    if not metrics:
        logger.info("No metrics data — skipping trend chart")
        return ""

    df = pd.DataFrame(metrics)
    if "logged_at" not in df.columns:
        logger.info("No 'logged_at' column — skipping trend chart")
        return ""

    try:
        df["logged_at"] = pd.to_datetime(df["logged_at"], errors="coerce")
        df = df.sort_values("logged_at")

        fig = go.Figure()
        for col, color in [("rows_inserted", "#22c55e"),
                           ("rows_skipped",  "#f59e0b"),
                           ("rows_failed",   "#ef4444")]:
            if col in df.columns:
                fig.add_trace(go.Scatter(
                    x=df["logged_at"], y=pd.to_numeric(df[col], errors="coerce"),
                    name=col.replace("_", " ").title(),
                    line=dict(color=color), mode="lines+markers"
                ))

        fig.update_layout(
            title="Row Processing Trend Over Time",
            xaxis_title="Time", yaxis_title="Row Count",
            plot_bgcolor="#0f172a", paper_bgcolor="#0f172a",
            font=dict(color="#e2e8f0"),
        )
        result = _fig_to_html(fig)
        logger.info("Metrics trend chart generated")
        return result
    except Exception as e:
        logger.error("Failed to generate metrics trend chart: %s", e, exc_info=True)
        return ""


# ─── 8. Data Quality Score Gauge ─────────────────────────────────────────────

def generate_quality_gauge(score: float, grade: str) -> str:
    """Gauge chart for the data quality score."""
    logger.info("Generating quality gauge → score=%.1f, grade=%s", score, grade)
    color = "#22c55e" if score >= 80 else "#f59e0b" if score >= 60 else "#ef4444"

    try:
        fig = go.Figure(go.Indicator(
            mode="gauge+number",
            value=score,
            title={"text": f"Data Quality Score — {grade}", "font": {"color": "#e2e8f0"}},
            gauge={
                "axis":       {"range": [0, 100], "tickcolor": "#e2e8f0"},
                "bar":        {"color": color},
                "bgcolor":    "#1e293b",
                "steps": [
                    {"range": [0,  40],  "color": "#450a0a"},
                    {"range": [40, 60],  "color": "#431407"},
                    {"range": [60, 80],  "color": "#422006"},
                    {"range": [80, 100], "color": "#052e16"},
                ],
                "threshold": {"line": {"color": "white", "width": 4}, "value": score},
            },
            number={"suffix": "/100", "font": {"color": "#e2e8f0"}},
        ))
        fig.update_layout(
            paper_bgcolor="#0f172a",
            font=dict(color="#e2e8f0"),
            height=350,
        )
        result = _fig_to_html(fig)
        logger.info("Quality gauge generated")
        return result
    except Exception as e:
        logger.error("Failed to generate quality gauge: %s", e, exc_info=True)
        return ""
