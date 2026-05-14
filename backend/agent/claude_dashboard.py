import asyncio
import json
import os
import re
from typing import Any, Optional

import pandas as pd

from agent.logger import get_logger

logger = get_logger(__name__)


CHART_TYPES = ["bar", "line", "pie", "scatter", "histogram", "box"]

DASHBOARD_DESIGNER_SYSTEM_PROMPT = """You are SparkBrains' senior dashboard designer and data analyst.

Your job is to choose the dashboard that a busy operator, analyst, or founder would actually use.

Decision principles:
- Start from the user's intent and dataset grain. Infer whether the dataset is operational, sales, finance, product, marketing, quality, or pipeline telemetry.
- Prefer charts that answer business questions: trend, comparison, composition, distribution, relationship, and risk.
- Make every chart earn its space. Avoid generic charts when a more useful view is possible.
- Pair insight with action: titles should say what the chart is about, descriptions should explain why it matters.
- Respect the available data. Never invent columns, metrics, dates, or categories.
- Use data quality charts only when quality issues are meaningful enough to affect trust or operations.
- Avoid pie charts unless the category count is small and composition is genuinely useful.
- Avoid four charts that all show the same measure. Build a balanced dashboard.

Output only the structured data requested by the schema."""

SUMMARY_SYSTEM_PROMPT = """You are SparkBrains' senior dashboard narrator.

Write like a sharp analyst preparing a dashboard handoff:
- concise, specific, and business-friendly
- grounded only in the provided analysis
- mention risks when data quality can affect decisions
- end with practical recommendations

Do not invent facts. Do not mention implementation details."""

DASHBOARD_PLAN_SCHEMA = {
    "type": "object",
    "properties": {
        "dashboard_title": {"type": "string"},
        "summary": {"type": "string"},
        "charts": {
            "type": "array",
            "minItems": 4,
            "maxItems": 4,
            "items": {
                "type": "object",
                "properties": {
                    "slot": {"type": "integer", "minimum": 1, "maximum": 4},
                    "chart_type": {"type": "string", "enum": CHART_TYPES},
                    "x_column": {"type": ["string", "null"]},
                    "y_column": {"type": ["string", "null"]},
                    "title": {"type": "string"},
                    "description": {"type": "string"},
                },
                "required": ["slot", "chart_type", "x_column", "y_column", "title", "description"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["dashboard_title", "summary", "charts"],
    "additionalProperties": False,
}


SUMMARY_SCHEMA = {
    "type": "object",
    "properties": {
        "summary": {"type": "string"},
    },
    "required": ["summary"],
    "additionalProperties": False,
}


def claude_agent_enabled() -> bool:
    value = os.getenv("CLAUDE_AGENT_SDK_ENABLED", "true").strip().lower()
    return value not in {"0", "false", "no", "off"}


def _run_async(coro):
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)
    raise RuntimeError("Claude Agent SDK sync wrapper cannot run inside an active event loop")


async def _query_structured(
    prompt: str,
    schema: dict[str, Any],
    system_prompt: str,
) -> Optional[dict[str, Any]]:
    if not claude_agent_enabled():
        return None

    try:
        from claude_agent_sdk import ClaudeAgentOptions, ResultMessage, query
    except Exception as exc:
        logger.info("Claude Agent SDK unavailable: %s", exc)
        return None

    stderr_lines: list[str] = []

    def _capture_stderr(line: str) -> None:
        if line:
            stderr_lines.append(line[-1000:])

    options = ClaudeAgentOptions(
        model=os.getenv("CLAUDE_AGENT_MODEL", "sonnet"),
        fallback_model=os.getenv("CLAUDE_AGENT_FALLBACK_MODEL", "haiku"),
        system_prompt=system_prompt,
        max_turns=1,
        max_budget_usd=float(os.getenv("CLAUDE_AGENT_MAX_BUDGET_USD", "0.15")),
        permission_mode="dontAsk",
        tools=[],
        allowed_tools=[],
        disallowed_tools=[
            "Bash",
            "Edit",
            "Write",
            "Read",
            "Glob",
            "Grep",
            "NotebookEdit",
            "WebFetch",
            "WebSearch",
            "TodoWrite",
        ],
        setting_sources=[],
        stderr=_capture_stderr,
        env={
            key: value
            for key, value in {
                "ANTHROPIC_API_KEY": os.getenv("ANTHROPIC_API_KEY"),
                "CLAUDE_CODE_OAUTH_TOKEN": os.getenv("CLAUDE_CODE_OAUTH_TOKEN"),
            }.items()
            if value
        },
        output_format={"type": "json_schema", "schema": schema},
    )

    try:
        async for message in query(prompt=prompt, options=options):
            if isinstance(message, ResultMessage):
                structured = getattr(message, "structured_output", None)
                if message.subtype == "success" and structured:
                    return structured
                result = getattr(message, "result", None)
                parsed = _parse_structured_result(result)
                if message.subtype == "success" and parsed:
                    return parsed
                logger.warning(
                    "Claude Agent SDK returned subtype=%s, has_structured=%s, result_len=%s, result_preview=%r",
                    getattr(message, "subtype", None),
                    bool(structured),
                    len(str(result or "")),
                    str(result or "")[:160],
                )
    except Exception as exc:
        stderr_tail = "\n".join(stderr_lines[-3:])
        logger.warning("Claude Agent SDK query failed: %s%s", exc, f"\nSTDERR: {stderr_tail}" if stderr_tail else "")
    return None


def _parse_structured_result(result: Any) -> Optional[dict[str, Any]]:
    if isinstance(result, dict):
        return result
    if not isinstance(result, str) or not result.strip():
        return None

    text = result.strip()
    candidates = [text]
    fenced = re.findall(r"```(?:json)?\s*(.*?)```", text, flags=re.DOTALL | re.IGNORECASE)
    candidates.extend(item.strip() for item in fenced)

    first = text.find("{")
    last = text.rfind("}")
    if 0 <= first < last:
        candidates.append(text[first:last + 1])

    for candidate in candidates:
        try:
            parsed = json.loads(candidate)
            if isinstance(parsed, dict):
                return parsed
        except Exception:
            continue
    return None


def _dataset_context(state: dict[str, Any]) -> dict[str, Any]:
    metrics = state.get("data", {}).get("metrics", []) or []
    df = pd.DataFrame(metrics)
    if df.empty:
        return {
            "columns": [],
            "numeric_columns": [],
            "categorical_columns": [],
            "datetime_columns": [],
            "row_count": 0,
            "sample": [],
        }

    numeric = df.select_dtypes(include="number").columns.tolist()
    categorical = df.select_dtypes(include="object").columns.tolist()
    datetime_cols = [c for c in df.columns if "date" in c.lower() or "time" in c.lower()]

    return {
        "columns": df.columns.tolist(),
        "numeric_columns": numeric,
        "categorical_columns": categorical,
        "datetime_columns": datetime_cols,
        "row_count": len(df),
        "sample": df.head(5).to_dict(orient="records"),
    }


def build_dashboard_plan_with_claude(state: dict[str, Any]) -> Optional[dict[str, Any]]:
    context = _dataset_context(state)
    if not context["columns"]:
        return None

    prompt = f"""Create the best dashboard plan for this dataset.

User request:
{state.get("user_request", "Create the best dashboard for this dataset.")}

Dataset context:
{json.dumps(context, default=str)}

Analysis context:
Quality: {json.dumps(state.get("quality_result", {}), default=str)}
Nulls: {json.dumps(state.get("null_result", {}), default=str)}
Duplicates: {json.dumps(state.get("dup_result", {}), default=str)}
Stats: {json.dumps(state.get("stats_result", {}).get("stats", {}), default=str)}
Outliers: {json.dumps(state.get("outlier_result", {}), default=str)}
Correlations: {json.dumps(state.get("corr_result", {}).get("strong_correlations", []), default=str)}

Rules:
- Use only columns that exist in Dataset context.
- Return exactly 4 charts.
- Choose the 4 charts as a complete dashboard, not as isolated visuals.
- If a date/time column exists and a useful numeric column exists, strongly prefer one trend chart.
- If strong correlations exist and the fields are meaningful, include a scatter chart for the strongest useful pair.
- Include one distribution or outlier view when numeric spread or anomalies matter.
- Include one category comparison when categorical and numeric fields support it.
- Pie charts should only use a categorical column with a small number of groups.
- Titles should be polished and specific.
- Descriptions should explain the decision value in one sentence.
"""

    result = _run_async(_query_structured(
        prompt,
        DASHBOARD_PLAN_SCHEMA,
        DASHBOARD_DESIGNER_SYSTEM_PROMPT,
    ))
    if result and result.get("charts"):
        logger.info("Claude Agent SDK generated dashboard plan with %d charts", len(result["charts"]))
        return result
    return None


def build_summary_with_claude(state: dict[str, Any]) -> Optional[str]:
    context = _dataset_context(state)
    prompt = f"""Write a polished dashboard analyst summary for this dataset.

Keep it specific, business-friendly, and actionable. Mention important quality problems, useful patterns, and 3-5 prioritized recommendations.

Dataset context:
{json.dumps(context, default=str)}

Analysis context:
Quality: {json.dumps(state.get("quality_result", {}), default=str)}
Nulls: {json.dumps(state.get("null_result", {}), default=str)}
Duplicates: {json.dumps(state.get("dup_result", {}), default=str)}
Stats: {json.dumps(state.get("stats_result", {}), default=str)}
Outliers: {json.dumps(state.get("outlier_result", {}), default=str)}
Correlations: {json.dumps(state.get("corr_result", {}), default=str)}
Health: {json.dumps(state.get("health_result", {}), default=str)}
"""

    result = _run_async(_query_structured(
        prompt,
        SUMMARY_SCHEMA,
        SUMMARY_SYSTEM_PROMPT,
    ))
    summary = (result or {}).get("summary")
    if summary:
        logger.info("Claude Agent SDK generated dashboard summary")
        return summary
    return None
