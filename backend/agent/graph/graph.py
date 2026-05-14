from langgraph.graph import StateGraph, END
from agent.graph.state import PipelineState
from agent.graph.nodes import (node_fetch_data, node_null_analysis,
                                node_duplicate_check, node_stats,
                                node_outliers, node_correlation,
                                node_health_check, node_quality_score_only,
                                node_generate_charts, node_llm_summary,
                                node_build_report)
from agent.graph.edges import edge_health_or_score


def edge_after_outliers(state: PipelineState) -> str:
    stats = state.get("stats_result", {}).get("stats", {})
    if len(stats) >= 2:
        return "correlation"
    return edge_health_or_score(state)   # skip correlation, go straight to health/score


def build_graph():
    g = StateGraph(PipelineState)

    g.add_node("fetch_data",         node_fetch_data)
    g.add_node("null_analysis",      node_null_analysis)
    g.add_node("duplicate_check",    node_duplicate_check)
    g.add_node("stats",              node_stats)
    g.add_node("outliers",           node_outliers)
    g.add_node("correlation",        node_correlation)
    g.add_node("health_check",       node_health_check)
    g.add_node("quality_score_only", node_quality_score_only)
    g.add_node("generate_charts",    node_generate_charts)
    g.add_node("llm_summary",        node_llm_summary)
    g.add_node("build_report",       node_build_report)

    g.set_entry_point("fetch_data")
    g.add_edge("fetch_data",      "null_analysis")
    g.add_edge("null_analysis",   "duplicate_check")
    g.add_edge("duplicate_check", "stats")
    g.add_edge("stats",           "outliers")

    g.add_conditional_edges("outliers", edge_after_outliers, {
        "correlation":        "correlation",
        "health_check":       "health_check",
        "quality_score_only": "quality_score_only",
    })

    g.add_conditional_edges("correlation", edge_health_or_score, {
        "health_check":       "health_check",
        "quality_score_only": "quality_score_only",
    })

    g.add_edge("health_check",       "generate_charts")
    g.add_edge("quality_score_only", "generate_charts")
    g.add_edge("generate_charts",    "llm_summary")
    g.add_edge("llm_summary",        "build_report")
    g.add_edge("build_report",        END)

    return g.compile()


pipeline_graph = build_graph()
