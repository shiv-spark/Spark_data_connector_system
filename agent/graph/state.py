from typing import TypedDict, Optional

class PipelineState(TypedDict):
    # inputs
    source_type:   str
    pipeline_name: Optional[str]
    file_path:     Optional[str]
    sheet_url:     Optional[str]
    table_name:    Optional[str]
    s3_path:       Optional[str]
    api_url:       Optional[str]
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
    report:         dict
    ai_summary:     str
    error:          Optional[str]
