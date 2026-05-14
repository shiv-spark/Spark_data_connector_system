"""
ADD THIS FUNCTION TO THE BOTTOM OF nodes.py
This handles on-the-fly chart requests from the dashboard chat input.
"""

import os
import json
from openai import OpenAI
import pandas as pd
import plotly.graph_objects as go

# reuse same client from top of nodes.py (already defined there)


def generate_onthefly_chart(data: list[dict], user_request: str) -> dict:
    """
    User types: 'bar chart of Quantity vs Product'
    LLM reads columns + request → decides chart type + columns → generates it.
    Returns base64 PNG + description.
    """
    if not data:
        return {"error": "No data available"}

    df      = pd.DataFrame(data)
    columns = df.columns.tolist()
    numeric = df.select_dtypes(include="number").columns.tolist()
    categ   = df.select_dtypes(include="object").columns.tolist()

    # Ask LLM to decide chart config
    decision_prompt = f"""You are a data visualization expert.

Available columns: {columns}
Numeric columns: {numeric}
Categorical columns: {categ}
Sample row: {df.head(1).to_dict(orient='records')}

User request: "{user_request}"

Respond ONLY with a JSON object, no extra text, no markdown:
{{
  "chart_type": "bar" | "line" | "pie" | "scatter" | "histogram",
  "x_column": "column name or null",
  "y_column": "column name or null",
  "title": "chart title",
  "description": "one sentence explaining what this chart shows"
}}

Rules:
- Pick columns that actually exist in the list above
- For pie: x_column = category column, y_column = null
- For histogram: x_column = numeric column, y_column = null
- If user said specific columns, use them
- If user said "best chart" or "relevant chart", pick the most insightful combination
"""

    llm_client = OpenAI(
        base_url = "https://openrouter.ai/api/v1",
        api_key  = os.getenv("OPENROUTER_API_KEY"),
    )
    MODEL = os.getenv("OPENROUTER_MODEL", "meta-llama/llama-3.3-70b-instruct:free")

    response = llm_client.chat.completions.create(
        model      = MODEL,
        messages   = [{"role": "user", "content": decision_prompt}],
        max_tokens = 300,
    )

    raw = response.choices[0].message.content.strip()
    # strip markdown fences if any
    raw = raw.replace("```json", "").replace("```", "").strip()
    config = json.loads(raw)

    chart_type  = config.get("chart_type", "bar")
    x_col       = config.get("x_column")
    y_col       = config.get("y_column")
    title       = config.get("title", user_request)
    description = config.get("description", "")

    # ── Generate the chart ──────────────────────────────────────────────────
    from agent.tools.chart_tools import _apply_theme, PALETTE  # shared dark-glass theme

    fig = go.Figure()

    if chart_type == "bar" and x_col and y_col:
        grp = df.groupby(x_col)[y_col].sum().reset_index().sort_values(y_col, ascending=False).head(20)
        fig.add_trace(go.Bar(
            x=grp[x_col], y=grp[y_col],
            marker=dict(color="#10b981", line=dict(width=0)),
            hovertemplate="<b>%{x}</b><br>%{y:,}<extra></extra>",
        ))

    elif chart_type == "line" and x_col and y_col:
        srt = df[[x_col, y_col]].dropna().sort_values(x_col)
        fig.add_trace(go.Scatter(
            x=srt[x_col], y=srt[y_col],
            mode="lines+markers",
            line=dict(color="#059669", width=2.2, shape="spline", smoothing=0.6),
            marker=dict(size=5, color="#059669", line=dict(width=0)),
            fill="tozeroy", fillcolor="rgba(16,185,129,0.10)",
            hovertemplate="%{x}<br><b>%{y:,}</b><extra></extra>",
        ))

    elif chart_type == "pie" and x_col:
        counts = df[x_col].value_counts().head(10)
        fig.add_trace(go.Pie(
            labels=counts.index, values=counts.values, hole=0.55,
            marker=dict(colors=PALETTE, line=dict(color="#ffffff", width=2)),
            textinfo="percent",
            hovertemplate="<b>%{label}</b><br>%{value:,} (%{percent})<extra></extra>",
        ))

    elif chart_type == "scatter" and x_col and y_col:
        fig.add_trace(go.Scatter(
            x=df[x_col], y=df[y_col], mode="markers",
            marker=dict(color="#0891b2", size=7, opacity=0.75, line=dict(width=0)),
            hovertemplate="<b>%{x}</b>, <b>%{y}</b><extra></extra>",
        ))

    elif chart_type == "histogram" and x_col:
        fig.add_trace(go.Histogram(
            x=df[x_col],
            marker=dict(color="#14b8a6", line=dict(width=0)),
        ))

    else:
        return {"error": f"Could not generate chart — columns not found or unsupported type"}

    _apply_theme(fig, title=title, height=320)
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
