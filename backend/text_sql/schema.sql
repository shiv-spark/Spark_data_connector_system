CREATE TABLE sample_data.text2sql_run_metadata (
    run_id UUID PRIMARY KEY,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    user_question TEXT,
    generated_sql TEXT,

    validation_status VARCHAR(50),
    execution_approved BOOLEAN,
    execution_status VARCHAR(50),

    row_count INTEGER,

    model_name VARCHAR(100),

    prompt_tokens INTEGER,
    completion_tokens INTEGER,
    total_tokens INTEGER,

    llm_latency_seconds NUMERIC(10,2),
    execution_latency_seconds NUMERIC(10,2),

    response_summary TEXT,

    error_message TEXT
);



SELECT * FROM sample_data.text2sql_run_metadata;