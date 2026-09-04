"""
MongoDB Connection Tester

Validates MongoDB connectivity, authentication, and database/collection access.
"""

from typing import Any, Dict

try:
    from pymongo import MongoClient
    from pymongo.errors import OperationFailure, ServerSelectionTimeoutError
    PYMONGO_AVAILABLE = True
except ImportError:
    PYMONGO_AVAILABLE = False

from testers import error_response, success_response


def test_connection(config: Dict[str, Any], test_write: bool = False) -> dict:
    """
    Test MongoDB connection.

    Args:
        config: Dict with keys: connection_string (optional, mongodb:// / mongodb+srv://
            URI — takes priority when present) OR host, port, database, user, password.
            `collection` is optional; when given, its existence is verified.
        test_write: Not used for MongoDB (included for API consistency)

    Returns:
        dict with success, message, category, and details
    """
    if not PYMONGO_AVAILABLE:
        return error_response(
            "MongoDB driver not installed. Install: pip install pymongo",
            "connectivity",
        )

    connection_string = config.get("connection_string")
    database = config.get("database")

    if not connection_string:
        required = ["host", "database"]
        missing = [f for f in required if not config.get(f)]
        if missing:
            return error_response(
                f"Missing required fields: {', '.join(missing)}", "connectivity", config
            )

    client = None
    try:
        if connection_string:
            client = MongoClient(connection_string, serverSelectionTimeoutMS=5000)
        else:
            client = MongoClient(
                host=config["host"],
                port=int(config.get("port") or 27017),
                username=config.get("user") or None,
                password=config.get("password") or None,
                serverSelectionTimeoutMS=5000,
            )

        client.admin.command("ping")

        db = client[database]
        collections = db.list_collection_names()

        collection = config.get("collection")
        if collection and collection not in collections:
            client.close()
            return error_response(
                f"Collection '{collection}' not found in database '{database}'",
                "not_found",
                {"database": database, "collection": collection},
            )

        client.close()
        client = None

        msg = f"Connected to MongoDB database '{database}'"
        if collection:
            msg += f". Collection '{collection}' is accessible."
        return success_response(msg, {"database": database, "collection": collection})

    except ServerSelectionTimeoutError as e:
        return error_response(f"Could not reach MongoDB server: {e}", "connectivity", config)
    except OperationFailure as e:
        category = "auth" if "auth" in str(e).lower() else "permission"
        return error_response(str(e), category, config)
    except Exception as e:
        return error_response(str(e), "connectivity", config)

    finally:
        if client:
            try:
                client.close()
            except Exception:
                pass
