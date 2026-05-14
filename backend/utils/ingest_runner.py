import os
import psycopg2
from utils.logger import DBLogger
from utils.run_tracker import RunTracker
from utils.schema_detector import detect_schema
from loaders.db_loader import load_to_db
from dotenv import load_dotenv

load_dotenv()

DB_CONFIG = {
    "host":     os.getenv("DB_HOST",     "postgres"),
    "database": os.getenv("DB_NAME",     "airflow"),
    "user":     os.getenv("DB_USER",     "airflow"),
    "password": os.getenv("DB_PASSWORD", "airflow"),
    "port":     os.getenv("DB_PORT",     "5432"),
}

def run_ingestion(connector_func, source, connector_name, *args,
                  option=None, table_name=None,
                  sync_mode="full", incremental_column=None):   # ← new params

    conn     = psycopg2.connect(**DB_CONFIG)
    tracker  = RunTracker(conn)
    run_id   = tracker.start_run(connector_name, source)
    logger   = DBLogger(conn, run_id)

    connector_type_map = {
        "CSVConnector":          "csv",
        "ExcelConnector":        "excel",
        "GoogleSheetsConnector": "google_sheets",
        "APIConnector":          "api",
        "PostgresConnector":     "postgres",
        "S3Connector":           "s3",
    }
    connector_type = connector_type_map.get(connector_name, connector_name)
    file_name = os.path.basename(source) if (source and os.path.exists(source)) else (source[:50] if source else None)
    pipeline_id    = f"pipeline_{table_name}"

    try:
        logger.log("INFO", f"{connector_name} started | sync_mode={sync_mode}")
        df        = connector_func(*args)
        row_count = df.shape[0]
        logger.log("INFO", f"Fetched {row_count} rows")

        detect_schema(df)
        logger.log("INFO", "Schema detected")

        load_to_db(
            df,
            option             = option,
            table_name         = table_name,
            pipeline_id        = pipeline_id,
            connector_type     = connector_type,
            file_name          = file_name,
            sync_mode          = sync_mode,           # ← pass 
            incremental_column = incremental_column,  # ← pass 
        )

        logger.log("INFO", "Data loaded to DB")
        tracker.end_run(run_id, "SUCCESS", row_count)
        return {"status": "SUCCESS", "run_id": run_id, "rows": row_count}

    except Exception as e:
        logger.log("ERROR", str(e))
        tracker.end_run(run_id, "FAILED", 0, str(e))
        return {"status": "FAILED", "run_id": run_id, "error": str(e)}

    finally:
        conn.close()
