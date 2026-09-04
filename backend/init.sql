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

-- Reverse ETL Pipelines (definitions; runs/logs reuse pipeline_runs/pipeline_logs/pipeline_metrics above)
CREATE TABLE IF NOT EXISTS reverse_etl_pipelines (
    id                  SERIAL PRIMARY KEY,
    pipeline_name       VARCHAR(200) UNIQUE NOT NULL,
    source_table        VARCHAR(200),
    source_query        TEXT,
    filter_sql          TEXT,
    destination_type    VARCHAR(50) NOT NULL,
    connection_id       INTEGER REFERENCES saved_connections(id) ON DELETE SET NULL,
    destination_config  JSONB DEFAULT '{}'::jsonb,
    destination_object  VARCHAR(300),
    field_mapping       JSONB DEFAULT '{}'::jsonb,
    upsert_key          VARCHAR(200),
    write_mode          VARCHAR(20) DEFAULT 'upsert',
    batch_size          INTEGER DEFAULT 200,
    sync_mode           VARCHAR(20) DEFAULT 'full',
    incremental_column  VARCHAR(200),
    last_synced_value   TEXT,
    schedule            VARCHAR(100) DEFAULT '*/15 * * * *',
    timezone            VARCHAR(50) DEFAULT 'Asia/Kolkata',
    status              VARCHAR(30) DEFAULT 'created',
    created_at          TIMESTAMP DEFAULT NOW(),
    updated_at          TIMESTAMP DEFAULT NOW()
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


-- -- ─────────────────────────────────────────────
-- -- USERS
-- -- ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS app_users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(100) UNIQUE NOT NULL,
    email VARCHAR(200) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    role VARCHAR(50) NOT NULL DEFAULT 'viewer',
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW(),
    last_login TIMESTAMP
);

INSERT INTO app_users (id, username, email, password_hash, role)
VALUES (1, 'default_user', 'default@example.com', 'x', 'admin')
ON CONFLICT (id) DO NOTHING;

SELECT setval('app_users_id_seq', GREATEST((SELECT MAX(id) FROM app_users), 1));

CREATE TABLE IF NOT EXISTS sql_query_history (
    query_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    connection_id INTEGER NOT NULL REFERENCES saved_connections(id),
    user_id INTEGER NOT NULL REFERENCES app_users(id),
    query_text TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'success',
    row_count INTEGER,
    error_message TEXT,
    duration_ms INTEGER,
    executed_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS sql_saved_queries (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    connection_id INTEGER NOT NULL REFERENCES saved_connections(id),
    user_id INTEGER NOT NULL REFERENCES app_users(id),
    name TEXT NOT NULL,
    query_text TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_sql_query_history_user ON sql_query_history(user_id);
CREATE INDEX IF NOT EXISTS idx_sql_query_history_connection ON sql_query_history(connection_id);
CREATE INDEX IF NOT EXISTS idx_sql_query_history_executed_at ON sql_query_history(executed_at DESC);



-- ─────────────────────────────────────────────
-- SQL EDITOR TABLES
-- ─────────────────────────────────────────────

-- Query history for SQL editor
CREATE TABLE IF NOT EXISTS sql_query_history (
    query_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    connection_id INTEGER NOT NULL REFERENCES saved_connections(id),
    user_id INTEGER NOT NULL REFERENCES app_users(id),
    query_text TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'success',
    row_count INTEGER,
    error_message TEXT,
    duration_ms INTEGER,
    executed_at TIMESTAMPTZ DEFAULT now()
);

-- Saved queries for SQL editor
CREATE TABLE IF NOT EXISTS sql_saved_queries (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    connection_id INTEGER NOT NULL REFERENCES saved_connections(id),
    user_id INTEGER NOT NULL REFERENCES app_users(id),
    name TEXT NOT NULL,
    query_text TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes for query history
CREATE INDEX IF NOT EXISTS idx_sql_query_history_user ON sql_query_history(user_id);
CREATE INDEX IF NOT EXISTS idx_sql_query_history_connection ON sql_query_history(connection_id);
CREATE INDEX IF NOT EXISTS idx_sql_query_history_executed_at ON sql_query_history(executed_at DESC);