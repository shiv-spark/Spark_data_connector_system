"""
PostgreSQL Connection Tester

Validates PostgreSQL connectivity, authentication, and schema permissions.
"""

import asyncio
from typing import Any, Dict

try:
    import psycopg2
    from psycopg2 import OperationalError, ProgrammingError
    PSYCOPG2_AVAILABLE = True
except ImportError:
    PSYCOPG2_AVAILABLE = False

import sys
from pathlib import Path
backend_dir = Path(__file__).parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

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
            "connectivity"
        )

    required_fields = ["host", "database", "user", "password"]
    missing = [f for f in required_fields if not config.get(f)]
    if missing:
        return error_response(
            f"Missing required fields: {', '.join(missing)}",
            "connectivity",
            config
        )

    conn = None
    try:
        # Build connection parameters with timeout
        conn_params: Dict[str, Any] = {
            "host": config["host"],
            "port": config.get("port", 5432),
            "database": config["database"],
            "user": config["user"],
            "password": config["password"],
            "connect_timeout": 5,
        }

        # Add sslmode if specified
        if config.get("sslmode"):
            conn_params["sslmode"] = config["sslmode"]

        # Connect to PostgreSQL
        conn = psycopg2.connect(**conn_params)
        cursor = conn.cursor()

        # Test 1: Basic connectivity
        cursor.execute("SELECT 1")
        cursor.fetchone()

        # Test 2: Schema existence check (if schema specified)
        schema = config.get("schema")
        schema_exists = None
        
        if schema:
            cursor.execute(
                "SELECT schema_name FROM information_schema.schemata WHERE schema_name = %s",
                (schema,)
            )
            schema_exists = cursor.fetchone() is not None

        cursor.close()
        conn.close()
        conn = None

        # Build response
        details = {
            "host": config["host"],
            "port": config.get("port", 5432),
            "database": config["database"],
        }
        
        if schema:
            details["schema"] = schema
            details["schema_exists"] = schema_exists

        msg = f"Connected to PostgreSQL at {config['host']}/{config['database']}"
        if schema:
            if schema_exists:
                msg += f". Schema '{schema}' exists and is accessible."
            else:
                msg += f" but schema '{schema}' was not found."

        return success_response(msg, details)

    except OperationalError as e:
        error_msg = str(e).lower()
        
        # Distinguish between different OperationalError types
        if "could not connect to server" in error_msg or "connection refused" in error_msg:
            return error_response(
                f"Cannot connect to host: {config.get('host')}. Host is unreachable or port is wrong.",
                "connectivity",
                config
            )
        elif "timeout" in error_msg or "connection timed out" in error_msg:
            return error_response(
                f"Connection timed out after 5s. Host: {config.get('host')}",
                "connectivity",
                config
            )
        elif "authentication failed" in error_msg or "password authentication failed" in error_msg:
            return error_response(
                "Authentication failed: Invalid username or password",
                "auth",
                config
            )
        elif "database" in error_msg and ("does not exist" in error_msg or "not found" in error_msg):
            return error_response(
                f"Database '{config.get('database')}' does not exist",
                "not_found",
                config
            )
        else:
            return error_response(
                f"Connection error: {e}",
                "connectivity",
                config
            )

    except ProgrammingError as e:
        return error_response(
            f"Permission denied: {e}",
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