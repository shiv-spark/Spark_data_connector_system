import uvicorn
import os
import psycopg2
import time
from dotenv import load_dotenv

load_dotenv()

DB_CONFIG = {
    "host":     os.getenv("DB_HOST",     "postgres"),
    "database": os.getenv("DB_NAME",     "airflow"),
    "user":     os.getenv("DB_USER",     "airflow"),
    "password": os.getenv("DB_PASSWORD", "airflow"),
    "port":     os.getenv("DB_PORT",     "5432"),
}

def create_logs_tables():
    queries = [
        """CREATE TABLE IF NOT EXISTS pipeline_runs (
            run_id SERIAL PRIMARY KEY,
            connector_name VARCHAR(100),
            source TEXT,
            start_time TIMESTAMP,
            end_time TIMESTAMP,
            status VARCHAR(20),
            records_count INTEGER DEFAULT 0,
            error TEXT
        )""",
        """CREATE TABLE IF NOT EXISTS pipeline_logs (
            id SERIAL PRIMARY KEY,
            run_id INTEGER REFERENCES pipeline_runs(run_id),
            log_time TIMESTAMP,
            level VARCHAR(10),
            message TEXT
        )""",
        """CREATE TABLE IF NOT EXISTS pipeline_metrics (
            id SERIAL PRIMARY KEY,
            pipeline_id VARCHAR(200),
            table_name VARCHAR(100),
            rows_inserted INTEGER DEFAULT 0,
            rows_skipped INTEGER DEFAULT 0,
            rows_failed INTEGER DEFAULT 0,
            duration_sec NUMERIC(10,2),
            evolved_columns TEXT[],
            match_pct NUMERIC(5,2),
            file_name TEXT,
            connector_type VARCHAR(50),
            option VARCHAR(5),
            status VARCHAR(20),
            error_message TEXT,
            logged_at TIMESTAMP DEFAULT NOW()
        )""",
        """CREATE TABLE IF NOT EXISTS airflow_pipeline_runs (
            id SERIAL PRIMARY KEY,
            dag_id VARCHAR(200),
            dag_run_id VARCHAR(200),
            pipeline_name VARCHAR(200),
            connector_type VARCHAR(50),
            file_path TEXT,
            folder_path TEXT,
            sheet_url TEXT,
            api_url TEXT,
            operation VARCHAR(20),
            table_name VARCHAR(100),
            schedule VARCHAR(100),
            status VARCHAR(20),
            execution_date TEXT,
            triggered_by VARCHAR(50),
            error_message TEXT,
            created_at TIMESTAMP DEFAULT NOW()
        )""",
        """CREATE TABLE IF NOT EXISTS pipeline_dag_logs (
            id SERIAL PRIMARY KEY,
            pipeline_id VARCHAR(200),
            dag_run_id VARCHAR(200),
            task_id VARCHAR(200),
            status VARCHAR(20),
            log_content TEXT,
            log_file_path TEXT,
            created_at TIMESTAMP DEFAULT NOW()
        )"""
    ]

    try:
        conn = psycopg2.connect(**DB_CONFIG)
        conn.autocommit = True
        cur = conn.cursor()
        for q in queries:
            cur.execute(q)
        cur.close()
        conn.close()
        print("✅ All logs tables created/verified successfully.")
        return True
    except Exception as e:
        print(f"❌ Table creation failed: {e}")
        return False

def wait_for_db(max_retries=12, delay=5):
    print(f"⏳ Waiting for database {DB_CONFIG['host']}:{DB_CONFIG['port']}...")
    for i in range(max_retries):
        try:
            conn = psycopg2.connect(**DB_CONFIG)
            conn.close()
            print(f"✅ Database ready after {i+1} attempt(s)")
            return True
        except Exception as e:
            print(f"⏳ Attempt {i+1}/{max_retries} failed: {e}")
            time.sleep(delay)
    print("❌ Database not reachable. Continuing without table creation.")
    return False

if __name__ == "__main__":
    print("🚀 Starting Data Connector API...")
    if wait_for_db():
        create_logs_tables()
    else:
        print("⚠️ Could not create tables (database not ready).")

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=False)