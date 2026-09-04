"""
Zoho CRM Connection Tester

Validates Zoho CRM connectivity + authentication, either against a
supplied access_token or by refreshing one from a refresh_token.
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
    Test a Zoho CRM connection.

    Args:
        config: Dict with either:
            - access_token, or
            - refresh_token, client_id, client_secret
            Optional: accounts_url (default https://accounts.zoho.com),
            api_domain (default https://www.zohoapis.com), module (default "Leads").
        test_write: Not used for Zoho (included for API consistency)
    """
    if not REQUESTS_AVAILABLE:
        return error_response("requests not installed", "connectivity")

    timeout = config.get("timeout", 10)
    access_token = config.get("access_token")

    if not access_token:
        required = ["refresh_token", "client_id", "client_secret"]
        missing = [f for f in required if not config.get(f)]
        if missing:
            return error_response(
                f"Missing required fields: {', '.join(missing)} (or supply access_token directly)",
                "connectivity",
                config,
            )
        accounts_url = (config.get("accounts_url") or "https://accounts.zoho.com").rstrip("/")
        try:
            resp = requests.post(
                f"{accounts_url}/oauth/v2/token",
                data={
                    "grant_type": "refresh_token",
                    "client_id": config["client_id"],
                    "client_secret": config["client_secret"],
                    "refresh_token": config["refresh_token"],
                },
                timeout=timeout,
            )
        except requests.exceptions.Timeout:
            return error_response(f"Token refresh timed out after {timeout}s", "connectivity", config)
        except requests.exceptions.ConnectionError:
            return error_response(f"Cannot connect to {accounts_url}", "connectivity", config)

        data = resp.json() if resp.content else {}
        if resp.status_code != 200 or "access_token" not in data:
            category = "auth" if resp.status_code in (400, 401) else "server_error"
            return error_response(f"Zoho token refresh failed: {resp.text}", category, config)
        access_token = data["access_token"]

    api_domain = (config.get("api_domain") or "https://www.zohoapis.com").rstrip("/")
    module = config.get("module") or "Leads"
    headers = {"Authorization": f"Zoho-oauthtoken {access_token}"}

    try:
        resp = requests.get(
            f"{api_domain}/crm/v3/{module}",
            headers=headers,
            params={"per_page": 1},
            timeout=timeout,
        )
    except requests.exceptions.Timeout:
        return error_response(f"Request timed out after {timeout}s", "connectivity", config)
    except requests.exceptions.ConnectionError:
        return error_response(f"Cannot connect to {api_domain}", "connectivity", config)

    if resp.status_code == 401:
        return error_response("Authentication failed: 401 Unauthorized", "auth", config)
    if resp.status_code == 403:
        return error_response("Authorization failed: 403 Forbidden", "auth", config)
    if resp.status_code == 204:
        # No content = authenticated fine, module just has 0 records.
        return success_response(f"Connected to Zoho CRM. Module '{module}' is accessible (empty).", {"module": module})
    if resp.status_code == 404:
        return error_response(f"Module '{module}' not found", "not_found", config)
    if resp.status_code >= 500:
        return error_response(f"Server error: HTTP {resp.status_code}", "server_error", {"status_code": resp.status_code})
    if resp.status_code != 200:
        return error_response(f"HTTP {resp.status_code}: {resp.text}", "server_error", {"status_code": resp.status_code})

    return success_response(f"Connected to Zoho CRM. Module '{module}' is accessible.", {"module": module})
