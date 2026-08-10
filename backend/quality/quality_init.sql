-- ─────────────────────────────────────────────────────────────────────────
-- Data Quality Layer — audit tables
-- Add this block to backend/init.sql (it already runs automatically on
-- postgres container startup via docker-entrypoint-initdb.d)
-- ─────────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS quality_runs (
    run_id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    connection_id    INTEGER NOT NULL REFERENCES saved_connections(id) ON DELETE CASCADE,
    started_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    completed_at     TIMESTAMPTZ,
    duration_seconds NUMERIC,
    total_checks     INTEGER NOT NULL DEFAULT 0,
    passed_checks    INTEGER NOT NULL DEFAULT 0,
    failed_checks    INTEGER NOT NULL DEFAULT 0,
    status           VARCHAR(20) NOT NULL DEFAULT 'RUNNING'  -- RUNNING | PASS | FAIL
);

CREATE TABLE IF NOT EXISTS quality_results (
    id            SERIAL PRIMARY KEY,
    run_id        UUID NOT NULL REFERENCES quality_runs(run_id) ON DELETE CASCADE,
    table_name    VARCHAR(160) NOT NULL,
    check_name    VARCHAR(80)  NOT NULL,   -- NULL_CHECK | DUPLICATE_CHECK | ROW_COUNT | ...
    status        VARCHAR(10)  NOT NULL,   -- PASS | FAIL
    failed_rows   INTEGER,
    source_value  TEXT,
    target_value  TEXT,
    message       TEXT,
    checked_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_quality_results_run     ON quality_results(run_id);
CREATE INDEX IF NOT EXISTS idx_quality_runs_connection  ON quality_runs(connection_id);
CREATE INDEX IF NOT EXISTS idx_quality_runs_started_at  ON quality_runs(started_at DESC);