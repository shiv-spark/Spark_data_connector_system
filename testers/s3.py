"""
S3 Connection Tester

Validates S3 connectivity, bucket existence, and access permissions.
"""

import asyncio
from typing import Any, Dict

try:
    import boto3
    from botocore.exceptions import ClientError, NoCredentialsError, EndpointConnectionError
    BOTO3_AVAILABLE = True
except ImportError:
    BOTO3_AVAILABLE = False

import sys
from pathlib import Path
backend_dir = Path(__file__).parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from testers import error_response, success_response


def test_connection(config: Dict[str, Any], test_write: bool = False) -> dict:
    """
    Test S3 connection.

    Args:
        config: Dict with keys: bucket, prefix, access_key, secret_key, region
        test_write: If True, test write permission by creating/deleting a marker file

    Returns:
        dict with success, message, category, and details
    """
    if not BOTO3_AVAILABLE:
        return error_response(
            "AWS SDK not installed. Install: pip install boto3",
            "connectivity"
        )

    if not config.get("bucket"):
        return error_response(
            "Missing required field: bucket",
            "connectivity",
            config
        )

    try:
        # Build boto3 client
        client_kwargs = {
            "service_name": "s3",
            "region_name": config.get("region", "us-east-1"),
        }

        # Use provided credentials or rely on IAM role
        if config.get("access_key") and config.get("secret_key"):
            client_kwargs["aws_access_key_id"] = config["access_key"]
            client_kwargs["aws_secret_access_key"] = config["secret_key"]

        s3 = boto3.client(**client_kwargs)

        bucket = config["bucket"]
        prefix = config.get("prefix", "").rstrip("/")
        
        # Test 1: Check bucket exists and credentials are valid
        try:
            s3.head_bucket(Bucket=bucket)
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "")
            if error_code == "404":
                return error_response(
                    f"Bucket '{bucket}' not found",
                    "not_found",
                    config
                )
            elif error_code == "403":
                return error_response(
                    f"Access denied to bucket '{bucket}'. Credentials may be invalid or lack permissions.",
                    "auth",
                    config
                )
            else:
                return error_response(
                    f"AWS error: {error_code} - {e}",
                    "permission",
                    config
                )
        except NoCredentialsError:
            return error_response(
                "No AWS credentials provided and no IAM role available",
                "auth",
                config
            )
        except EndpointConnectionError:
            return error_response(
                f"Cannot connect to S3 endpoint in region {config.get('region', 'us-east-1')}",
                "connectivity",
                config
            )

        # Test 2: Check list/read permission on prefix
        try:
            list_params = {
                "Bucket": bucket,
                "Prefix": prefix + "/" if prefix else "",
                "MaxKeys": 1
            }
            s3.list_objects_v2(**list_params)
            list_access = True
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "")
            if error_code == "403":
                list_access = False
            else:
                return error_response(
                    f"Error checking prefix access: {error_code}",
                    "permission",
                    config
                )
        except Exception as e:
            list_access = False

        # Test 3: Optional write test
        write_access = None
        if test_write:
            marker_key = f"{prefix}/.connector-test/marker.txt" if prefix else ".connector-test/marker.txt"
            try:
                s3.put_object(
                    Bucket=bucket,
                    Key=marker_key,
                    Body=b"connector-test",
                    ContentType="text/plain"
                )
                s3.delete_object(Bucket=bucket, Key=marker_key)
                write_access = True
            except ClientError as e:
                error_code = e.response.get("Error", {}).get("Code", "")
                if error_code == "403":
                    write_access = False
                else:
                    return error_response(
                        f"Error testing write access: {error_code}",
                        "permission",
                        config
                    )

        # Build success message
        msg = f"Connected to S3 bucket '{bucket}'"
        if list_access:
            msg += ". Read/list access confirmed."
        else:
            msg += ". Bucket exists but read/list access may be limited."
        
        if test_write:
            if write_access:
                msg += " Write access confirmed."
            else:
                msg += " Write access denied."

        details = {
            "bucket": bucket,
            "prefix": prefix or "(root)",
            "region": config.get("region", "us-east-1"),
            "list_access": list_access,
        }
        
        if test_write:
            details["write_access"] = write_access

        return success_response(msg, details)

    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "")
        return error_response(
            f"AWS error ({error_code}): {e}",
            "permission" if error_code in ("403", "404") else "connectivity",
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