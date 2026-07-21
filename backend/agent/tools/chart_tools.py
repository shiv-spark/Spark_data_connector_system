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


_FONT_FAMILY = "Inter, ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, sans-serif"
_TEXT       = "#0f172a"   # slate-900
_MUTED      = "#475569"   # slate-600
_MUTED_2    = "#64748b"   # slate-500
_GRID       = "rgba(15,23,42,0.06)"
_AXIS_LINE  = "rgba(15,23,42,0.10)"

# Emerald/teal/cyan brand palette — matches the frontend (index.css).
PALETTE = ["#10b981", "#0891b2", "#14b8a6", "#059669", "#22c55e",
           "#06b6d4", "#84cc16", "#0ea5e9"]


def _apply_theme(fig, *, title: str | None = None, height: int | None = None):
    """Apply a consistent dark-glass theme that blends into the dashboard cards."""
    fig.update_layout(
        title=dict(
            text=title,
            font=dict(family=_FONT_FAMILY, size=14, color=_TEXT),
            x=0.02, xanchor="left", y=0.96, yanchor="top",
        ) if title else None,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family=_FONT_FAMILY, color=_TEXT, size=12),
        margin=dict(l=48, r=24, t=46 if title else 24, b=44),
        colorway=PALETTE,
        hoverlabel=dict(
            bgcolor="#ffffff",
            bordercolor="rgba(16,185,129,0.35)",
            font=dict(family=_FONT_FAMILY, color=_TEXT, size=12),
        ),
        legend=dict(
            font=dict(color=_MUTED, size=11),
            bgcolor="rgba(0,0,0,0)",
            bordercolor="rgba(0,0,0,0)",
            orientation="h", y=-0.18, x=0,
        ),
        height=height,
    )
    # fig.update_xaxes(
    #     showgrid=False,
    #     zeroline=False,
    #     linecolor=_AXIS_LINE,
    #     tickfont=dict(color=_MUTED, size=11),
    #     title_font=dict(color=_MUTED, size=11),
    # )
    fig.update_xaxes(
        showgrid=False,
        zeroline=False,
        linecolor=_AXIS_LINE,
        tickfont=dict(color=_MUTED, size=11),
        title_font=dict(color=_MUTED, size=11),
        tickangle=-30,
        automargin=True,
        nticks=15,
    )
    fig.update_yaxes(
        showgrid=True, gridcolor=_GRID,
        zeroline=False,
        linecolor=_AXIS_LINE,
        tickfont=dict(color=_MUTED, size=11),
        title_font=dict(color=_MUTED, size=11),
    )
    return fig


def _fig_to_html(fig) -> str:
    """Convert a Plotly figure to an embeddable, responsive HTML div string."""
    return fig.to_html(
        full_html=False,
        include_plotlyjs=False,
        config={"displayModeBar": False, "responsive": True},
        default_height="320px",
    )


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
    colors = ["#ef4444" if v > 20 else "#f59e0b" if v > 5 else "#10b981"
              for v in values]

    try:
        fig = go.Figure(go.Bar(
            x=cols, y=values,
            marker=dict(color=colors, line=dict(width=0)),
            text=[f"{v}%" for v in values],
            textposition="outside",
            textfont=dict(color=_MUTED, size=11),
            hovertemplate="<b>%{x}</b><br>Null: %{y}%<extra></extra>",
        ))
        _apply_theme(fig, title="Null / Missing Values per Column (%)")
        fig.update_xaxes(title_text="Column")
        fig.update_yaxes(title_text="Null %", range=[0, 110])
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
            marker=dict(colors=["#10b981", "#ef4444"], line=dict(color="#ffffff", width=2)),
            hole=0.62,
            textinfo="percent",
            textfont=dict(color=_TEXT, size=12),
            hovertemplate="<b>%{label}</b><br>%{value:,} rows (%{percent})<extra></extra>",
        ))
        _apply_theme(fig, title="Duplicate Row Distribution")
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
        fig.add_trace(go.Bar(name="Mean",    x=cols, y=means,   marker_color="#10b981"))
        fig.add_trace(go.Bar(name="Median",  x=cols, y=medians, marker_color="#0891b2"))
        fig.add_trace(go.Bar(name="Std Dev", x=cols, y=stds,    marker_color="#14b8a6"))

        _apply_theme(fig, title="Descriptive Statistics per Column")
        fig.update_layout(barmode="group", bargap=0.25, bargroupgap=0.08)
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
        for i, col in enumerate(numeric_cols[:8]):   # max 8 columns
            fig.add_trace(go.Box(
                y=df[col].dropna(), name=col,
                boxpoints="outliers",
                marker=dict(color=PALETTE[i % len(PALETTE)], size=4, opacity=0.85),
                line=dict(width=1.4),
                fillcolor="rgba(16,185,129,0.08)",
            ))
        _apply_theme(fig, title="Outlier Distribution")
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

        # Cyan → neutral → emerald diverging scale, matching the brand.
        colorscale = [
            [0.0, "#0891b2"],
            [0.5, "#f1f5f9"],
            [1.0, "#059669"],
        ]
        fig = go.Figure(go.Heatmap(
            z=df.values, x=cols, y=cols,
            colorscale=colorscale, zmid=0,
            text=df.round(2).values,
            texttemplate="%{text}",
            textfont=dict(color=_TEXT, size=11),
            hovertemplate="<b>%{x}</b> × <b>%{y}</b><br>r = %{z:.2f}<extra></extra>",
            colorbar=dict(
                tickfont=dict(color=_MUTED, size=10),
                outlinewidth=0, thickness=10, len=0.7,
            ),
        ))
        _apply_theme(fig, title="Correlation Matrix")
        fig.update_yaxes(showgrid=False)
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

        color_map = {"success": "#10b981", "failed": "#ef4444",
                     "running": "#0891b2", "skipped": "#f59e0b"}
        colors = [color_map.get(s, "#64748b") for s in status_counts["status"]]

        fig = go.Figure(go.Bar(
            x=status_counts["status"], y=status_counts["count"],
            marker=dict(color=colors, line=dict(width=0)),
            text=status_counts["count"], textposition="outside",
            textfont=dict(color=_MUTED, size=11),
            hovertemplate="<b>%{x}</b><br>%{y} runs<extra></extra>",
        ))
        _apply_theme(fig, title="Pipeline Run Status Breakdown")
        fig.update_xaxes(title_text="Status")
        fig.update_yaxes(title_text="Count")
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
        for col, color in [("rows_inserted", "#10b981"),
                           ("rows_skipped",  "#f59e0b"),
                           ("rows_failed",   "#ef4444")]:
            if col in df.columns:
                fig.add_trace(go.Scatter(
                    x=df["logged_at"], y=pd.to_numeric(df[col], errors="coerce"),
                    name=col.replace("_", " ").title(),
                    line=dict(color=color, width=2.2, shape="spline", smoothing=0.6),
                    mode="lines+markers",
                    marker=dict(size=5, line=dict(width=0)),
                    fill="tozeroy",
                    fillcolor=f"rgba({int(color[1:3],16)},{int(color[3:5],16)},{int(color[5:7],16)},0.08)",
                    hovertemplate=f"<b>{col.replace('_',' ').title()}</b><br>%{{y:,}} @ %{{x|%b %d, %H:%M}}<extra></extra>",
                ))

        _apply_theme(fig, title="Row Processing Trend Over Time")
        fig.update_xaxes(title_text="Time")
        fig.update_yaxes(title_text="Row Count")
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
    color = "#10b981" if score >= 80 else "#f59e0b" if score >= 60 else "#ef4444"

    try:
        fig = go.Figure(go.Indicator(
            mode="gauge+number",
            value=score,
            title={"text": f"Data Quality Score — {grade}",
                   "font": {"family": _FONT_FAMILY, "color": _TEXT, "size": 14}},
            gauge={
                "axis":      {"range": [0, 100], "tickcolor": _MUTED,
                              "tickfont": {"color": _MUTED, "size": 10}},
                "bar":       {"color": color, "thickness": 0.32},
                "bgcolor":   "rgba(255,255,255,0.02)",
                "borderwidth": 0,
                "steps": [
                    {"range": [0,  40],  "color": "rgba(239,68,68,0.12)"},
                    {"range": [40, 60],  "color": "rgba(245,158,11,0.12)"},
                    {"range": [60, 80],  "color": "rgba(8,145,178,0.12)"},
                    {"range": [80, 100], "color": "rgba(16,185,129,0.18)"},
                ],
                "threshold": {"line": {"color": "#0f172a", "width": 3}, "value": score},
            },
            number={"suffix": "/100",
                    "font": {"family": _FONT_FAMILY, "color": _TEXT, "size": 32}},
        ))
        _apply_theme(fig, height=320)
        result = _fig_to_html(fig)
        logger.info("Quality gauge generated")
        return result
    except Exception as e:
        logger.error("Failed to generate quality gauge: %s", e, exc_info=True)
        return ""
