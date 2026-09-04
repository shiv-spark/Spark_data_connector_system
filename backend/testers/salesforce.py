"""
Salesforce Connection Tester

Validates Salesforce connectivity + authentication, either against a
supplied access_token/instance_url or by running the username-password
OAuth flow with the supplied credentials.
"""

from typing import Any, Dict

try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False

from testers import error_response, success_response

API_VERSION = "v59.0"


def test_connection(config: Dict[str, Any], test_write: bool = False) -> dict:
    """
    Test a Salesforce connection.

    Args:
        config: Dict with either:
            - access_token + instance_url, or
            - login_url, client_id, client_secret, username, password[, security_token]
            Optional: object_name — if given, also verifies the object is describable.
        test_write: Not used for Salesforce (included for API consistency)
    """
    if not REQUESTS_AVAILABLE:
        return error_response("requests not installed", "connectivity")

    access_token = config.get("access_token")
    instance_url = config.get("instance_url")
    timeout = config.get("timeout", 10)

    if not access_token or not instance_url:
        required = ["client_id", "client_secret", "username", "password"]
        missing = [f for f in required if not config.get(f)]
        if missing:
            return error_response(
                f"Missing required fields: {', '.join(missing)} "
                f"(or supply access_token + instance_url directly)",
                "connectivity",
                config,
            )
        login_url = (config.get("login_url") or "https://login.salesforce.com").rstrip("/")
        try:
            resp = requests.post(
                f"{login_url}/services/oauth2/token",
                data={
                    "grant_type": "password",
                    "client_id": config["client_id"],
                    "client_secret": config["client_secret"],
                    "username": config["username"],
                    "password": f"{config['password']}{config.get('security_token', '')}",
                },
                timeout=timeout,
            )
        except requests.exceptions.Timeout:
            return error_response(f"Login request timed out after {timeout}s", "connectivity", config)
        except requests.exceptions.ConnectionError:
            return error_response(f"Cannot connect to {login_url}", "connectivity", config)

        if resp.status_code == 400:
            return error_response(f"Salesforce login rejected: {resp.text}", "auth", config)
        if resp.status_code != 200:
            return error_response(f"Salesforce login failed: HTTP {resp.status_code}", "server_error", config)

        data = resp.json()
        access_token = data["access_token"]
        instance_url = data["instance_url"]

    headers = {"Authorization": f"Bearer {access_token}"}
    try:
        resp = requests.get(
            f"{instance_url}/services/data/{API_VERSION}/limits",
            headers=headers,
            timeout=timeout,
        )
    except requests.exceptions.Timeout:
        return error_response(f"Request timed out after {timeout}s", "connectivity", config)
    except requests.exceptions.ConnectionError:
        return error_response(f"Cannot connect to {instance_url}", "connectivity", config)

    if resp.status_code == 401:
        return error_response("Authentication failed: 401 Unauthorized", "auth", config)
    if resp.status_code == 403:
        return error_response("Authorization failed: 403 Forbidden", "auth", config)
    if resp.status_code != 200:
        return error_response(f"HTTP {resp.status_code}: {resp.text}", "server_error", config)

    object_name = config.get("object_name")
    if object_name:
        describe_resp = requests.get(
            f"{instance_url}/services/data/{API_VERSION}/sobjects/{object_name}/describe",
            headers=headers,
            timeout=timeout,
        )
        if describe_resp.status_code == 404:
            return error_response(f"Object '{object_name}' not found", "not_found", config)
        if describe_resp.status_code != 200:
            return error_response(
                f"Could not describe object '{object_name}': HTTP {describe_resp.status_code}",
                "permission",
                config,
            )
        return success_response(
            f"Connected to Salesforce. Object '{object_name}' is accessible.",
            {"instance_url": instance_url, "object_name": object_name},
        )

    return success_response("Connected to Salesforce.", {"instance_url": instance_url})
