"""
PostgreSQL Connection Tester

Validates PostgreSQL connectivity, authentication, and schema existence.
"""

from typing import Any, Dict

try:
    import psycopg2
    PSYCOPG2_AVAILABLE = True
except ImportError:
    PSYCOPG2_AVAILABLE = False

from testers import error_response, success_response


def test_connection(config: Dict[str, Any], test_write: bool = False) -> dict:
    """
    Test PostgreSQL connection.

    Args:
        config: Dict with keys: host, port, database, user, password, schema, sslmode
        test_write: Not used for PostgreSQL (included for API consistency)

    Returns:
        dict with success, message, category, and details
    """
    if not PSYCOPG2_AVAILABLE:
        return error_response(
            "PostgreSQL driver not installed. Install: pip install psycopg2-binary",
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
        conn_params: Dict[str, Any] = {
            "host": config["host"],
            "port": config.get("port", 5432),
            "database": config["database"],
            "user": config["user"],
            "password": config["password"],
            "connect_timeout": 5,
        }
        if config.get("sslmode"):
            conn_params["sslmode"] = config["sslmode"]

        conn = psycopg2.connect(**conn_params)
        cursor = conn.cursor()
        cursor.execute("SELECT 1")
        cursor.fetchone()

        # Verify schema exists if specified
        schema = config.get("schema")
        if schema:
            cursor.execute(
                "SELECT schema_name FROM information_schema.schemata "
                "WHERE schema_name = %s",
                (schema,),
            )
            if not cursor.fetchone():
                conn.close()
                conn = None
                return error_response(
                    f"Schema '{schema}' not found in database '{config['database']}'",
                    "not_found",
                    {"schema": schema, "database": config["database"]},
                )

        cursor.close()
        conn.close()
        conn = None

        msg = f"Connected to PostgreSQL at {config['host']}/{config['database']}"
        if schema:
            msg += f". Schema '{schema}' is accessible."
        return success_response(
            msg,
            {
                "host": config["host"],
                "database": config["database"],
                "schema": schema,
            },
        )

    except Exception as e:
        error_msg = str(e).lower()
        if "could not connect" in error_msg or "connection refused" in error_msg:
            category = "connectivity"
        elif "authentication" in error_msg or "password" in error_msg:
            category = "auth"
        elif "does not exist" in error_msg:
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
