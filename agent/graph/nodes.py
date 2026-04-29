import os
from openai import OpenAI
from agent.graph.state import PipelineState
from agent.logger import get_logger
from agent.tools.data_tools     import (fetch_pipeline_runs, fetch_pipeline_metrics,
                                         fetch_data_by_source, fetch_full_pipeline_summary)
from agent.tools.analysis_tools import (check_nulls_and_missing, check_duplicates,
                                         get_descriptive_stats, detect_outliers,
                                         get_correlation_matrix, check_data_type_issues,
                                         analyze_pipeline_health, calculate_quality_score)
from agent.tools.chart_tools    import (generate_null_bar_chart, generate_duplicate_pie,
                                         generate_stats_chart, generate_outlier_boxplot,
                                         generate_correlation_heatmap, generate_run_status_chart,
                                         generate_metrics_trend_chart, generate_quality_gauge)
from agent.tools.report_tools   import build_html_report

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


def node_fetch_data(state: PipelineState) -> dict:
    logger.info("═══ Node: fetch_data ═══  source=%s, pipeline=%s",
                state["source_type"], state.get("pipeline_name"))
    try:
        if state["source_type"] == "postgres":
            data = fetch_full_pipeline_summary(state.get("pipeline_name"))
        else:
            raw  = fetch_data_by_source(state["source_type"],
                                        file_path     = state.get("file_path"),
                                        sheet_url     = state.get("sheet_url"),
                                        pipeline_name = state.get("pipeline_name"))
            data = {"metrics": raw, "runs": []}
        logger.info("fetch_data → metrics=%d, runs=%d",
                    len(data.get("metrics", [])), len(data.get("runs", [])))
        return {"data": data}
    except Exception as e:
        logger.error("fetch_data failed: %s", e, exc_info=True)
        return {"data": {}, "error": str(e)}


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

            try:
                resp = _get_llm().chat.completions.create(
                    model    = _get_model(),
                    messages = [{"role": "user", "content": decision_prompt}],
                    max_tokens = 600,
                )
                raw = resp.choices[0].message.content.strip()
                raw = raw.replace("```json","").replace("```","").strip()
                chart_configs = json.loads(raw)
                logger.info("LLM decided %d charts", len(chart_configs))
            except Exception as ex:
                logger.warning("LLM chart decision failed, using fallback: %s", ex)
                # fallback configs
                chart_configs = _fallback_chart_configs(numeric, categ, datetime_cols)

            # ── Generate each LLM-decided chart ──────────────────────────────
            def fig_to_b64(fig):
                return base64.b64encode(
                    fig.to_image(format="png", width=900, height=420, scale=1.5)
                ).decode()

            layout_base = dict(
                plot_bgcolor="#0f172a", paper_bgcolor="#0f172a",
                font=dict(color="#e2e8f0"), margin=dict(l=40,r=20,t=50,b=40)
            )

            for cfg in chart_configs:
                slot   = cfg.get("slot", 1)
                ctype  = cfg.get("chart_type", "bar")
                xcol   = cfg.get("x_column")
                ycol   = cfg.get("y_column")
                title  = cfg.get("title", f"Chart {slot}")
                desc   = cfg.get("description", "")
                fig    = go.Figure()

                try:
                    if ctype == "bar" and xcol and ycol and xcol in df and ycol in df:
                        grp = df.groupby(xcol)[ycol].sum().reset_index().sort_values(ycol, ascending=False).head(15)
                        fig.add_trace(go.Bar(x=grp[xcol], y=grp[ycol], marker_color="#3b82f6",
                                             text=grp[ycol].round(1), textposition="outside"))

                    elif ctype == "line" and xcol and ycol and xcol in df and ycol in df:
                        srt = df[[xcol, ycol]].dropna().sort_values(xcol)
                        fig.add_trace(go.Scatter(x=srt[xcol], y=srt[ycol],
                                                  mode="lines+markers", line=dict(color="#22c55e", width=2)))

                    elif ctype == "pie" and xcol and xcol in df:
                        counts = df[xcol].value_counts().head(10)
                        fig.add_trace(go.Pie(labels=counts.index, values=counts.values,
                                              hole=0.35, marker=dict(colors=["#3b82f6","#22c55e","#f59e0b","#ef4444","#8b5cf6","#06b6d4","#ec4899","#84cc16","#f97316","#6366f1"])))

                    elif ctype == "scatter" and xcol and ycol and xcol in df and ycol in df:
                        fig.add_trace(go.Scatter(x=df[xcol], y=df[ycol], mode="markers",
                                                  marker=dict(color="#8b5cf6", size=5, opacity=0.6)))

                    elif ctype == "histogram" and xcol and xcol in df:
                        fig.add_trace(go.Histogram(x=df[xcol], marker_color="#f59e0b", nbinsx=30))

                    elif ctype == "box" and ycol and ycol in df:
                        fig.add_trace(go.Box(y=df[ycol], name=ycol, boxpoints="outliers",
                                              marker_color="#06b6d4"))
                    else:
                        continue

                    fig.update_layout(title=title, **layout_base)
                    llm_charts[f"chart_{slot}"] = fig_to_b64(fig)
                    llm_chart_meta.append({
                        "slot": slot, "title": title,
                        "description": desc, "config": cfg
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


def _fallback_chart_configs(numeric, categ, datetime_cols):
    """Fallback chart configs when LLM fails."""
    configs = []
    slot = 1
    if datetime_cols and numeric:
        configs.append({"slot": slot, "chart_type": "line",
                         "x_column": datetime_cols[0], "y_column": numeric[0],
                         "title": f"{numeric[0]} over time",
                         "description": f"Trend of {numeric[0]} over time"})
        slot += 1
    if categ and numeric:
        configs.append({"slot": slot, "chart_type": "bar",
                         "x_column": categ[0], "y_column": numeric[0],
                         "title": f"{numeric[0]} by {categ[0]}",
                         "description": f"Comparison of {numeric[0]} across {categ[0]}"})
        slot += 1
    if len(numeric) >= 2:
        configs.append({"slot": slot, "chart_type": "scatter",
                         "x_column": numeric[0], "y_column": numeric[1],
                         "title": f"{numeric[0]} vs {numeric[1]}",
                         "description": f"Relationship between {numeric[0]} and {numeric[1]}"})
        slot += 1
    if numeric:
        configs.append({"slot": slot, "chart_type": "histogram",
                         "x_column": numeric[0], "y_column": None,
                         "title": f"Distribution of {numeric[0]}",
                         "description": f"How {numeric[0]} values are distributed"})
    return configs[:4]


def node_llm_summary(state: PipelineState) -> dict:
    model = _get_model()
    logger.info("═══ Node: llm_summary ═══  (calling %s)", model)
    prompt = f"""You are a senior data analyst. Write a detailed summary (min 150 words) based on these results.
Use exact column names and numbers. End with top 3-5 prioritised recommendations.

Quality Score: {state['quality_result']}
Null Analysis: {state['null_result']}
Duplicates:    {state['dup_result']}
Stats:         {state['stats_result']}
Outliers:      {state['outlier_result']}
Correlations:  {state['corr_result']}
Health:        {state['health_result']}

Cover: overview, null issues, duplicates, stats insights, outliers, correlations, recommendations.
DO NOT use generic statements. Be specific with column names and percentages."""

    logger.debug("LLM prompt (first 500 chars): %.500s", prompt)

    try:
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
        logger.error("llm_summary failed: %s", e, exc_info=True)
        return {"ai_summary": f"Error generating summary: {e}", "error": str(e)}


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
