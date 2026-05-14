from typing import TypedDict, Optional, List

class PipelineState(TypedDict):
    # inputs
    source_type:   str
    pipeline_name: Optional[str]
    file_path:     Optional[str]
    sheet_url:     Optional[str]
    table_name:    Optional[str]
    s3_path:       Optional[str]
    api_url:       Optional[str]
    api_headers:   Optional[dict]
    user_request:  str
    # results
    data:           dict
    null_result:    dict
    dup_result:     dict
    stats_result:   dict
    outlier_result: dict
    corr_result:    dict
    health_result:  dict
    quality_result: dict
    charts:         dict
    chart_meta:     list   # [{slot, title, description, config}] — LLM-decided chart info
    report:         dict
    ai_summary:     str
    error:          Optional[str]
