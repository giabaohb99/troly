"""Cloudflare R2 qua API S3 (S3 giả ở máy cá nhân khi R2_ENDPOINT trỏ moto)."""

from functools import lru_cache

import boto3
from botocore.client import Config
from botocore.exceptions import BotoCoreError, ClientError

from app.core.config import get_settings
from app.core.errors import ExternalServiceError


@lru_cache
def _client():
    s = get_settings()
    return boto3.client(
        "s3",
        endpoint_url=s.r2_endpoint_url,
        aws_access_key_id=s.r2_access_key_id or "dev",
        aws_secret_access_key=s.r2_secret_access_key or "dev",
        region_name="auto",
        config=Config(
            signature_version="s3v4", connect_timeout=10, read_timeout=30, retries={"max_attempts": 2}
        ),
    )


def presign_put(bucket: str, key: str, mime: str) -> str:
    return _client().generate_presigned_url(
        "put_object",
        Params={"Bucket": bucket, "Key": key, "ContentType": mime},
        ExpiresIn=get_settings().r2_presign_seconds,
    )


def presign_get(bucket: str, key: str, filename: str | None = None) -> str:
    params = {"Bucket": bucket, "Key": key}
    if filename:
        params["ResponseContentDisposition"] = f'attachment; filename="{filename}"'
    return _client().generate_presigned_url(
        "get_object", Params=params, ExpiresIn=get_settings().r2_presign_seconds
    )


def head(bucket: str, key: str) -> dict | None:
    try:
        return _client().head_object(Bucket=bucket, Key=key)
    except ClientError as exc:
        if exc.response.get("Error", {}).get("Code") in ("404", "NoSuchKey", "NotFound"):
            return None
        raise ExternalServiceError() from exc
    except BotoCoreError as exc:
        raise ExternalServiceError() from exc


def get_bytes(bucket: str, key: str, max_bytes: int | None = None) -> bytes:
    try:
        obj = _client().get_object(Bucket=bucket, Key=key)
        return obj["Body"].read(max_bytes) if max_bytes else obj["Body"].read()
    except (ClientError, BotoCoreError) as exc:
        raise ExternalServiceError() from exc


def put_bytes(bucket: str, key: str, data: bytes, mime: str = "application/octet-stream") -> None:
    try:
        _client().put_object(Bucket=bucket, Key=key, Body=data, ContentType=mime)
    except (ClientError, BotoCoreError) as exc:
        raise ExternalServiceError() from exc


def upload_fileobj(bucket: str, key: str, fileobj) -> None:
    try:
        _client().upload_fileobj(fileobj, bucket, key)
    except (ClientError, BotoCoreError) as exc:
        raise ExternalServiceError() from exc


def delete(bucket: str, key: str) -> None:
    try:
        _client().delete_object(Bucket=bucket, Key=key)
    except (ClientError, BotoCoreError) as exc:
        raise ExternalServiceError() from exc


def list_keys(bucket: str, prefix: str) -> list[dict]:
    try:
        resp = _client().list_objects_v2(Bucket=bucket, Prefix=prefix)
    except (ClientError, BotoCoreError) as exc:
        raise ExternalServiceError() from exc
    return [
        {"key": o["Key"], "size": o["Size"], "modified": o["LastModified"]} for o in resp.get("Contents", [])
    ]
