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

client = OpenAI(
    base_url = "https://openrouter.ai/api/v1",
    api_key  = os.getenv("OPENROUTER_API_KEY"),
)
MODEL = os.getenv("OPENROUTER_MODEL", "meta-llama/llama-3.3-70b-instruct:free")


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
    logger.info("═══ Node: generate_charts ═══")
    try:
        metrics = state["data"].get("metrics", [])
        runs    = state["data"].get("runs", [])
        score   = state["quality_result"].get("quality_score", 0)
        grade   = state["quality_result"].get("grade", "Unknown")
        charts  = {
            "gauge":         generate_quality_gauge(score, grade),
            "null_bar":      generate_null_bar_chart(state["null_result"])      if state["null_result"]    else "",
            "dup_pie":       generate_duplicate_pie(state["dup_result"])        if state["dup_result"]     else "",
            "stats_bar":     generate_stats_chart(state["stats_result"])        if state["stats_result"]   else "",
            "boxplot":       generate_outlier_boxplot(metrics),
            "correlation":   generate_correlation_heatmap(state["corr_result"]) if state["corr_result"]   else "",
            "run_status":    generate_run_status_chart(runs),
            "metrics_trend": generate_metrics_trend_chart(metrics),
        }
        generated = [k for k, v in charts.items() if v]
        logger.info("generate_charts → %d charts generated: %s", len(generated), generated)
        return {"charts": charts}
    except Exception as e:
        logger.error("generate_charts failed: %s", e, exc_info=True)
        return {"charts": {}, "error": str(e)}


def node_llm_summary(state: PipelineState) -> dict:
    logger.info("═══ Node: llm_summary ═══  (calling %s)", MODEL)
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
        response = client.chat.completions.create(
            model    = MODEL,
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
