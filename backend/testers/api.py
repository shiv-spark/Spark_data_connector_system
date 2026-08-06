"""
REST API Connection Tester

Validates that the configured API endpoint is reachable and that the
supplied credentials are accepted.
"""

from typing import Any, Dict

try:
    import httpx
    HTTPX_AVAILABLE = True
except ImportError:
    HTTPX_AVAILABLE = False

from testers import error_response, success_response


def _build_auth(config: Dict[str, Any]):
    """Translate the stored auth config into httpx headers/params/auth."""
    auth_type = config.get("auth_type", "none").lower().strip()
    headers: Dict[str, str] = {}
    params: Dict[str, str] = {}
    auth = None

    if auth_type == "bearer":
        token = config.get("bearer_token") or config.get("api_key")
        if token:
            headers["Authorization"] = f"Bearer {token}"
    elif auth_type == "api_key_header":
        if config.get("api_key"):
            headers[config.get("header_name", "x-api-key")] = config["api_key"]
    elif auth_type == "basic":
        if config.get("basic_user") and config.get("basic_password"):
            auth = (config["basic_user"], config["basic_password"])
    elif auth_type == "query_param":
        if config.get("api_key"):
            params[config.get("query_param_name", "api_key")] = config["api_key"]

    return headers, params, auth


def _resolve_url(base_url: str, test_endpoint: str) -> str:
    """
    Join base_url and test_endpoint into the URL to probe.

    The frontend defaults test_endpoint to base_url for convenience, so a
    naive concatenation would produce a doubled, invalid URL such as
    ".../search/https://.../search". Handle that case, and the case where
    test_endpoint is itself a complete URL, before falling back to a join.
    """
    base_url = (base_url or "").strip()
    test_endpoint = (test_endpoint or "").strip()

    if not test_endpoint or test_endpoint == base_url:
        return base_url
    if test_endpoint.startswith("http://") or test_endpoint.startswith("https://"):
        return test_endpoint
    return base_url.rstrip("/") + "/" + test_endpoint.lstrip("/")


def test_connection(config: Dict[str, Any], test_write: bool = False) -> dict:
    """
    Test a REST API connection.

    Args:
        config: Dict with keys: base_url, test_endpoint, auth_type, method,
                timeout, and auth-related fields
        test_write: Not used for APIs (included for API consistency)

    Returns:
        dict with success, message, category, and details
    """
    if not HTTPX_AVAILABLE:
        return error_response("httpx not installed", "connectivity")

    if not config.get("base_url"):
        return error_response(
            "Missing required field: base_url", "connectivity", config
        )

    timeout = config.get("timeout", 10)
    method = (config.get("method") or "GET").upper()
    headers, params, auth = _build_auth(config)
    url = _resolve_url(config["base_url"], config.get("test_endpoint", ""))

    try:
        with httpx.Client(timeout=timeout, auth=auth, follow_redirects=True) as client:
            response = client.request(method, url, headers=headers, params=params)

        if response.status_code in (200, 201, 204):
            return success_response(
                f"API connected. Status: {response.status_code}", {"url": url}
            )
        elif response.status_code in (301, 302, 303, 307, 308):
            return success_response(
                f"API connected (redirect). Final status: {response.status_code}",
                {"url": url},
            )
        elif response.status_code == 401:
            return error_response(
                "Authentication failed: 401 Unauthorized", "auth", config
            )
        elif response.status_code == 403:
            return error_response(
                "Authorization failed: 403 Forbidden", "auth", config
            )
        elif response.status_code >= 500:
            return error_response(
                f"Server error: HTTP {response.status_code}",
                "server_error",
                {"status_code": response.status_code},
            )
        return error_response(
            f"HTTP {response.status_code}",
            "server_error",
            {"status_code": response.status_code},
        )

    except httpx.TimeoutException:
        return error_response(
            f"Request timed out after {timeout}s", "connectivity", config
        )
    except httpx.ConnectError:
        return error_response(f"Cannot connect to {url}", "connectivity", config)
    except Exception as e:
        return error_response(str(e), "connectivity", config)
