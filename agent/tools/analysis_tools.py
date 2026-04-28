"""
analysis_tools.py
Runs pandas-based analysis on data fetched from Postgres.
Designed to work on any list-of-dicts (table rows).
"""

import pandas as pd
import numpy as np
from scipy import stats as scipy_stats

from agent.logger import get_logger

logger = get_logger(__name__)


def _to_df(data: list[dict]) -> pd.DataFrame:
    return pd.DataFrame(data) if data else pd.DataFrame()


# ─── 1. Null & Missing ────────────────────────────────────────────────────────

def check_nulls_and_missing(data: list[dict]) -> dict:
    """Returns null count, null %, and missing value summary per column."""
    logger.info("check_nulls_and_missing → %d records", len(data) if data else 0)
    df = _to_df(data)
    if df.empty:
        logger.error("check_nulls_and_missing: No data provided")
        return {"error": "No data provided"}

    total = len(df)
    null_counts  = df.isnull().sum().to_dict()
    null_pct     = (df.isnull().mean() * 100).round(2).to_dict()
    empty_str    = {col: int((df[col].astype(str).str.strip() == "").sum())
                    for col in df.select_dtypes(include="object").columns}

    critical = [col for col, pct in null_pct.items() if pct > 20]
    warning  = [col for col, pct in null_pct.items() if 5 < pct <= 20]

    logger.info("Null analysis complete → critical=%d, warning=%d, total_rows=%d",
                len(critical), len(warning), total)
    logger.debug("Critical columns: %s", critical)
    logger.debug("Warning columns: %s", warning)

    return {
        "total_rows":    total,
        "null_counts":   null_counts,
        "null_pct":      null_pct,
        "empty_strings": empty_str,
        "critical_cols": critical,   # >20% null
        "warning_cols":  warning,    # 5–20% null
    }


# ─── 2. Duplicates ────────────────────────────────────────────────────────────

def check_duplicates(data: list[dict]) -> dict:
    """Detects fully duplicate rows."""
    logger.info("check_duplicates → %d records", len(data) if data else 0)
    df = _to_df(data)
    if df.empty:
        logger.error("check_duplicates: No data provided")
        return {"error": "No data provided"}

    dup_count = int(df.duplicated().sum())
    dup_pct   = round(dup_count / len(df) * 100, 2)

    logger.info("Duplicate check complete → %d duplicates (%.2f%%)", dup_count, dup_pct)

    return {
        "total_rows":     len(df),
        "duplicate_rows": dup_count,
        "duplicate_pct":  dup_pct,
        "has_duplicates": dup_count > 0,
    }


# ─── 3. Descriptive Stats ─────────────────────────────────────────────────────

def get_descriptive_stats(data: list[dict]) -> dict:
    """Mean, median, std, min, max for numeric columns."""
    logger.info("get_descriptive_stats → %d records", len(data) if data else 0)
    df = _to_df(data)
    if df.empty:
        logger.error("get_descriptive_stats: No data provided")
        return {"error": "No data provided"}

    numeric_df = df.select_dtypes(include=[np.number])
    if numeric_df.empty:
        logger.info("get_descriptive_stats: No numeric columns found")
        return {"message": "No numeric columns found"}

    stats = {}
    for col in numeric_df.columns:
        series = numeric_df[col].dropna()
        stats[col] = {
            "mean":   round(float(series.mean()), 4),
            "median": round(float(series.median()), 4),
            "std":    round(float(series.std()), 4),
            "min":    round(float(series.min()), 4),
            "max":    round(float(series.max()), 4),
            "count":  int(series.count()),
        }

    logger.info("Descriptive stats complete → %d numeric columns", len(stats))
    logger.debug("Stats columns: %s", list(stats.keys()))
    return {"stats": stats}


# ─── 4. Outlier Detection ─────────────────────────────────────────────────────

def detect_outliers(data: list[dict]) -> dict:
    """IQR + Z-score outlier detection on numeric columns."""
    logger.info("detect_outliers → %d records", len(data) if data else 0)
    df = _to_df(data)
    if df.empty:
        logger.error("detect_outliers: No data provided")
        return {"error": "No data provided"}

    numeric_df = df.select_dtypes(include=[np.number])
    results = {}

    for col in numeric_df.columns:
        series = numeric_df[col].dropna()
        if len(series) < 4:
            continue

        # IQR method
        Q1, Q3  = series.quantile(0.25), series.quantile(0.75)
        IQR     = Q3 - Q1
        iqr_out = series[(series < Q1 - 1.5 * IQR) | (series > Q3 + 1.5 * IQR)]

        # Z-score method
        z_scores = np.abs(scipy_stats.zscore(series))
        z_out    = series[z_scores > 3]

        results[col] = {
            "iqr_outlier_count":     int(len(iqr_out)),
            "zscore_outlier_count":  int(len(z_out)),
            "iqr_bounds":            {"lower": round(float(Q1 - 1.5 * IQR), 4),
                                      "upper": round(float(Q3 + 1.5 * IQR), 4)},
            "outlier_values_sample": iqr_out.head(5).tolist(),
        }

    logger.info("Outlier detection complete → %d columns with outliers", len(results))
    logger.debug("Outlier columns: %s", list(results.keys()))
    return {"outliers": results}


# ─── 5. Correlation Matrix ────────────────────────────────────────────────────

def get_correlation_matrix(data: list[dict]) -> dict:
    """Pearson correlation matrix for numeric columns."""
    logger.info("get_correlation_matrix → %d records", len(data) if data else 0)
    df = _to_df(data)
    if df.empty:
        logger.error("get_correlation_matrix: No data provided")
        return {"error": "No data provided"}

    numeric_df = df.select_dtypes(include=[np.number])
    if numeric_df.shape[1] < 2:
        logger.info("get_correlation_matrix: Need at least 2 numeric columns")
        return {"message": "Need at least 2 numeric columns for correlation"}

    corr = numeric_df.corr().round(3)
    logger.info("Correlation matrix complete → %dx%d", corr.shape[0], corr.shape[1])
    return {"correlation_matrix": corr.to_dict()}


# ─── 6. Data Type Issues ──────────────────────────────────────────────────────

def check_data_type_issues(data: list[dict]) -> dict:
    """Detects columns that should be numeric but contain strings, etc."""
    logger.info("check_data_type_issues → %d records", len(data) if data else 0)
    df = _to_df(data)
    if df.empty:
        logger.error("check_data_type_issues: No data provided")
        return {"error": "No data provided"}

    issues = {}
    for col in df.select_dtypes(include="object").columns:
        # Try converting to numeric — if many succeed, the col is mixed type
        converted = pd.to_numeric(df[col], errors="coerce")
        numeric_count = converted.notna().sum()
        total_non_null = df[col].notna().sum()

        if total_non_null > 0 and numeric_count / total_non_null > 0.5:
            issues[col] = {
                "issue":          "mixed_type",
                "numeric_values": int(numeric_count),
                "total_values":   int(total_non_null),
                "suggestion":     f"Column '{col}' looks numeric but stored as text",
            }

    logger.info("Data type check complete → %d issues found", len(issues))
    logger.debug("Type-issue columns: %s", list(issues.keys()))
    return {"type_issues": issues}


# ─── 7. Pipeline-Specific Analysis ────────────────────────────────────────────

def analyze_pipeline_health(runs: list[dict], metrics: list[dict]) -> dict:
    """
    Specific to pipeline_runs + pipeline_metrics tables.
    Returns success rate, avg duration, failure patterns.
    """
    logger.info("analyze_pipeline_health → runs=%d, metrics=%d",
                len(runs) if runs else 0, len(metrics) if metrics else 0)
    runs_df    = _to_df(runs)
    metrics_df = _to_df(metrics)

    result = {}

    if not runs_df.empty and "status" in runs_df.columns:
        status_counts  = runs_df["status"].value_counts().to_dict()
        total          = len(runs_df)
        success_count  = status_counts.get("success", 0)
        result["runs"] = {
            "total":        total,
            "status_breakdown": status_counts,
            "success_rate": round(success_count / total * 100, 2) if total else 0,
        }
        logger.info("Pipeline runs health → total=%d, success_rate=%.2f%%",
                    total, result["runs"]["success_rate"])

    if not metrics_df.empty:
        num_cols = ["rows_inserted", "rows_skipped", "rows_failed",
                    "duration_sec", "match_pct"]
        agg = {}
        for col in num_cols:
            if col in metrics_df.columns:
                series = pd.to_numeric(metrics_df[col], errors="coerce").dropna()
                if not series.empty:
                    agg[col] = {
                        "total": round(float(series.sum()), 2),
                        "avg":   round(float(series.mean()), 2),
                        "max":   round(float(series.max()), 2),
                    }
        result["metrics_summary"] = agg
        logger.debug("Metrics summary: %s", agg)

    return result


# ─── 8. Master Quality Score ──────────────────────────────────────────────────

def calculate_quality_score(null_result: dict, dup_result: dict,
                             type_result: dict, outlier_result: dict) -> dict:
    """
    Combines all analysis results into a 0–100 quality score.
    Deducts points for critical nulls, duplicates, type issues, outliers.
    """
    logger.info("Calculating quality score …")
    score = 100

    # Null penalty: up to -30
    critical_cols = len(null_result.get("critical_cols", []))
    warning_cols  = len(null_result.get("warning_cols", []))
    score -= min(30, critical_cols * 10 + warning_cols * 3)

    # Duplicate penalty: up to -20
    dup_pct = dup_result.get("duplicate_pct", 0)
    score -= min(20, dup_pct * 2)

    # Type issue penalty: up to -20
    type_issues = len(type_result.get("type_issues", {}))
    score -= min(20, type_issues * 5)

    # Outlier penalty: up to -15
    outlier_cols = len(outlier_result.get("outliers", {}))
    score -= min(15, outlier_cols * 3)

    score = max(0, round(score, 1))

    if score >= 80:
        grade = "Good"
    elif score >= 60:
        grade = "Fair"
    elif score >= 40:
        grade = "Poor"
    else:
        grade = "Critical"

    logger.info("Quality score → %.1f (%s)  [null_penalty: critical=%d warning=%d, "
                "dup_pct=%.2f, type_issues=%d, outlier_cols=%d]",
                score, grade, critical_cols, warning_cols, dup_pct,
                type_issues, outlier_cols)

    return {"quality_score": score, "grade": grade}
