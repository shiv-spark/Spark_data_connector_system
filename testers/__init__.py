"""
Test Connection Modules

Each module provides a test_connection(config: dict, test_write: bool = False) -> dict
function that validates connectivity, authentication, and permissions for a data source.

Response Format:
{
    "success": bool,
    "message": str,
    "category": "connectivity" | "auth" | "permission" | "not_found" | "server_error",
    "details": dict  # sanitized - no secrets
}
"""

from typing import Any


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