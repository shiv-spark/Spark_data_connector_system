"""
S3 Connection Tester

Validates S3 bucket reachability and read/list permissions.
"""

from typing import Any, Dict

try:
    import boto3
    from botocore.exceptions import ClientError
    BOTO3_AVAILABLE = True
except ImportError:
    BOTO3_AVAILABLE = False

    class ClientError(Exception):
        """Placeholder so the except clause stays valid without boto3."""

from testers import error_response, success_response


def test_connection(config: Dict[str, Any], test_write: bool = False) -> dict:
    """
    Test S3 connection.

    Args:
        config: Dict with keys: bucket, region, access_key, secret_key, prefix
        test_write: Not used for S3 (included for API consistency)

    Returns:
        dict with success, message, category, and details
    """
    if not BOTO3_AVAILABLE:
        return error_response("boto3 not installed", "connectivity")

    if not config.get("bucket"):
        return error_response("Missing required field: bucket", "connectivity", config)

    try:
        client_kwargs = {
            "service_name": "s3",
            "region_name": config.get("region", "us-east-1"),
        }
        if config.get("access_key") and config.get("secret_key"):
            client_kwargs["aws_access_key_id"] = config["access_key"]
            client_kwargs["aws_secret_access_key"] = config["secret_key"]

        s3 = boto3.client(**client_kwargs)
        bucket = config["bucket"]
        prefix = config.get("prefix", "").rstrip("/")

        s3.head_bucket(Bucket=bucket)
        s3.list_objects_v2(
            Bucket=bucket, Prefix=prefix + "/" if prefix else "", MaxKeys=1
        )

        return success_response(
            f"Connected to S3 bucket '{bucket}'. Read/list access confirmed.",
            {"bucket": bucket, "region": config.get("region", "us-east-1")},
        )

    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "")
        if error_code == "404":
            return error_response(
                f"Bucket '{config.get('bucket')}' not found", "not_found", config
            )
        elif error_code == "403":
            return error_response(
                "Access denied. Check credentials and permissions.", "auth", config
            )
        return error_response(f"AWS error: {error_code}", "permission", config)

    except Exception as e:
        return error_response(str(e), "connectivity", config)
