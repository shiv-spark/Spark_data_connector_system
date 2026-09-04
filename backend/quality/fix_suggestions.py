"""
Fix Suggestions
───────────────
Turns a failed/errored quality-check result into a short, actionable
"how to fix this" message, so a blocked pipeline tells the user what to do
next instead of just that something failed.

Two tiers:
  1. suggest_fix() — deterministic, rule-based, offline. Runs on every
     non-PASS result automatically (dataframe_checks.py and quality/router.py
     both call this), so a suggestion is ALWAYS present, even with no LLM
     key configured.
  2. quality/router.py's POST /quality/ai-fix — optional, LLM-powered,
     for when the canned suggestion isn't specific enough. Takes the same
     result dicts this module already annotated and asks the model to
     reason about the actual column/table/values involved.

Matching is done on the `check_name` prefix, since table-level check names
carry a bracketed suffix with the specific column/rule (e.g.
"BUSINESS_RULE[amount]", "OUTLIER_CHECK[price]") — matching by prefix keeps
one rule per check family instead of one per column.
"""

from typing import Any, Dict


def _prefix(check_name: str) -> str:
    """'OUTLIER_CHECK[price]' -> 'OUTLIER_CHECK'; 'NULL_PERCENTAGE' -> 'NULL_PERCENTAGE'."""
    return check_name.split("[", 1)[0].strip()


# ── Dataframe-level checks (quality/dataframe_checks.py, pre-ingest) ──────
# Keys match the check_name PREFIX actually emitted by dataframe_checks.py
# (before any bracketed "[column]" suffix — see _prefix()).
_DATAFRAME_SUGGESTIONS = {
    "EMPTY_DATAFRAME_CHECK":
        "The source returned zero rows. Check the query/filter/date-range on the source "
        "side (e.g. an overly narrow WHERE clause, a wrong sheet tab, an empty API page) "
        "before re-running — there's nothing here to fix downstream.",
    "REQUIRED_COLUMNS_CHECK":
        "One or more required columns are missing from the incoming data. Confirm the "
        "column names in the source match exactly (case and spelling), or update the "
        "required-columns list in the quality config if the source schema legitimately "
        "changed.",
    "NULL_PCT_CHECK":
        "Too many nulls in this column. Either backfill/impute the missing values at the "
        "source, add a default value in the source query (e.g. COALESCE), or raise the "
        "allowed null-percentage threshold in the quality config if nulls are expected.",
    "DUPLICATE_ROWS_CHECK":
        "Duplicate rows detected. De-duplicate at the source query (e.g. add DISTINCT or "
        "GROUP BY), or narrow the duplicate-check column set if some repetition across "
        "those columns is actually expected.",
    "DTYPE_CHECK":
        "A column's values don't match the expected data type. Clean the offending values "
        "at the source (e.g. strip currency symbols/commas from a numeric column, fix "
        "malformed dates) or adjust the expected_dtypes mapping if the real type is "
        "different from what was configured.",
    "RANGE_CHECK":
        "Values fall outside the configured min/max range. Check for a unit mismatch "
        "(e.g. cents vs. dollars), bad rows at the source, or widen the range in the "
        "quality config if the current values are legitimately outside it.",
    "PATTERN_CHECK":
        "Some values don't match the required format (regex). Look for the specific rows "
        "that failed and check for typos, extra whitespace, or a source system that "
        "changed its format, or loosen the pattern if the format has legitimately changed.",
    "ENUM_CHECK":
        "Values outside the allowed set were found. Add the new value to the allowed list "
        "if it's legitimate (e.g. a new status/category was introduced upstream), or fix "
        "the source data if it's a typo or an unexpected value.",
}

# ── Table-level checks (quality/checks.py, run via /quality/run and the
#    post-load ingest gate) ────────────────────────────────────────────────
_TABLE_SUGGESTIONS = {
    "ROW_COUNT_CHECK":
        "Row count is below the expected minimum. Check whether the source query/filter "
        "changed, whether an earlier step in the pipeline silently dropped rows, or lower "
        "the expected_min_rows threshold if a smaller load is now normal.",
    "NULL_CHECK":
        "Nulls found in a column that's expected to always be populated. Fix the null "
        "values at the source, add a default/COALESCE in the load query, or remove this "
        "column from null_columns if nulls are actually acceptable here.",
    "DUPLICATE_CHECK":
        "Duplicate rows found on the primary key. This usually means the load ran twice, "
        "an upsert/merge key is missing, or the source itself has duplicate records — "
        "de-duplicate at the source or switch the pipeline to an incremental/upsert load "
        "keyed on this column.",
    "DUPLICATE_CHECK[BUSINESS_KEY]":
        "Duplicate rows found on the business key (e.g. same email/order twice). Check for "
        "a missing de-dup step in the pipeline, or confirm this key really should be "
        "unique — some domains (e.g. multiple orders per email) legitimately allow repeats.",
    "FRESHNESS_CHECK":
        "The most recent row is older than the freshness threshold. Check whether the "
        "upstream pipeline/schedule actually ran, whether the source has new data at all, "
        "or increase the freshness_threshold_hours if the real update cadence is slower.",
    "BUSINESS_RULE":
        "Rows violate a configured business rule. Inspect the failing rows against the "
        "rule's condition — the rule may be catching genuinely bad data (fix at the "
        "source), or the condition itself may need adjusting if business logic changed.",
    "REFERENTIAL_INTEGRITY":
        "Rows reference a parent record that doesn't exist (orphaned foreign key). Load "
        "the parent table first / in the same run, backfill the missing parent rows, or "
        "check for a hard-delete on the parent side that didn't cascade.",
    "DATA_TYPE":
        "A column's actual values don't match its declared type. Check the source for "
        "malformed values (e.g. text in a numeric column), or update the expected type in "
        "the quality config if the column's real type has changed.",
    "RANGE_CHECK":
        "Values fall outside the configured min/max. Check for unit mismatches or bad "
        "source rows, or widen the configured range if the new values are legitimate.",
    "OUTLIER_CHECK":
        "Statistical outliers detected (outside the IQR bounds). These aren't necessarily "
        "wrong — review the flagged rows for data-entry errors or a scaling/unit bug, or "
        "if they're legitimate extreme values, no fix is needed and this can be treated "
        "as informational.",
    "SCHEMA_VALIDATION[MANUAL]":
        "The table's actual schema doesn't match the expected column list/types. Update "
        "the expected_columns config if the schema change was intentional, or investigate "
        "why the source/loader produced an unexpected column.",
    "SCHEMA_VALIDATION[BASELINE]":
        "The table's schema has drifted from its captured baseline. If this change is "
        "intentional (e.g. a planned migration), reset the baseline via "
        "POST /quality/schema-baseline/reset; otherwise investigate the upstream change "
        "that added/removed/retyped a column.",
    "CONSISTENCY_CHECK":
        "Two tables/aggregates that should match are out of tolerance. Check for a partial "
        "load on one side, a timing difference between when each table was refreshed, or "
        "widen the tolerance if some drift is expected.",
}


def suggest_fix(check_name: str, result: Dict[str, Any], source: str = "table") -> str:
    """
    Return a short actionable suggestion for a non-PASS result.

    `source` is "dataframe" for quality/dataframe_checks.py results (pre-ingest)
    or "table" for quality/checks.py results (post-load / ad-hoc /quality/run).
    Falls back to a generic message for any check name not in the map above,
    so this never returns None/empty for a FAIL or ERROR result.
    """
    status = result.get("status")
    if status == "PASS":
        return ""

    if status == "ERROR":
        return (
            "This check couldn't run — usually a config problem (a column/table name "
            "that doesn't exist, or a rule that isn't valid SQL) rather than a data "
            "problem. See the message above for the exact error, then fix the check's "
            "configuration and re-run."
        )

    message = (result.get("message") or "")
    if "not found in dataframe" in message or "not found" in message and "olumn" in message:
        return (
            "The configured column doesn't exist in the incoming data. Check for a typo "
            "in the quality-check config, or a source schema change (renamed/removed "
            "column) that needs to be reflected in the pipeline's column mapping."
        )

    table = _DATAFRAME_SUGGESTIONS if source == "dataframe" else _TABLE_SUGGESTIONS
    key = check_name if check_name in table else _prefix(check_name)
    return table.get(
        key,
        "Review the failed rows and the check's configured threshold/condition — either "
        "fix the underlying data at the source, or adjust the check's config if the "
        "current values are actually expected.",
    )


def annotate_results(results, source: str = "table"):
    """Attach a `fix_suggestion` field (empty string for PASS) to every result
    dict in-place and return the same list, for convenient chaining."""
    for r in results:
        r["fix_suggestion"] = suggest_fix(r.get("check_name", ""), r, source=source)
    return results
