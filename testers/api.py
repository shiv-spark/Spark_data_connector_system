"""
API Connection Tester

Validates API connectivity, authentication, and endpoint access.
Supports: none, bearer, api_key_header, basic, query_param, oauth2
"""

import asyncio
from typing import Any, Dict

try:
    import httpx
    HTTPX_AVAILABLE = True
except ImportError:
    HTTPX_AVAILABLE = False

import sys
from pathlib import Path
backend_dir = Path(__file__).parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from testers import error_response, success_response


def test_connection(config: Dict[str, Any], test_write: bool = False) -> dict:
    """
    Test API connection.

    Args:
        config: Dict with keys: base_url, auth_type, test_endpoint, and auth-related fields
               Auth types:
               - none: no auth
               - bearer: bearer_token
               - api_key_header: api_key, header_name
               - basic: basic_user, basic_password
               - query_param: api_key, query_param_name
               - oauth2: oauth2_client_id, oauth2_client_secret, oauth2_token_url, oauth2_scope
        test_write: Not used for API (included for API consistency)

    Returns:
        dict with success, message, category, and details
    """
    if not HTTPX_AVAILABLE:
        return error_response(
            "HTTP client not installed. Install: pip install httpx",
            "connectivity"
        )

    if not config.get("base_url"):
        return error_response(
            "Missing required field: base_url",
            "connectivity",
            config
        )

    if not config.get("test_endpoint"):
        return error_response(
            "Missing required field: test_endpoint (e.g., /health, /me, /v1/status)",
            "connectivity",
            config
        )

    auth_type = config.get("auth_type", "none").lower().strip()
    timeout = config.get("timeout", 10)
    
    headers = {}
    params = {}
    auth = None

    try:
        # Build auth based on type
        if auth_type == "none":
            pass

        elif auth_type == "bearer":
            token = config.get("bearer_token") or config.get("api_key")
            if not token:
                return error_response(
                    "bearer auth requires bearer_token or api_key",
                    "auth",
                    config
                )
            headers["Authorization"] = f"Bearer {token}"

        elif auth_type == "api_key_header":
            api_key = config.get("api_key")
            if not api_key:
                return error_response(
                    "api_key_header auth requires api_key",
                    "auth",
                    config
                )
            header_name = config.get("header_name", "x-api-key")
            headers[header_name] = api_key

        elif auth_type == "basic":
            user = config.get("basic_user")
            password = config.get("basic_password")
            if not user or not password:
                return error_response(
                    "basic auth requires basic_user and basic_password",
                    "auth",
                    config
                )
            auth = (user, password)

        elif auth_type == "query_param":
            api_key = config.get("api_key")
            if not api_key:
                return error_response(
                    "query_param auth requires api_key",
                    "auth",
                    config
                )
            param_name = config.get("query_param_name", "api_key")
            params[param_name] = api_key

        elif auth_type == "oauth2":
            client_id = config.get("oauth2_client_id")
            client_secret = config.get("oauth2_client_secret")
            token_url = config.get("oauth2_token_url")
            scope = config.get("oauth2_scope", "")

            if not all([client_id, client_secret, token_url]):
                return error_response(
                    "oauth2 auth requires oauth2_client_id, oauth2_client_secret, and oauth2_token_url",
                    "auth",
                    config
                )

            # Perform OAuth2 token exchange
            token_response = None
            try:
                token_data = {
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "grant_type": "client_credentials",
                }
                if scope:
                    token_data["scope"] = scope

                with httpx.Client(timeout=timeout) as client:
                    token_response = client.post(token_url, data=token_data)

                if token_response.status_code != 200:
                    return error_response(
                        f"OAuth2 token exchange failed: HTTP {token_response.status_code}",
                        "auth",
                        config
                    )

                token_json = token_response.json()
                access_token = token_json.get("access_token")
                
                if not access_token:
                    return error_response(
                        "OAuth2 token exchange succeeded but no access_token in response",
                        "auth",
                        config
                    )

                headers["Authorization"] = f"Bearer {access_token}"

            except httpx.TimeoutException:
                return error_response(
                    f"OAuth2 token request timed out after {timeout}s",
                    "connectivity",
                    config
                )
            except httpx.ConnectError:
                return error_response(
                    "Cannot connect to OAuth2 token endpoint",
                    "connectivity",
                    config
                )
            except Exception as e:
                return error_response(
                    f"OAuth2 token exchange error: {e}",
                    "auth",
                    config
                )

        else:
            return error_response(
                f"Unsupported auth_type: {auth_type}",
                "connectivity",
                config
            )

        # Build test URL
        base_url = config["base_url"].rstrip("/")
        test_endpoint = config["test_endpoint"].lstrip("/")
        url = f"{base_url}/{test_endpoint}"

        # Add any extra headers
        if config.get("extra_headers"):
            headers.update(config["extra_headers"])

        # Make the test request
        try:
            with httpx.Client(timeout=timeout, auth=auth) as client:
                response = client.get(url, headers=headers, params=params)

            # Map response status to category
            if response.status_code == 200:
                details = {
                    "url": url,
                    "auth_type": auth_type,
                    "status_code": response.status_code,
                }
                return success_response(
                    f"API connected successfully. Status: {response.status_code}",
                    details
                )

            elif response.status_code == 401:
                return error_response(
                    "Authentication failed: 401 Unauthorized",
                    "auth",
                    {"url": url, "auth_type": auth_type}
                )

            elif response.status_code == 403:
                return error_response(
                    "Authorization failed: 403 Forbidden",
                    "auth",
                    {"url": url, "auth_type": auth_type}
                )

            elif 500 <= response.status_code < 600:
                return error_response(
                    f"Server error: HTTP {response.status_code}",
                    "server_error",
                    {"url": url, "status_code": response.status_code}
                )

            else:
                return error_response(
                    f"Unexpected response: HTTP {response.status_code}",
                    "server_error",
                    {"url": url, "status_code": response.status_code}
                )

        except httpx.TimeoutException:
            return error_response(
                f"Request to {url} timed out after {timeout}s",
                "connectivity",
                config
            )

        except httpx.ConnectError as e:
            return error_response(
                f"Cannot connect to {url}: {e}",
                "connectivity",
                config
            )

    except Exception as e:
        return error_response(
            f"Unexpected error: {e}",
            "connectivity",
            config
        )


async def test_connection_async(config: Dict[str, Any], test_write: bool = False) -> dict:
    """Async wrapper for test_connection."""
    return await asyncio.to_thread(test_connection, config, test_write)