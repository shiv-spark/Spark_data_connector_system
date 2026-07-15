from typing import TypedDict, Optional, List

class PipelineState(TypedDict):
    # inputs
    source_type:   str
    pipeline_name: Optional[str]
    file_path:     Optional[str]
    sheet_url:     Optional[str]
    table_name:    Optional[str]
    pg_host:       Optional[str]    
    pg_port:       Optional[str]   
    pg_database:   Optional[str]     
    pg_user:       Optional[str]      
    pg_password:   Optional[str]
    s3_path:       Optional[str]
    api_url:       Optional[str]
    api_headers:   Optional[dict]
    sf_account:    Optional[str]
    sf_user:       Optional[str]
    sf_password:   Optional[str]
    sf_warehouse:  Optional[str]
    sf_database:   Optional[str]
    sf_schema:     Optional[str]
    sf_table:      Optional[str]
    sf_query:      Optional[str]
    sf_role:       Optional[str]
    user_request:  str
    model:         Optional[str]
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

