import boto3
import polars as pl
from io import BytesIO
import os

def s3_connector(bucket: str, key: str, file_type: str = "csv"):
    try:
        s3 = boto3.client(
            "s3",
            aws_access_key_id     = os.getenv("AWS_ACCESS_KEY_ID"),
            aws_secret_access_key = os.getenv("AWS_SECRET_ACCESS_KEY"),
            region_name           = os.getenv("AWS_REGION", "us-east-1"),
        )

        # ── Folder/Prefix  or single file ─────────────
        if key.endswith("/") or "." not in key.split("/")[-1]:
            # Folder mode — list all files in prefix
            print(f"Folder mode — listing: s3://{bucket}/{key}")
            keys = _list_s3_files(s3, bucket, key, file_type)

            if not keys:
                raise FileNotFoundError(
                    f"No .{file_type} files found in s3://{bucket}/{key}"
                )

            print(f"Found {len(keys)} file(s): {keys}")
            dfs = []
            for k in keys:
                df = _read_s3_file(s3, bucket, k, file_type)
                dfs.append(df)
                print(f"Loaded: {k} — {df.shape[0]} rows")

            # All files merge to one DataFrame
            merged = pl.concat(dfs)
            for col in merged.columns:
                if merged[col].dtype in [pl.Object, pl.Struct, pl.List]:
                    print(f"Converting complex column '{col}' to string to prevent DB errors.")
                    merged = merged.with_columns(pl.col(col).cast(pl.Utf8))
            print(f"Total merged — {merged.shape[0]} rows x {merged.shape[1]} cols")
            return merged

        else:
            # Single file mode
            print(f"Single file mode — s3://{bucket}/{key}")
            return _read_s3_file(s3, bucket, key, file_type)

    except Exception as e:
        raise Exception(f"S3 connector failed: {e}")


def _list_s3_files(s3_client, bucket: str, prefix: str, file_type: str) -> list:
    """List all S3 files in a given prefix with a specific file type"""
    response = s3_client.list_objects_v2(Bucket=bucket, Prefix=prefix)

    if "Contents" not in response:
        return []

    ext = f".{file_type.lower().strip('.')}"
    keys = [
        obj["Key"]
        for obj in response["Contents"]
        if obj["Key"].lower().endswith(ext)
        and not obj["Key"].endswith("/")   # folder entries skip
    ]
    return keys


def _read_s3_file(s3_client, bucket: str, key: str, file_type: str) -> pl.DataFrame:
    """Read a single S3 file and return as DataFrame"""
    obj  = s3_client.get_object(Bucket=bucket, Key=key)
    data = obj["Body"].read()
    print(f"Fetched: {key} — {len(data)} bytes")

    file_type = file_type.lower().strip(".")

    if file_type == "csv":
        return pl.read_csv(BytesIO(data))
    elif file_type in ("xlsx", "xls"):
        return pl.read_excel(BytesIO(data))
    elif file_type == "parquet":
        return pl.read_parquet(BytesIO(data))
    elif file_type == "json":
        return pl.read_json(BytesIO(data))
    else:
        raise ValueError(f"Unsupported file_type: {file_type}")

