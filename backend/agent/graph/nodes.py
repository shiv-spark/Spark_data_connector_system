import os
from openai import OpenAI
from agent.graph.state import PipelineState
from agent.logger import get_logger
from agent.tools.data_tools     import (fetch_pipeline_runs, fetch_pipeline_metrics,
                                         fetch_data_by_source, fetch_full_pipeline_summary,
                                         fetch_table_data)
from agent.tools.analysis_tools import (check_nulls_and_missing, check_duplicates,
                                         get_descriptive_stats, detect_outliers,
                                         get_correlation_matrix, check_data_type_issues,
                                         analyze_pipeline_health, calculate_quality_score)
from agent.tools.chart_tools    import (generate_null_bar_chart, generate_duplicate_pie,
                                         generate_stats_chart, generate_outlier_boxplot,
                                         generate_correlation_heatmap, generate_run_status_chart,
                                         generate_metrics_trend_chart, generate_quality_gauge)
from agent.tools.report_tools   import build_html_report
from agent.claude_dashboard     import (build_dashboard_plan_with_claude,
                                         build_summary_with_claude)

logger = get_logger(__name__)

# ── Lazy LLM client — avoids crash when API keys are not yet set ──────────────
_client = None

def _get_llm():
    global _client
    if _client is None:
        groq_key = os.getenv("GROQ_API_KEY")
        or_key   = os.getenv("OPENROUTER_API_KEY")
        if groq_key:
            _client = OpenAI(
                base_url="https://api.groq.com/openai/v1",
                api_key=groq_key,
            )
            logger.info("LLM client → Groq")
        elif or_key:
            _client = OpenAI(
                base_url="https://openrouter.ai/api/v1",
                api_key=or_key,
            )
            logger.info("LLM client → OpenRouter")
        else:
            raise RuntimeError(
                "No LLM API key found. Set GROQ_API_KEY or OPENROUTER_API_KEY in .env"
            )
    return _client

def _get_model():
    if os.getenv("GROQ_API_KEY"):
        return os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
    return os.getenv("OPENROUTER_MODEL", "meta-llama/llama-3.3-70b-instruct:free")

def _resolve_model(state: PipelineState) -> str:
    """Use the user-selected model if provided, else fall back to env default."""
    override = (state.get("model") or "").strip()
    if override:
        return override
    return _get_model()

# def node_fetch_data(state: PipelineState) -> dict:
#     logger.info("═══ Node: fetch_data ═══  source=%s, pipeline=%s",
#                 state["source_type"], state.get("pipeline_name"))
#     try:
#         if state["source_type"] == "postgres":
#             data = fetch_full_pipeline_summary(state.get("pipeline_name"))
#         else:
#             raw  = fetch_data_by_source(state["source_type"],
#                                         file_path     = state.get("file_path"),
#                                         sheet_url     = state.get("sheet_url"),
#                                         pipeline_name = state.get("pipeline_name"),
#                                         table_name    = state.get("table_name"),
#                                         s3_path       = state.get("s3_path"),
#                                         api_url       = state.get("api_url"),
#                                         api_headers   = state.get("api_headers"))
#             data = {"metrics": raw, "runs": []}
#         logger.info("fetch_data → metrics=%d, runs=%d",
#                     len(data.get("metrics", [])), len(data.get("runs", [])))
#         return {"data": data}
#     except Exception as e:
#         logger.error("fetch_data failed: %s", e, exc_info=True)
#         return {"data": {}, "error": str(e)}
def node_fetch_data(state: PipelineState) -> dict:
    logger.info("═══ Node: fetch_data ═══  source=%s, pipeline=%s",
                state["source_type"], state.get("pipeline_name"))
    try:
        if state["source_type"] == "postgres":
            table_name = state.get("table_name")
            pg_host    = state.get("pg_host")

            if pg_host:
                # Direct connection picked from Connections dropdown —
                # use the REAL credentials resolved server-side.
                from agent.tools.data_tools import fetch_table_data_direct
                metrics = fetch_table_data_direct(
                    host       = pg_host,
                    port       = state.get("pg_port"),
                    database   = state.get("pg_database"),
                    user       = state.get("pg_user"),
                    password   = state.get("pg_password"),
                    table_name = table_name,
                )
                data = {"metrics": metrics, "runs": []}
                logger.info("fetch_data (postgres/direct) → host=%s db=%s rows=%d",
                            pg_host, state.get("pg_database"), len(metrics))
            elif table_name:
                metrics = fetch_table_data(table_name)
                runs = fetch_pipeline_runs(state.get("pipeline_name"))
                data = {"metrics": metrics, "runs": runs}
                logger.info("fetch_data (postgres/table) → table=%s, rows=%d",
                            table_name, len(metrics))
            else:
                data = fetch_full_pipeline_summary(state.get("pipeline_name"))
        else:
            raw  = fetch_data_by_source(state["source_type"],
                                        file_path     = state.get("file_path"),
                                        sheet_url     = state.get("sheet_url"),
                                        pipeline_name = state.get("pipeline_name"),
                                        table_name    = state.get("table_name"),
                                        s3_path       = state.get("s3_path"),
                                        api_url       = state.get("api_url"),
                                        api_headers   = state.get("api_headers"),
                                        sf_account    = state.get("sf_account"),
                                        sf_user       = state.get("sf_user"),
                                        sf_password   = state.get("sf_password"),
                                        sf_warehouse  = state.get("sf_warehouse"),
                                        sf_database   = state.get("sf_database"),
                                        sf_schema     = state.get("sf_schema"),
                                        sf_table      = state.get("sf_table"),
                                        sf_query      = state.get("sf_query"),
                                        sf_role       = state.get("sf_role"))
            data = {"metrics": raw, "runs": []}
        logger.info("fetch_data → metrics=%d, runs=%d",
                    len(data.get("metrics", [])), len(data.get("runs", [])))
        return {"data": data}
    except Exception as e:
        logger.error("fetch_data failed: %s", e, exc_info=True)
        return {"data": {}, "error": str(e)}

# def node_fetch_data(state: PipelineState) -> dict:
#     logger.info("═══ Node: fetch_data ═══  source=%s, pipeline=%s",
#                 state["source_type"], state.get("pipeline_name"))
#     try:
#         if state["source_type"] == "postgres":
#             table_name = state.get("table_name")
#             if table_name:
#                 # Analyze the ACTUAL data table (e.g. "dash"), not the
#                 # pipeline_metrics ingestion-log table. Also pull recent
#                 # runs so health_check still works downstream.
#                 metrics = fetch_table_data(table_name)
#                 runs = fetch_pipeline_runs(state.get("pipeline_name"))
#                 data = {"metrics": metrics, "runs": runs}
#                 logger.info("fetch_data (postgres/table) → table=%s, rows=%d",
#                             table_name, len(metrics))
#             else:
#                 # No table_name given — fall back to old behaviour
#                 # (pipeline run/metrics summary only).
#                 data = fetch_full_pipeline_summary(state.get("pipeline_name"))
#         else:
#             raw  = fetch_data_by_source(state["source_type"],
#                                         file_path     = state.get("file_path"),
#                                         sheet_url     = state.get("sheet_url"),
#                                         pipeline_name = state.get("pipeline_name"),
#                                         table_name    = state.get("table_name"),
#                                         s3_path       = state.get("s3_path"),
#                                         api_url       = state.get("api_url"),
#                                         api_headers   = state.get("api_headers"),
#                                         sf_account    = state.get("sf_account"),     
#                                         sf_user       = state.get("sf_user"),        # ← NEW
#                                         sf_password   = state.get("sf_password"),    # ← NEW
#                                         sf_warehouse  = state.get("sf_warehouse"),   # ← NEW
#                                         sf_database   = state.get("sf_database"),    # ← NEW
#                                         sf_schema     = state.get("sf_schema"),      # ← NEW
#                                         sf_table      = state.get("sf_table"),       # ← NEW
#                                         sf_query      = state.get("sf_query"),       # ← NEW
#                                         sf_role       = state.get("sf_role"))
#             data = {"metrics": raw, "runs": []}
#         logger.info("fetch_data → metrics=%d, runs=%d",
#                     len(data.get("metrics", [])), len(data.get("runs", [])))
#         return {"data": data}
#     except Exception as e:
#         logger.error("fetch_data failed: %s", e, exc_info=True)
#         return {"data": {}, "error": str(e)}

def node_null_analysis(state: PipelineState) -> dict:
    logger.info("═══ Node: null_analysis ═══")
    try:
        result = check_nulls_and_missing(state["data"].get("metrics", []))
        logger.info("null_analysis → critical=%d, warning=%d",
                    len(result.get("critical_cols", [])), len(result.get("warning_cols", [])))
        return {"null_result": result}
    except Exception as e:
        logger.error("null_analysis failed: %s", e, exc_info=True)
        return {"null_result": {"error": str(e)}}


def node_duplicate_check(state: PipelineState) -> dict:
    logger.info("═══ Node: duplicate_check ═══")
    try:
        result = check_duplicates(state["data"].get("metrics", []))
        logger.info("duplicate_check → %d duplicates (%.2f%%)",
                    result.get("duplicate_rows", 0), result.get("duplicate_pct", 0))
        return {"dup_result": result}
    except Exception as e:
        logger.error("duplicate_check failed: %s", e, exc_info=True)
        return {"dup_result": {"error": str(e)}}


def node_stats(state: PipelineState) -> dict:
    logger.info("═══ Node: stats ═══")
    try:
        result = get_descriptive_stats(state["data"].get("metrics", []))
        logger.info("stats → %d numeric columns", len(result.get("stats", {})))
        return {"stats_result": result}
    except Exception as e:
        logger.error("stats failed: %s", e, exc_info=True)
        return {"stats_result": {"error": str(e)}}


def node_outliers(state: PipelineState) -> dict:
    logger.info("═══ Node: outliers ═══")
    try:
        result = detect_outliers(state["data"].get("metrics", []))
        logger.info("outliers → %d columns with outliers",
                    len(result.get("outliers", {})))
        return {"outlier_result": result}
    except Exception as e:
        logger.error("outliers failed: %s", e, exc_info=True)
        return {"outlier_result": {"error": str(e)}}


def node_correlation(state: PipelineState) -> dict:
    logger.info("═══ Node: correlation ═══")
    try:
        result = get_correlation_matrix(state["data"].get("metrics", []))
        logger.info("correlation complete")
        return {"corr_result": result}
    except Exception as e:
        logger.error("correlation failed: %s", e, exc_info=True)
        return {"corr_result": {"error": str(e)}}


def node_health_check(state: PipelineState) -> dict:
    logger.info("═══ Node: health_check ═══")
    try:
        runs    = state["data"].get("runs", [])
        metrics = state["data"].get("metrics", [])
        health  = analyze_pipeline_health(runs, metrics)
        quality = calculate_quality_score(
            state["null_result"], state["dup_result"],
            check_data_type_issues(metrics), state["outlier_result"]
        )
        logger.info("health_check → quality_score=%.1f, grade=%s",
                    quality.get("quality_score", 0), quality.get("grade", "?"))
        return {"health_result": health, "quality_result": quality}
    except Exception as e:
        logger.error("health_check failed: %s", e, exc_info=True)
        return {"health_result": {}, "quality_result": {}, "error": str(e)}


def node_quality_score_only(state: PipelineState) -> dict:
    """Used when source is not postgres — skips health check but still computes score."""
    logger.info("═══ Node: quality_score_only ═══  (non-postgres source)")
    try:
        metrics = state["data"].get("metrics", [])
        quality = calculate_quality_score(
            state["null_result"], state["dup_result"],
            check_data_type_issues(metrics), state["outlier_result"]
        )
        logger.info("quality_score_only → score=%.1f, grade=%s",
                    quality.get("quality_score", 0), quality.get("grade", "?"))
        return {"health_result": {}, "quality_result": quality}
    except Exception as e:
        logger.error("quality_score_only failed: %s", e, exc_info=True)
        return {"health_result": {}, "quality_result": {}, "error": str(e)}


def node_generate_charts(state: PipelineState) -> dict:
    """
    LLM decides the 4 most relevant charts based on the actual dataset columns.
    Also generates fixed quality charts (gauge, null_bar, dup_pie) as supporting visuals.
    """
    logger.info("═══ Node: generate_charts ═══")
    import json
    import pandas as pd
    import numpy as np
    import plotly.graph_objects as go
    import base64

    try:
        metrics = state["data"].get("metrics", [])
        runs    = state["data"].get("runs",    [])
        score   = state["quality_result"].get("quality_score", 0)
        grade   = state["quality_result"].get("grade", "Unknown")

        # ── Fixed quality charts (always generated) ──────────────────────────
        fixed = {
            "gauge":    generate_quality_gauge(score, grade),
            "null_bar": generate_null_bar_chart(state["null_result"]) if state["null_result"] else "",
            "dup_pie":  generate_duplicate_pie(state["dup_result"])   if state["dup_result"]  else "",
        }

        # ── LLM decides 4 best charts ────────────────────────────────────────
        llm_charts = {}
        llm_chart_meta = []   # [{slot, title, description, type, x, y}]

        if metrics:
            df      = pd.DataFrame(metrics)
            numeric = df.select_dtypes(include="number").columns.tolist()
            categ   = df.select_dtypes(include="object").columns.tolist()
            datetime_cols = [c for c in df.columns if "date" in c.lower() or "time" in c.lower()]
            sample  = df.head(3).to_dict(orient="records")

            decision_prompt = f"""You are a data visualization expert.

Dataset columns: {df.columns.tolist()}
Numeric columns: {numeric}
Categorical columns: {categ}
Date/time columns: {datetime_cols}
Total rows: {len(df)}
Sample data: {sample}
Stats summary: {state.get('stats_result', {}).get('stats', {})}
Strong correlations: {state.get('corr_result', {}).get('strong_correlations', [])}

Pick the 4 MOST INSIGHTFUL charts for this specific dataset.
Choose chart types that reveal real patterns — trends, distributions, comparisons, relationships.

Rules:
- Use only columns that exist in the list above
- If date/time column exists, at least one chart should be a time trend
- If strong correlations exist, include a scatter plot for the strongest pair
- Prefer charts that show business/analytical value over generic ones
- For pie charts, only use categorical columns with 2-10 unique values
- NEVER use an ID-like column (customer_id, order_id, etc.) or any column with more than 20 unique values as a bar/pie chart's category axis — it will be unreadable. Aggregate or pick a lower-cardinality column instead.

Respond ONLY with a valid JSON array of exactly 4 objects, no markdown, no extra text:
[
  {{
    "slot": 1,
    "chart_type": "bar|line|pie|scatter|histogram|box",
    "x_column": "column name or null",
    "y_column": "column name or null",
    "title": "descriptive chart title",
    "description": "one sentence explaining the insight this chart reveals"
  }},
  ...
]"""

            chart_source = "fallback"
            claude_plan = build_dashboard_plan_with_claude(state)
            if claude_plan:
                chart_configs = claude_plan.get("charts", [])
                chart_source = "claude_agent_sdk"
                logger.info("Claude Agent SDK decided %d charts", len(chart_configs))
            else:
                try:
                    resp = _get_llm().chat.completions.create(
                        # model    = _get_model(),
                        model    = _resolve_model(state),
                        messages = [{"role": "user", "content": decision_prompt}],
                        max_tokens = 600,
                    )
                    raw = resp.choices[0].message.content.strip()
                    raw = raw.replace("```json","").replace("```","").strip()
                    chart_configs = json.loads(raw)
                    chart_source = "openai_compatible_llm"
                    logger.info("LLM decided %d charts", len(chart_configs))
                except Exception as ex:
                    logger.warning("LLM chart decision failed, using fallback: %s", ex)
                    chart_configs = _fallback_chart_configs(df, numeric, categ, datetime_cols)

            # ── Generate each LLM-decided chart ──────────────────────────────
            # Use the shared dashboard theme so customizable-board charts blend
            # into the white surface cards (transparent paper, emerald palette).
            from agent.tools.chart_tools import _apply_theme, _fig_to_html, PALETTE

            def fig_to_html(fig):
                return _fig_to_html(fig)

            for cfg in chart_configs:
                slot   = cfg.get("slot", 1)
                ctype  = cfg.get("chart_type", "bar")
                xcol   = cfg.get("x_column")
                ycol   = cfg.get("y_column")
                title  = cfg.get("title", f"Chart {slot}")
                desc   = cfg.get("description", "")
                fig    = go.Figure()

                try:
                    # if ctype == "bar" and xcol and ycol and xcol in df and ycol in df:
                    #     grp = df.groupby(xcol)[ycol].sum().reset_index().sort_values(ycol, ascending=False).head(15)
                    #     fig.add_trace(go.Bar(
                    #         x=grp[xcol], y=grp[ycol],
                    #         marker=dict(color="#10b981", line=dict(width=0)),
                    #         text=grp[ycol].round(1), textposition="outside",
                    #         textfont=dict(color="#64748b", size=10),
                    #         hovertemplate="<b>%{x}</b><br>%{y:,}<extra></extra>",
                    #     ))
                    if ctype == "bar" and xcol and ycol and xcol in df and ycol in df:
                        grp = df.groupby(xcol)[ycol].sum().reset_index().sort_values(ycol, ascending=False).head(10)
                        fig.add_trace(go.Bar(
                            x=grp[xcol].astype(str).str.slice(0, 20), y=grp[ycol],
                            marker=dict(color="#10b981", line=dict(width=0)),
                            text=grp[ycol].round(1), textposition="outside",
                            textfont=dict(color="#64748b", size=10),
                            hovertemplate="<b>%{x}</b><br>%{y:,}<extra></extra>",
                        ))

                    elif ctype == "line" and xcol and ycol and xcol in df and ycol in df:
                        srt = df[[xcol, ycol]].dropna().sort_values(xcol)
                        fig.add_trace(go.Scatter(
                            x=srt[xcol], y=srt[ycol], mode="lines+markers",
                            line=dict(color="#059669", width=2.2, shape="spline", smoothing=0.6),
                            marker=dict(size=5, color="#059669", line=dict(width=0)),
                            fill="tozeroy", fillcolor="rgba(16,185,129,0.10)",
                            hovertemplate="%{x}<br><b>%{y:,}</b><extra></extra>",
                        ))

                    # elif ctype == "pie" and xcol and xcol in df:
                    #     counts = df[xcol].value_counts().head(10)
                    elif ctype == "pie" and xcol and xcol in df:
                        if df[xcol].nunique(dropna=True) > 12:
                            continue
                        counts = df[xcol].value_counts().head(10)
                        fig.add_trace(go.Pie(
                            labels=counts.index, values=counts.values, hole=0.55,
                            marker=dict(colors=PALETTE, line=dict(color="#ffffff", width=2)),
                            textinfo="percent",
                            hovertemplate="<b>%{label}</b><br>%{value:,} (%{percent})<extra></extra>",
                        ))

                    elif ctype == "scatter" and xcol and ycol and xcol in df and ycol in df:
                        fig.add_trace(go.Scatter(
                            x=df[xcol], y=df[ycol], mode="markers",
                            marker=dict(color="#0891b2", size=6, opacity=0.75, line=dict(width=0)),
                            hovertemplate="<b>%{x}</b>, <b>%{y}</b><extra></extra>",
                        ))

                    # elif ctype == "histogram" and xcol and xcol in df:
                    #     fig.add_trace(go.Histogram(
                    #         x=df[xcol], nbinsx=30,
                    #         marker=dict(color="#14b8a6", line=dict(width=0)),
                    #     ))
                    elif ctype == "histogram" and xcol and xcol in df:
                        if xcol not in numeric:
                            continue
                        fig.add_trace(go.Histogram(
                            x=df[xcol], nbinsx=30,
                            marker=dict(color="#14b8a6", line=dict(width=0)),
                        ))

                    elif ctype == "box" and ycol and ycol in df:
                        fig.add_trace(go.Box(
                            y=df[ycol], name=ycol, boxpoints="outliers",
                            marker=dict(color="#0891b2", size=4),
                            line=dict(width=1.4),
                            fillcolor="rgba(8,145,178,0.08)",
                        ))
                    else:
                        continue

                    # Set clear axis titles so viewers know what each axis means
                    x_label = xcol.replace("_", " ").title() if xcol else None
                    y_label = ycol.replace("_", " ").title() if ycol else None
                    if ctype in ("bar", "line", "scatter") and x_label:
                        fig.update_xaxes(title_text=x_label)
                    if ctype in ("bar", "line", "scatter") and y_label:
                        fig.update_yaxes(title_text=y_label)
                    if ctype == "histogram" and x_label:
                        fig.update_xaxes(title_text=x_label)
                        fig.update_yaxes(title_text="Count")
                    if ctype == "box" and y_label:
                        fig.update_yaxes(title_text=y_label)
                    if ctype in ("bar", "pie") and not ycol and x_label:
                        # count-based bar/pie (value_counts style) — y is always a count
                        fig.update_yaxes(title_text="Count")


                    _apply_theme(fig, title=title, height=320)
                    llm_charts[f"chart_{slot}"] = fig_to_html(fig)
                    llm_chart_meta.append({
                        "slot": slot, "title": title,
                        "description": desc, "config": cfg,
                        "source": chart_source,
                    })
                    logger.info("Generated chart slot %d: %s (%s)", slot, title, ctype)

                except Exception as ex:
                    logger.warning("Chart slot %d failed: %s", slot, ex)

        # ── Run/pipeline charts (postgres only) ───────────────────────────────
        if runs:
            fixed["run_status"]    = generate_run_status_chart(runs)
            fixed["metrics_trend"] = generate_metrics_trend_chart(metrics)

        all_charts = {**fixed, **llm_charts}
        generated  = [k for k, v in all_charts.items() if v]
        logger.info("generate_charts → %d total charts: %s", len(generated), generated)

        return {"charts": all_charts, "chart_meta": llm_chart_meta}

    except Exception as e:
        logger.error("generate_charts failed: %s", e, exc_info=True)
        return {"charts": {}, "chart_meta": [], "error": str(e)}


def _fallback_chart_configs(df, numeric, categ, datetime_cols):
    """Fallback chart configs when LLM fails."""
    configs = []
    slot = 1

    def score_col(col, preferred, blocked=()):
        lower = col.lower()
        score = 0
        for token, weight in preferred:
            if token in lower:
                score += weight
        for token, weight in blocked:
            if token in lower:
                score -= weight
        return score

    def pick_numeric(preferred):
        blocked = [("id", 8), ("age", 3), ("zip", 8), ("postal", 8), ("phone", 8)]
        ranked = sorted(numeric, key=lambda col: score_col(col, preferred, blocked), reverse=True)
        return ranked[0] if ranked else None

    def pick_category():
        preferred = [
            ("category", 9), ("segment", 8), ("region", 8), ("country", 7),
            ("state", 6), ("city", 5), ("channel", 7), ("status", 6),
            ("product", 5), ("department", 5), ("type", 4),
        ]
        blocked = [("id", 10), ("email", 10), ("phone", 10), ("name", 4), ("date", 8), ("time", 8)]
        usable = []
        for col in categ:
            unique = int(df[col].nunique(dropna=True)) if col in df else 0
            if 2 <= unique <= min(30, max(2, len(df) // 3)):
                usable.append((col, unique))
        ranked = sorted(
            usable,
            key=lambda item: (score_col(item[0], preferred, blocked), -item[1]),
            reverse=True,
        )
        return ranked[0][0] if ranked else None

    def pick_datetime():
        preferred = [("order", 5), ("sale", 4), ("created", 4), ("date", 3), ("time", 2)]
        return sorted(datetime_cols, key=lambda col: score_col(col, preferred), reverse=True)[0] if datetime_cols else None

    value_col = pick_numeric([
        ("revenue", 12), ("sales", 11), ("amount", 10), ("total", 9),
        ("price", 6), ("profit", 12), ("margin", 8), ("quantity", 5),
    ]) or (numeric[0] if numeric else None)
    secondary_col = pick_numeric([
        ("profit", 12), ("margin", 10), ("quantity", 9), ("discount", 7),
        ("price", 6), ("cost", 5),
    ])
    category_col = pick_category()
    date_col = pick_datetime()

    if date_col and value_col:
        configs.append({"slot": slot, "chart_type": "line",
                         "x_column": date_col, "y_column": value_col,
                         "title": f"{value_col} trend over time",
                         "description": f"Shows how {value_col} changes across {date_col}."})
        slot += 1
    if category_col and value_col:
        configs.append({"slot": slot, "chart_type": "bar",
                         "x_column": category_col, "y_column": value_col,
                         "title": f"{value_col} by {category_col}",
                         "description": f"Compares {value_col} across {category_col} to surface the strongest groups."})
        slot += 1
    if value_col and secondary_col and value_col != secondary_col:
        configs.append({"slot": slot, "chart_type": "scatter",
                         "x_column": secondary_col, "y_column": value_col,
                         "title": f"{value_col} vs {secondary_col}",
                         "description": f"Shows whether {secondary_col} is associated with changes in {value_col}."})
        slot += 1
    if value_col:
        configs.append({"slot": slot, "chart_type": "histogram",
                         "x_column": value_col, "y_column": None,
                         "title": f"Distribution of {value_col}",
                         "description": f"Reveals the spread, skew, and unusual values in {value_col}."})
    return configs[:4]


def node_llm_summary(state: PipelineState) -> dict:
    model = _resolve_model(state)          
    # model = _get_model()
    logger.info("═══ Node: llm_summary ═══  (calling %s)", model)
    prompt = f"""You are a Senior Data Analyst presenting insights to business stakeholders. 
    Write a clear, engaging, and easy-to-understand summary (minimum 150 words) based on the analysis results below. 
    Your goal is to explain what the data is saying and what actions the business should take, without confusing the reader with technical jargon.

    **Data Results:**
    Quality Score: {state['quality_result']}
    Null Analysis: {state['null_result']}
    Duplicates:    {state['dup_result']}
    Stats:         {state['stats_result']}
    Outliers:      {state['outlier_result']}
    Correlations:  {state['corr_result']}
    Health:        {state['health_result']}

    **Follow these guidelines strictly:**
    1. **Tell a Story, Don't Just List:** Do not write a robotic list like "1. Null Analysis, 2. Duplicates". Instead, weave the insights into a flowing narrative. 
    2. **Translate Jargon:** Explain technical things simply. For example, instead of saying "36 outliers found via IQR", say "We noticed 36 unusually high values in the 'total_value' column, which means..."
    3. **Be Specific:** Use exact column names and numbers, but explain what those numbers mean for the business (e.g., "A correlation of 0.99 between 'price_per_unit' and 'price_per_unit_sold' means these two columns are practically identical").
    4. **Structure the Summary:**
    - **The Big Picture:** Start with a 1-2 sentence overview of data health.
    - **What Stands Out:** Highlight the most important findings (missing data, unusual spikes/outliers, strong connections between numbers).
    - **Action Plan:** End with 3-5 prioritized recommendations. Frame them as business actions (e.g., "Clean up the X column because...", "Investigate Y to understand Z").
    """
#     prompt = f"""You are a senior data analyst. Write a detailed summary (min 150 words) based on these results.
# Use exact column names and numbers. End with top 3-5 prioritised recommendations.

# Quality Score: {state['quality_result']}
# Null Analysis: {state['null_result']}
# Duplicates:    {state['dup_result']}
# Stats:         {state['stats_result']}
# Outliers:      {state['outlier_result']}
# Correlations:  {state['corr_result']}
# Health:        {state['health_result']}

# Cover: overview, null issues, duplicates, stats insights, outliers, correlations, recommendations.
# DO NOT use generic statements. Be specific with column names and percentages."""

    logger.debug("LLM prompt (first 500 chars): %.500s", prompt)

    try:
        claude_summary = build_summary_with_claude(state)
        if claude_summary:
            return {"ai_summary": claude_summary}

        response = _get_llm().chat.completions.create(
            model    = model,
            messages = [{"role": "user", "content": prompt}],
            max_tokens = 1000,
        )
        summary = response.choices[0].message.content
        logger.info("llm_summary → received %d chars", len(summary) if summary else 0)
        logger.debug("LLM summary (first 500 chars): %.500s", summary)
        if hasattr(response, "usage") and response.usage:
            logger.debug("LLM usage → prompt=%s, completion=%s, total=%s",
                         getattr(response.usage, "prompt_tokens", "?"),
                         getattr(response.usage, "completion_tokens", "?"),
                         getattr(response.usage, "total_tokens", "?"))
        return {"ai_summary": summary}
    except Exception as e:
        logger.warning("llm_summary fallback used: %s", e)
        return {"ai_summary": _fallback_summary(state), "error": None}


def _fallback_summary(state: PipelineState) -> str:
    quality = state.get("quality_result", {}) or {}
    nulls = state.get("null_result", {}) or {}
    dups = state.get("dup_result", {}) or {}
    outliers = state.get("outlier_result", {}) or {}
    corr = state.get("corr_result", {}) or {}
    metrics = state.get("data", {}).get("metrics", []) or []

    score = quality.get("quality_score", 0)
    grade = quality.get("grade", "N/A")
    rows = nulls.get("total_rows", len(metrics))
    cols = nulls.get("total_columns", len(metrics[0]) if metrics else 0)
    critical = nulls.get("critical_cols", []) or []
    warning = nulls.get("warning_cols", []) or []
    duplicate_rows = dups.get("duplicate_rows", 0)
    duplicate_pct = dups.get("duplicate_pct", 0)
    outlier_cols = outliers.get("cols_with_outliers", []) or []
    strong_pairs = corr.get("strong_correlations", []) or []

    findings = []
    if critical:
        findings.append(f"{len(critical)} critical null column(s): {', '.join(map(str, critical[:5]))}")
    if warning:
        findings.append(f"{len(warning)} warning null column(s)")
    if duplicate_rows:
        findings.append(f"{duplicate_rows:,} duplicate row(s), about {duplicate_pct}% of the dataset")
    if outlier_cols:
        findings.append(f"outliers detected in {len(outlier_cols)} numeric column(s)")
    if strong_pairs:
        findings.append(f"{len(strong_pairs)} strong correlation pair(s)")

    finding_text = "; ".join(findings) if findings else "no major automated quality issues were detected"
    return (
        f"Automated analysis completed for {rows:,} rows across {cols} columns. "
        f"The current data quality score is {score}/100 with grade {grade}. "
        f"Key findings: {finding_text}. "
        "Review the generated trend, comparison, relationship, and distribution charts to confirm the main business signals. "
        "Before using this dashboard for decisions, validate warning null columns, duplicate rows, and any outlier-heavy measures."
    )


def node_build_report(state: PipelineState) -> dict:
    logger.info("═══ Node: build_report ═══")
    try:
        report = build_html_report(
            pipeline_name  = state.get("pipeline_name") or state.get("file_path") or "dataset",
            user_request   = state["user_request"],
            ai_summary     = state["ai_summary"],
            quality_result = state["quality_result"],
            null_analysis  = state["null_result"],
            dup_analysis   = state["dup_result"],
            stats_result   = state["stats_result"],
            outlier_result = state["outlier_result"],
            runs           = state["data"].get("runs", []),
            metrics        = state["data"].get("metrics", []),
            charts         = state["charts"],
        )
        logger.info("build_report → report_id=%s, url=%s",
                    report.get("report_id"), report.get("report_url"))
        return {"report": report}
    except Exception as e:
        logger.error("build_report failed: %s", e, exc_info=True)
        return {"report": {}, "error": str(e)}
