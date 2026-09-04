"""
MySQL Connection Tester

Validates MySQL connectivity, authentication, and database existence.
"""

from typing import Any, Dict

try:
    import pymysql
    PYMYSQL_AVAILABLE = True
except ImportError:
    PYMYSQL_AVAILABLE = False

from testers import error_response, success_response


def test_connection(config: Dict[str, Any], test_write: bool = False) -> dict:
    """
    Test MySQL connection.

    Args:
        config: Dict with keys: host, port, database, user, password
        test_write: Not used for MySQL (included for API consistency)

    Returns:
        dict with success, message, category, and details
    """
    if not PYMYSQL_AVAILABLE:
        return error_response(
            "MySQL driver not installed. Install: pip install pymysql",
            "connectivity",
        )

    required = ["host", "database", "user", "password"]
    missing = [f for f in required if not config.get(f)]
    if missing:
        return error_response(
            f"Missing required fields: {', '.join(missing)}", "connectivity", config
        )

    conn = None
    try:
        conn = pymysql.connect(
            host=config["host"],
            port=int(config.get("port") or 3306),
            database=config["database"],
            user=config["user"],
            password=config["password"],
            connect_timeout=5,
        )
        cursor = conn.cursor()
        cursor.execute("SELECT 1")
        cursor.fetchone()
        cursor.close()
        conn.close()
        conn = None

        return success_response(
            f"Connected to MySQL at {config['host']}/{config['database']}",
            {"host": config["host"], "database": config["database"]},
        )

    except Exception as e:
        error_msg = str(e).lower()
        if "can't connect" in error_msg or "connection refused" in error_msg or "timed out" in error_msg:
            category = "connectivity"
        elif "access denied" in error_msg:
            category = "auth"
        elif "unknown database" in error_msg:
            category = "not_found"
        else:
            category = "connectivity"
        return error_response(str(e), category, config)

    finally:
        if conn:
            try:
                conn.close()
            except Exception:
                pass
