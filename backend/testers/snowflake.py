"""
Snowflake Connection Tester

Validates Snowflake connectivity, authentication, and that the configured
database and schema are reachable.
"""

from typing import Any, Dict

try:
    import snowflake.connector
    SNOWFLAKE_AVAILABLE = True
except ImportError:
    SNOWFLAKE_AVAILABLE = False

from testers import error_response, success_response


def test_connection(config: Dict[str, Any], test_write: bool = False) -> dict:
    """
    Test Snowflake connection.

    Args:
        config: Dict with keys: account, user, password, warehouse, database,
                and optionally schema and role
        test_write: Not used for Snowflake (included for API consistency)

    Returns:
        dict with success, message, category, and details
    """
    if not SNOWFLAKE_AVAILABLE:
        return error_response("snowflake-connector-python not installed", "connectivity")

    required = ["account", "user", "password", "warehouse", "database"]
    missing = [f for f in required if not config.get(f)]
    if missing:
        return error_response(
            f"Missing required fields: {', '.join(missing)}", "connectivity", config
        )

    conn = None
    try:
        conn_params = {
            "account": config["account"],
            "user": config["user"],
            "password": config["password"],
            "warehouse": config["warehouse"],
            "database": config["database"],
            "schema": config.get("schema", "PUBLIC"),
            "login_timeout": 10,
            "network_timeout": 10,
        }
        if config.get("role"):
            conn_params["role"] = config["role"]

        conn = snowflake.connector.connect(**conn_params)
        cursor = conn.cursor()
        cursor.execute("SELECT CURRENT_VERSION()")
        version = cursor.fetchone()[0]

        # Verify database exists
        database = config["database"]
        cursor.execute(
            "SELECT DATABASE_NAME FROM INFORMATION_SCHEMA.DATABASES "
            "WHERE DATABASE_NAME = %s",
            (database,),
        )
        if not cursor.fetchone():
            conn.close()
            conn = None
            return error_response(
                f"Database '{database}' not found or not accessible",
                "not_found",
                {"database": database},
            )

        # Verify schema exists in the database
        schema = config.get("schema", "PUBLIC")
        cursor.execute(
            f"SELECT SCHEMA_NAME FROM {database}.INFORMATION_SCHEMA.SCHEMATA "
            "WHERE SCHEMA_NAME = %s AND CATALOG_NAME = %s",
            (schema, database),
        )
        if not cursor.fetchone():
            conn.close()
            conn = None
            return error_response(
                f"Schema '{schema}' not found in database '{database}'",
                "not_found",
                {"database": database, "schema": schema},
            )

        cursor.close()
        conn.close()
        conn = None

        return success_response(
            f"Connected to Snowflake {version}. "
            f"Database '{database}' and schema '{schema}' are accessible.",
            {"version": version, "database": database, "schema": schema},
        )

    except Exception as e:
        error_msg = str(e).lower()
        if "network" in error_msg or "timeout" in error_msg:
            category = "connectivity"
        elif (
            "authentication" in error_msg
            or "password" in error_msg
            or "invalid credentials" in error_msg
        ):
            category = "auth"
        else:
            category = "connectivity"
        return error_response(str(e), category, config)

    finally:
        if conn:
            try:
                conn.close()
            except Exception:
                pass
