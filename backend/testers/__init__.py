"""
Connection Testers

Each module provides a test_connection(config: dict, test_write: bool = False) -> dict
function that validates connectivity, authentication, and permissions for a data source.

Response Format:
{
    "success": bool,
    "message": str,
    "category": "connectivity" | "auth" | "permission" | "not_found" | "server_error" | "success",
    "details": dict  # sanitized - no secrets
}
"""


def sanitize_config(config: dict) -> dict:
    """Remove sensitive information from config before returning to client."""
    safe = dict(config)
    sensitive_keys = {
        "password", "secret", "token", "access_key", "secret_key",
        "private_key", "passphrase", "api_key", "bearer_token",
        "basic_password", "client_secret", "refresh_token"
    }
    for key in list(safe.keys()):
        if any(s in key.lower() for s in sensitive_keys):
            safe[key] = "********"
    return safe


def error_response(message: str, category: str, details: dict = None) -> dict:
    """Create a standardized error response."""
    return {
        "success": False,
        "message": message,
        "category": category,
        "details": sanitize_config(details or {})
    }


def success_response(message: str, details: dict = None) -> dict:
    """Create a standardized success response."""
    return {
        "success": True,
        "message": message,
        "category": "success",
        "details": sanitize_config(details or {})
    }


# Source types that are validated by a tester module in this package.
# Anything else is handled inline by the /connectors/test route
# (local_folder, google_sheet, figma_design are format/path checks only).
TESTER_MODULES = {
    "snowflake": "testers.snowflake",
    "postgres": "testers.postgres",
    "mysql": "testers.mysql",
    "oracle": "testers.oracle",
    "mongodb": "testers.mongodb",
    "s3": "testers.s3",
    "api": "testers.api",
    "salesforce": "testers.salesforce",
    "hubspot": "testers.hubspot",
    "zoho": "testers.zoho",
}


def get_tester(source_type: str):
    """
    Resolve a source type to its test_connection callable.

    Returns None if the source type has no network tester.
    """
    module_path = TESTER_MODULES.get(source_type.lower().strip())
    if not module_path:
        return None

    import importlib
    return importlib.import_module(module_path).test_connection
