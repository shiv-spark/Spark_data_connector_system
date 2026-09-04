"""
Oracle Connection Tester

Validates Oracle connectivity, authentication, and service name existence.
Uses python-oracledb in "thin" mode — no Oracle Instant Client required.
"""

from typing import Any, Dict

try:
    import oracledb
    ORACLEDB_AVAILABLE = True
except ImportError:
    ORACLEDB_AVAILABLE = False

from testers import error_response, success_response


def test_connection(config: Dict[str, Any], test_write: bool = False) -> dict:
    """
    Test Oracle connection.

    Args:
        config: Dict with keys: host, port, database (service name), user, password
        test_write: Not used for Oracle (included for API consistency)

    Returns:
        dict with success, message, category, and details
    """
    if not ORACLEDB_AVAILABLE:
        return error_response(
            "Oracle driver not installed. Install: pip install oracledb",
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
        dsn = oracledb.makedsn(
            config["host"], int(config.get("port") or 1521), service_name=config["database"]
        )
        conn = oracledb.connect(user=config["user"], password=config["password"], dsn=dsn, tcp_connect_timeout=5)
        cursor = conn.cursor()
        cursor.execute("SELECT 1 FROM DUAL")
        cursor.fetchone()
        cursor.close()
        conn.close()
        conn = None

        return success_response(
            f"Connected to Oracle at {config['host']}/{config['database']}",
            {"host": config["host"], "database": config["database"]},
        )

    except Exception as e:
        error_msg = str(e).lower()
        if "ora-01017" in error_msg or "invalid username" in error_msg:
            category = "auth"
        elif "ora-12154" in error_msg or "ora-12514" in error_msg or "not found" in error_msg:
            category = "not_found"
        elif "connect" in error_msg or "timeout" in error_msg:
            category = "connectivity"
        else:
            category = "connectivity"
        return error_response(str(e), category, config)

    finally:
        if conn:
            try:
                conn.close()
            except Exception:
                pass
