"""
Snowflake Connection Tester

Validates Snowflake connectivity, authentication, and schema permissions.
"""

import asyncio
from typing import Any, Dict

try:
    import snowflake.connector
    from snowflake.connector import Error as SnowflakeError
    SNOWFLAKE_AVAILABLE = True
except ImportError:
    SNOWFLAKE_AVAILABLE = False

import sys
from pathlib import Path
backend_dir = Path(__file__).parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from testers import error_response, success_response, sanitize_config


def test_connection(config: Dict[str, Any], test_write: bool = False) -> dict:
    """
    Test Snowflake connection.

    Args:
        config: Dict with keys: account, user, password, warehouse, database, schema, role
        test_write: Not used for Snowflake (included for API consistency)

    Returns:
        dict with success, message, category, and details
    """
    if not SNOWFLAKE_AVAILABLE:
        return error_response(
            "Snowflake driver not installed. Install: pip install snowflake-connector-python",
            "connectivity"
        )

    required_fields = ["account", "user", "password", "warehouse", "database"]
    missing = [f for f in required_fields if not config.get(f)]
    if missing:
        return error_response(
            f"Missing required fields: {', '.join(missing)}",
            "connectivity",
            config
        )

    conn = None
    try:
        # Build connection parameters with timeouts
        conn_params: Dict[str, Any] = {
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

        # Connect to Snowflake
        conn = snowflake.connector.connect(**conn_params)
        cursor = conn.cursor()

        # Test 1: Basic connectivity and auth
        cursor.execute("SELECT CURRENT_VERSION()")
        version = cursor.fetchone()[0]

        # Test 2: Schema permission check - verify role has access to target schema
        schema = config.get("schema", "PUBLIC")
        database = config["database"]
        
        try:
            cursor.execute(
                f"SELECT COUNT(*) FROM INFORMATION_SCHEMA.TABLES "
                f"WHERE TABLE_SCHEMA = '{schema}' AND TABLE_CATALOG = '{database}'"
            )
            cursor.fetchone()
            schema_access = True
        except Exception:
            schema_access = False

        cursor.close()
        conn.close()
        conn = None

        # Build success message
        msg = f"Connected to Snowflake {version}"
        if schema_access:
            msg += f". Schema '{schema}' is accessible."
        else:
            msg += f" but role may not have access to schema '{schema}'."

        return success_response(
            msg,
            {
                "version": version,
                "database": database,
                "schema": schema,
                "warehouse": config["warehouse"],
                "schema_access": schema_access
            }
        )

    except snowflake.connector.errors.OperationalError as e:
        error_msg = str(e).lower()
        if "network" in error_msg or "timeout" in error_msg or "could not connect" in error_msg:
            return error_response(
                f"Unable to reach Snowflake: {e}",
                "connectivity",
                config
            )
        elif "authentication" in error_msg or "invalid credentials" in error_msg or "password" in error_msg:
            return error_response(
                "Authentication failed: Invalid credentials",
                "auth",
                config
            )
        else:
            return error_response(
                f"Connection error: {e}",
                "connectivity",
                config
            )

    except snowflake.connector.errors.ProgrammingError as e:
        return error_response(
            f"Permission denied or object not found: {e}",
            "permission",
            config
        )

    except Exception as e:
        return error_response(
            f"Unexpected error: {e}",
            "connectivity",
            config
        )

    finally:
        if conn:
            try:
                conn.close()
            except Exception:
                pass


async def test_connection_async(config: Dict[str, Any], test_write: bool = False) -> dict:
    """Async wrapper for test_connection."""
    return await asyncio.to_thread(test_connection, config, test_write)