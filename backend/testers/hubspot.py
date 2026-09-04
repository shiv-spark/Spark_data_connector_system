"""
HubSpot Connection Tester

Validates that the supplied Private App access token is accepted and, if
an object_type is given, that it's a readable CRM object.
"""

from typing import Any, Dict

try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False

from testers import error_response, success_response


def test_connection(config: Dict[str, Any], test_write: bool = False) -> dict:
    """
    Test a HubSpot connection.

    Args:
        config: Dict with keys: access_token (required), object_type (optional,
            defaults to "contacts" for the connectivity probe).
        test_write: Not used for HubSpot (included for API consistency)
    """
    if not REQUESTS_AVAILABLE:
        return error_response("requests not installed", "connectivity")

    access_token = config.get("access_token")
    if not access_token:
        return error_response("Missing required field: access_token", "connectivity", config)

    object_type = config.get("object_type") or "contacts"
    timeout = config.get("timeout", 10)
    headers = {"Authorization": f"Bearer {access_token}"}
    url = f"https://api.hubapi.com/crm/v3/objects/{object_type}"

    try:
        resp = requests.get(url, headers=headers, params={"limit": 1}, timeout=timeout)
    except requests.exceptions.Timeout:
        return error_response(f"Request timed out after {timeout}s", "connectivity", config)
    except requests.exceptions.ConnectionError:
        return error_response("Cannot connect to api.hubapi.com", "connectivity", config)

    if resp.status_code == 401:
        return error_response("Authentication failed: 401 Unauthorized (check access_token)", "auth", config)
    if resp.status_code == 403:
        return error_response(
            f"Authorization failed: 403 Forbidden (token may be missing scope for '{object_type}')",
            "auth",
            config,
        )
    if resp.status_code == 404:
        return error_response(f"Object type '{object_type}' not found", "not_found", config)
    if resp.status_code >= 500:
        return error_response(f"Server error: HTTP {resp.status_code}", "server_error", {"status_code": resp.status_code})
    if resp.status_code != 200:
        return error_response(f"HTTP {resp.status_code}: {resp.text}", "server_error", {"status_code": resp.status_code})

    return success_response(
        f"Connected to HubSpot. Object '{object_type}' is accessible.",
        {"object_type": object_type},
    )
