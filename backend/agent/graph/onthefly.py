
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
                             existing_charts: list[dict] = None) -> dict:
    if not data:
        return {"error": "No data available"}

    llm_client, default_model = _get_onthefly_llm()
    if not llm_client:
        return {"error": "No LLM API key configured. Set GROQ_API_KEY or OPENROUTER_API_KEY in .env and restart the backend."}

    effective_model = model or default_model

    df = pd.DataFrame(data)

    # Coerce numeric-looking columns
    for col in df.columns:
        converted = pd.to_numeric(df[col], errors="coerce")
        if converted.notna().sum() / max(len(df), 1) > 0.8:
            df[col] = converted

    # ── THESE MUST COME BEFORE decision_prompt ──
    columns = df.columns.tolist()
    numeric = df.select_dtypes(include="number").columns.tolist()
    categ   = df.select_dtypes(include="object").columns.tolist()

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

{existing_summary}

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
- Choose a DIFFERENT column combination and/or chart type than what's already shown above
- For pie: x_column = category column, y_column = null
- For histogram: x_column = numeric column, y_column = null
- If user said specific columns, use them
- If user said "best chart" or "relevant chart", pick the most insightful combination not already covered
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

    chart_type  = config.get("chart_type", "bar")
    x_col       = config.get("x_column")
    y_col       = config.get("y_column")
    title       = config.get("title", user_request)
    description = config.get("description", "")

    from agent.tools.chart_tools import _apply_theme, PALETTE

    fig = go.Figure()

    if chart_type == "bar" and x_col and y_col and x_col in df and y_col in df:
        grp = df.groupby(x_col)[y_col].sum().reset_index().sort_values(y_col, ascending=False).head(20)
        fig.add_trace(go.Bar(
            x=grp[x_col], y=grp[y_col],
            marker=dict(color="#10b981", line=dict(width=0)),
            hovertemplate="<b>%{x}</b><br>%{y:,}<extra></extra>",
        ))

    elif chart_type in ("bar", "pie") and x_col and not y_col and x_col in df:
        counts = df[x_col].value_counts().head(20).reset_index()
        counts.columns = [x_col, "count"]
        if chart_type == "pie":
            fig.add_trace(go.Pie(
                labels=counts[x_col], values=counts["count"], hole=0.55,
                marker=dict(colors=PALETTE, line=dict(color="#ffffff", width=2)),
                textinfo="percent",
                hovertemplate="<b>%{label}</b><br>%{value:,} (%{percent})<extra></extra>",
            ))
        else:
            fig.add_trace(go.Bar(
                x=counts[x_col], y=counts["count"],
                marker=dict(color="#10b981", line=dict(width=0)),
                hovertemplate="<b>%{x}</b><br>%{y:,} records<extra></extra>",
            ))
        title = title or f"{x_col} count"

    elif chart_type == "line" and x_col and y_col and x_col in df and y_col in df:
        srt = df[[x_col, y_col]].dropna().sort_values(x_col)
        fig.add_trace(go.Scatter(
            x=srt[x_col], y=srt[y_col],
            mode="lines+markers",
            line=dict(color="#059669", width=2.2, shape="spline", smoothing=0.6),
            marker=dict(size=5, color="#059669", line=dict(width=0)),
            fill="tozeroy", fillcolor="rgba(16,185,129,0.10)",
            hovertemplate="%{x}<br><b>%{y:,}</b><extra></extra>",
        ))

    elif chart_type == "pie" and x_col and x_col in df:
        counts = df[x_col].value_counts().head(10)
        fig.add_trace(go.Pie(
            labels=counts.index, values=counts.values, hole=0.55,
            marker=dict(colors=PALETTE, line=dict(color="#ffffff", width=2)),
            textinfo="percent",
            hovertemplate="<b>%{label}</b><br>%{value:,} (%{percent})<extra></extra>",
        ))

    elif chart_type == "scatter" and x_col and y_col and x_col in df and y_col in df:
        fig.add_trace(go.Scatter(
            x=df[x_col], y=df[y_col], mode="markers",
            marker=dict(color="#0891b2", size=7, opacity=0.75, line=dict(width=0)),
            hovertemplate="<b>%{x}</b>, <b>%{y}</b><extra></extra>",
        ))

    elif chart_type == "histogram" and x_col and x_col in df:
        fig.add_trace(go.Histogram(
            x=df[x_col],
            marker=dict(color="#14b8a6", line=dict(width=0)),
        ))

    else:
        return {
            "error": (
                f"Could not build a '{chart_type}' chart for x={x_col!r}, y={y_col!r}. "
                f"Available columns: {columns}"
            )
        }
    
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