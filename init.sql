-- Pipeline Runs
CREATE TABLE IF NOT EXISTS pipeline_runs (
    run_id         SERIAL PRIMARY KEY,
    connector_name VARCHAR(100),
    source         TEXT,
    start_time     TIMESTAMP,
    end_time       TIMESTAMP,
    status         VARCHAR(20),
    records_count  INTEGER DEFAULT 0,
    error          TEXT
);

-- Pipeline Logs
CREATE TABLE IF NOT EXISTS pipeline_logs (
    id       SERIAL PRIMARY KEY,
    run_id   INTEGER REFERENCES pipeline_runs(run_id),
    log_time TIMESTAMP,
    level    VARCHAR(10),
    message  TEXT
);

-- Pipeline Metrics
CREATE TABLE IF NOT EXISTS pipeline_metrics (
    id              SERIAL PRIMARY KEY,
    pipeline_id     VARCHAR(200),
    table_name      VARCHAR(100),
    rows_inserted   INTEGER  DEFAULT 0,
    rows_skipped    INTEGER  DEFAULT 0,
    rows_failed     INTEGER  DEFAULT 0,
    duration_sec    NUMERIC(10,2),
    evolved_columns TEXT[],
    match_pct       NUMERIC(5,2),
    file_name       TEXT,
    connector_type  VARCHAR(50),
    option          VARCHAR(5),
    status          VARCHAR(20),
    error_message   TEXT,
    logged_at       TIMESTAMP DEFAULT NOW()
);

-- Airflow Pipeline Runs
CREATE TABLE IF NOT EXISTS airflow_pipeline_runs (
    id             SERIAL PRIMARY KEY,
    dag_id         VARCHAR(200),
    dag_run_id     VARCHAR(200),
    pipeline_name  VARCHAR(200),
    connector_type VARCHAR(50),
    file_path      TEXT,
    folder_path    TEXT,
    sheet_url      TEXT,
    api_url        TEXT,
    operation      VARCHAR(20),
    table_name     VARCHAR(100),
    schedule       VARCHAR(100),
    status         VARCHAR(20),
    execution_date TEXT,
    triggered_by   VARCHAR(50),
    error_message  TEXT,
    created_at     TIMESTAMP DEFAULT NOW()
);

-- Pipeline DAG Logs
CREATE TABLE IF NOT EXISTS pipeline_dag_logs (
    id            SERIAL PRIMARY KEY,
    pipeline_id   VARCHAR(200),
    dag_run_id    VARCHAR(200),
    task_id       VARCHAR(200),
    status        VARCHAR(20),
    log_content   TEXT,
    log_file_path TEXT,
    created_at    TIMESTAMP DEFAULT NOW()
);