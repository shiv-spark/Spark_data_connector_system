from agent.graph.state import PipelineState
from agent.logger import get_logger

logger = get_logger(__name__)


def edge_should_run_correlation(state: PipelineState) -> str:
    """Skip correlation if fewer than 2 numeric columns."""
    stats = state.get("stats_result", {}).get("stats", {})
    if len(stats) >= 2:
        logger.info("Edge: correlation → yes (%d numeric columns)", len(stats))
        return "correlation"
    logger.info("Edge: correlation → skip (only %d numeric column(s))", len(stats))
    return "health_or_score"


def edge_health_or_score(state: PipelineState) -> str:
    """Run health check only for postgres, otherwise just compute quality score."""
    if state["source_type"] == "postgres":
        logger.info("Edge: source=postgres → health_check")
        return "health_check"
    logger.info("Edge: source=%s → quality_score_only", state["source_type"])
    return "quality_score_only"
