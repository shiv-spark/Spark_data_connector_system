

import os
import json
from openai import OpenAI
import pandas as pd
import plotly.graph_objects as go


def _get_onthefly_llm():
    groq_key = os.getenv("GROQ_API_KEY")
    or_key   = os.getenv("OPENROUTER_API_KEY")

    if groq_key:
        return (
            OpenAI(base_url="https://api.groq.com/openai/v1", api_key=groq_key),
            os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile"),
        )
    if or_key:
        return (
            OpenAI(base_url="https://openrouter.ai/api/v1", api_key=or_key),
            os.getenv("OPENROUTER_MODEL", "meta-llama/llama-3.3-70b-instruct:free"),
        )
    return None, None


def generate_onthefly_chart(data: list[dict], user_request: str, model: str = None,
                             existing_charts: list[dict] = None,
                             target_chart: dict = None) -> dict:
    """
    target_chart: when set (editing an existing slot via toolbar buttons),
    this is that chart's saved chart_meta entry — {"slot", "title", "config": {...}}.
    When present, the LLM is told to EDIT that chart (keep same columns/type
    unless explicitly asked to change them) instead of inventing a new insight.
    """
    if not data:
        return {"error": "No data available"}

    llm_client, default_model = _get_onthefly_llm()
    if not llm_client:
        return {"error": "No LLM API key configured. Set GROQ_API_KEY or OPENROUTER_API_KEY in .env and restart the backend."}

    effective_model = model or default_model

    df = pd.DataFrame(data)

    for col in df.columns:
        converted = pd.to_numeric(df[col], errors="coerce")
        if converted.notna().sum() / max(len(df), 1) > 0.8:
            df[col] = converted

    columns = df.columns.tolist()
    numeric = df.select_dtypes(include="number").columns.tolist()
    categ   = df.select_dtypes(include="object").columns.tolist()

    current_cfg = (target_chart or {}).get("config", {}) or {}

    if target_chart:
        # EDIT MODE — anchor the LLM to the chart being edited.
        edit_block = f"""You are EDITING an EXISTING chart (slot {target_chart.get('slot')}), not creating a new one.

Current chart config:
- chart_type: {current_cfg.get('chart_type')}
- x_column: {current_cfg.get('x_column')}
- y_column: {current_cfg.get('y_column')}
- title: "{target_chart.get('title')}"

RULES:
- Keep the SAME x_column, y_column, and chart_type as above UNLESS the user's request explicitly asks to change them (e.g. "change to a bar chart", "use column X instead").
- If the user only asked for a color/font/legend/style change, you MUST reuse the exact same x_column, y_column and chart_type as listed above — do not pick a different metric.
- If the user asked to change the chart type only, keep the same x_column/y_column.
"""
        existing_summary = ""
    else:
        # ADD MODE — original "pick something new" behaviour.
        edit_block = ""
        existing_summary = ""
        if existing_charts:
            lines = []
            for c in existing_charts:
                cfg = c.get("config", {})
                lines.append(
                    f"- {c.get('title', 'Untitled')} "
                    f"(type={cfg.get('chart_type')}, x={cfg.get('x_column')}, y={cfg.get('y_column')})"
                )
            existing_summary = "Charts already on this dashboard (DO NOT repeat these column/type combos):\n" + "\n".join(lines)

    decision_prompt = f"""You are a data visualization expert.

Available columns: {columns}
Numeric columns: {numeric}
Categorical columns: {categ}
Sample row: {df.head(1).to_dict(orient='records')}

{edit_block}
{existing_summary}

User request: "{user_request}"

Respond ONLY with a JSON object, no extra text, no markdown:
{{
  "chart_type": "bar" | "line" | "area" | "pie" | "donut" | "scatter" | "histogram" | "table",
  "x_column": "column name or null",
  "y_column": "column name or null",
  "title": "chart title",
  "description": "one sentence explaining what this chart shows",
  "color": "hex color(s) comma-separated if user asked to recolor, else null",
  "font_size": "integer font size if user asked to change it, else null",
  "show_legend": "true/false if user asked to show/hide legend, else null",
  "sort_order": "asc" | "desc" | null
}}

Rules:
- Pick columns that actually exist in the list above
{"- Choose a DIFFERENT column combination and/or chart type than what's already shown above" if not target_chart else ""}
- For pie/donut: x_column = category column, y_column = null
- For histogram: x_column = numeric column, y_column = null
- For table: x_column = category/group column, y_column = numeric column to aggregate (or null to just list rows)
- If user said specific columns, use them
- If user said "best chart" or "relevant chart", pick the most insightful combination not already covered
- If the user asks to sort ascending/descending, set sort_order accordingly ("asc" or "desc"). Otherwise keep it null.
"""

    try:
        response = llm_client.chat.completions.create(
            model      = effective_model,
            messages   = [{"role": "user", "content": decision_prompt}],
            max_tokens = 300,
        )
        raw = response.choices[0].message.content.strip()
        raw = raw.replace("```json", "").replace("```", "").strip()
        config = json.loads(raw)
    except Exception as e:
        return {"error": f"Chart decision failed: {e}"}

    if not isinstance(config, dict):
        return {"error": "Chart decision returned invalid format"}

    from agent.tools.chart_tools import _apply_theme, PALETTE

    # Fall back to the CURRENT chart's columns/type when editing and the
    # LLM omits them (e.g. a pure color-change request).
    if target_chart:
        chart_type = config.get("chart_type") or current_cfg.get("chart_type", "bar")
        x_col      = config.get("x_column") if config.get("x_column") is not None else current_cfg.get("x_column")
        y_col      = config.get("y_column") if config.get("y_column") is not None else current_cfg.get("y_column")
        title      = config.get("title") or target_chart.get("title") or user_request
    else:
        chart_type = config.get("chart_type", "bar")
        x_col      = config.get("x_column")
        y_col      = config.get("y_column")
        title      = config.get("title", user_request)

    description  = config.get("description", "")
    color_hint   = config.get("color")
    font_size    = config.get("font_size")
    show_legend  = config.get("show_legend")
    main_color   = (str(color_hint).split(",")[0].strip() if color_hint else "#10b981")
    palette_list = ([c.strip() for c in str(color_hint).split(",")] if color_hint else PALETTE)
    sort_order = config.get("sort_order")
    if not sort_order and target_chart:
        sort_order = current_cfg.get("sort_order")
    ascending = (str(sort_order).lower() == "asc")

    is_donut = chart_type == "donut"
    is_area  = chart_type == "area"
    if is_donut:
        chart_type = "pie"
    if is_area:
        chart_type = "line"

    line_shape = "linear" if is_area else "spline"

    fig = go.Figure()

    if chart_type == "table":
        if x_col and x_col in df:
            if y_col and y_col in df:
                grp = df.groupby(x_col)[y_col].sum().reset_index().sort_values(y_col, ascending=ascending).head(30)
                headers = [x_col, y_col]
                cell_vals = [grp[x_col].astype(str), grp[y_col]]
            else:
                counts = df[x_col].value_counts().head(30).reset_index()
                counts.columns = [x_col, "count"]
                headers = [x_col, "count"]
                cell_vals = [counts[x_col].astype(str), counts["count"]]
        else:
            preview = df.head(30)
            headers = preview.columns.tolist()
            cell_vals = [preview[c].astype(str) for c in preview.columns]

        fig.add_trace(go.Table(
            header=dict(values=headers, fill_color=main_color, font=dict(color="white", size=12), align="left"),
            cells=dict(values=cell_vals, fill_color="rgba(15,23,42,0.02)", align="left"),
        ))

    elif chart_type == "bar" and x_col and y_col and x_col in df and y_col in df:
        grp = df.groupby(x_col)[y_col].sum().reset_index().sort_values(y_col, ascending=ascending).head(20)
        fig.add_trace(go.Bar(
            x=grp[x_col], y=grp[y_col],
            marker=dict(color=main_color, line=dict(width=0)),
            hovertemplate="<b>%{x}</b><br>%{y:,}<extra></extra>",
        ))

    elif chart_type in ("bar", "pie") and x_col and not y_col and x_col in df:
        vc = df[x_col].value_counts()
        vc = vc.sort_values(ascending=ascending)
        counts = vc.head(20).reset_index()
        # counts = df[x_col].value_counts().head(20).reset_index()
        counts.columns = [x_col, "count"]
        if chart_type == "pie":
            fig.add_trace(go.Pie(
                labels=counts[x_col], values=counts["count"], hole=(0.68 if is_donut else 0.55),
                marker=dict(colors=palette_list, line=dict(color="#ffffff", width=2)),
                textinfo="percent",
                hovertemplate="<b>%{label}</b><br>%{value:,} (%{percent})<extra></extra>",
            ))
        else:
            fig.add_trace(go.Bar(
                x=counts[x_col], y=counts["count"],
                marker=dict(color=main_color, line=dict(width=0)),
                hovertemplate="<b>%{x}</b><br>%{y:,} records<extra></extra>",
            ))
        title = title or f"{x_col} count"

    elif chart_type == "line" and x_col and y_col and x_col in df and y_col in df:
        srt = df[[x_col, y_col]].dropna().sort_values(x_col)
        fig.add_trace(go.Scatter(
            x=srt[x_col], y=srt[y_col],
            mode="lines+markers",
            line=dict(color=main_color, width=2.2, shape=line_shape, smoothing=0.6),
            marker=dict(size=5, color=main_color, line=dict(width=0)),
            fill="tozeroy",
            fillcolor=f"rgba({int(main_color[1:3],16)},{int(main_color[3:5],16)},{int(main_color[5:7],16)},{0.5 if is_area else 0.10})",
            hovertemplate="%{x}<br><b>%{y:,}</b><extra></extra>",
        ))

    elif chart_type == "line" and x_col and not y_col and x_col in df:
        # No numeric y_column available — plot counts per category instead,
        # so line/area charts work even for category-only chart configs.
        counts = df[x_col].value_counts().sort_index()
        fig.add_trace(go.Scatter(
            x=counts.index, y=counts.values,
            mode="lines+markers",
            line=dict(color=main_color, width=2.2, shape=line_shape, smoothing=0.6),
            marker=dict(size=5, color=main_color, line=dict(width=0)),
            fill="tozeroy",
            fillcolor=f"rgba({int(main_color[1:3],16)},{int(main_color[3:5],16)},{int(main_color[5:7],16)},{0.5 if is_area else 0.10})",
            hovertemplate="<b>%{x}</b><br>%{y:,} records<extra></extra>",
        ))
        title = title or f"{x_col} count"

    elif chart_type == "pie" and x_col and x_col in df:
        counts = df[x_col].value_counts().head(10)
        fig.add_trace(go.Pie(
            labels=counts.index, values=counts.values, hole=(0.68 if is_donut else 0.55),
            marker=dict(colors=palette_list, line=dict(color="#ffffff", width=2)),
            textinfo="percent",
            hovertemplate="<b>%{label}</b><br>%{value:,} (%{percent})<extra></extra>",
        ))

    elif chart_type == "scatter" and x_col and y_col and x_col in df and y_col in df:
        fig.add_trace(go.Scatter(
            x=df[x_col], y=df[y_col], mode="markers",
            marker=dict(color=main_color, size=7, opacity=0.75, line=dict(width=0)),
            hovertemplate="<b>%{x}</b>, <b>%{y}</b><extra></extra>",
        ))

    elif chart_type == "histogram" and x_col and x_col in df:
        fig.add_trace(go.Histogram(
            x=df[x_col],
            marker=dict(color=main_color, line=dict(width=0)),
        ))

    else:
        return {
            "error": (
                f"Could not build a '{chart_type}' chart for x={x_col!r}, y={y_col!r}. "
                f"Available columns: {columns}"
            )
        }

    if chart_type != "table":
        x_label = x_col.replace("_", " ").title() if x_col else None
        y_label = y_col.replace("_", " ").title() if y_col else None
        if chart_type in ("bar", "line", "scatter") and x_label:
            fig.update_xaxes(title_text=x_label)
        if chart_type in ("bar", "line", "scatter") and y_label:
            fig.update_yaxes(title_text=y_label)
        if chart_type == "histogram" and x_label:
            fig.update_xaxes(title_text=x_label)
            fig.update_yaxes(title_text="Count")
        if chart_type in ("bar", "pie") and not y_col and x_label:
            fig.update_yaxes(title_text="Count")
        if chart_type in ("bar", "pie", "line") and not y_col and x_label:
            fig.update_yaxes(title_text="Count")

        _apply_theme(fig, title=title, height=320)
        if font_size:
            fig.update_layout(font=dict(size=int(font_size)))
        if show_legend is not None:
            fig.update_layout(showlegend=str(show_legend).lower() == "true")
    else:
        fig.update_layout(title=dict(text=title, font=dict(size=14)), height=320,
                           margin=dict(l=10, r=10, t=40, b=10))
        if font_size:
            fig.update_layout(font=dict(size=int(font_size)))

    chart_html = fig.to_html(
        full_html=False, include_plotlyjs=False,
        config={"displayModeBar": False, "responsive": True},
        default_height="320px",
    )

    return {
        "chart":       chart_html,
        "chart_html":  chart_html,
        "title":       title,
        "description": description,
        "config":      config,
    }