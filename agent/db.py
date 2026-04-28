import psycopg2
import psycopg2.extras
import os
from contextlib import contextmanager

from agent.logger import get_logger

logger = get_logger(__name__)

DB_CONFIG = {
    "host":     os.getenv("DB_HOST", "localhost"),
    "port":     int(os.getenv("DB_PORT", 5432)),
    "dbname":   os.getenv("DB_NAME", "your_db"),
    "user":     os.getenv("DB_USER", "your_user"),
    "password": os.getenv("DB_PASSWORD", "your_password"),
}

@contextmanager
def get_conn():
    logger.debug("Opening DB connection to %s:%s/%s",
                 DB_CONFIG["host"], DB_CONFIG["port"], DB_CONFIG["dbname"])
    conn = psycopg2.connect(**DB_CONFIG)
    try:
        yield conn
    except Exception as e:
        logger.error("DB connection error: %s", e, exc_info=True)
        raise
    finally:
        conn.close()
        logger.debug("DB connection closed")

def query(sql: str, params=None) -> list[dict]:
    logger.debug("Executing SQL: %s", sql.strip()[:200])
    logger.debug("SQL params: %s", params)
    try:
        with get_conn() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(sql, params or [])
                rows = [dict(row) for row in cur.fetchall()]
                logger.info("Query returned %d rows", len(rows))
                return rows
    except Exception as e:
        logger.error("Query failed: %s", e, exc_info=True)
        raise
