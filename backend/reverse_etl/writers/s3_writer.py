"""
Writes rows OUT to S3 as a file (csv / json / parquet). Mirror image of
connectors/s3_connector.py (which reads FROM S3) — same config keys, so an
existing S3 saved connection can be reused as a reverse-ETL destination.

S3 has no row-level upsert concept, so every run uploads one object:
destination_object is treated as the S3 key (e.g. "exports/customers.csv").
write_mode "insert"/"upsert" appends a timestamp suffix so each run lands as
a new object; "update" overwrites the same key every run.

config keys: bucket, region (default us-east-1), access_key, secret_key,
             file_type (default inferred from destination_object's extension, else "csv")
"""

import io
import json as json_lib
from datetime import datetime, timezone

import pandas as pd

try:
    import boto3
    BOTO3_AVAILABLE = True
except ImportError:
    BOTO3_AVAILABLE = False


def _infer_file_type(key: str, config: dict) -> str:
    if config.get("file_type"):
        return config["file_type"].lower().strip(".")
    ext = key.rsplit(".", 1)[-1].lower() if "." in key else ""
    return ext if ext in ("csv", "json", "parquet") else "csv"


def _serialize(records: list, file_type: str) -> bytes:
    df = pd.DataFrame(records)
    buf = io.BytesIO()
    if file_type == "csv":
        df.to_csv(buf, index=False)
    elif file_type == "json":
        buf.write(json_lib.dumps(records, default=str).encode("utf-8"))
    elif file_type == "parquet":
        df.to_parquet(buf, index=False)
    else:
        raise ValueError(f"Unsupported file_type for S3 destination: {file_type!r}")
    return buf.getvalue()


def s3_writer(records: list, config: dict, object_name: str,
              upsert_key: str | None, write_mode: str, batch_size: int = 0) -> dict:
    if not records:
        return {"success": 0, "failed": 0, "errors": []}

    if not BOTO3_AVAILABLE:
        raise ImportError("S3 support requires boto3 (pip install boto3).")

    bucket = config.get("bucket")
    if not bucket:
        raise ValueError("s3 destination requires 'bucket' in config")
    if not object_name:
        raise ValueError("s3 destination requires a destination_object (S3 key, e.g. 'exports/customers.csv')")

    file_type = _infer_file_type(object_name, config)
    key = object_name
    if write_mode in ("insert", "upsert"):
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        base, _, ext = object_name.rpartition(".")
        key = f"{base or object_name}_{stamp}.{ext or file_type}"
    # write_mode == "update" -> overwrite the same key every run

    try:
        s3 = boto3.client(
            "s3",
            region_name=config.get("region", "us-east-1"),
            aws_access_key_id=config.get("access_key") or None,
            aws_secret_access_key=config.get("secret_key") or None,
        )
        body = _serialize(records, file_type)
        s3.put_object(Bucket=bucket, Key=key, Body=body)
        return {"success": len(records), "failed": 0, "errors": [], "s3_key": key}
    except Exception as e:
        return {"success": 0, "failed": len(records), "errors": [str(e)]}
