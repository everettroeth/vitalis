"""Cloudflare R2 (S3-compatible) file upload service."""

from __future__ import annotations

import hashlib
import logging
import uuid
from typing import BinaryIO

import boto3
from botocore.config import Config as BotoConfig

from src.config import Settings, get_settings

logger = logging.getLogger("vitalis.r2")

# Reusable client — created lazily
_client: "boto3.client" | None = None


def _get_client(settings: Settings | None = None) -> "boto3.client":
    global _client
    if _client is not None:
        return _client

    s = settings or get_settings()
    _client = boto3.client(
        "s3",
        endpoint_url=f"https://{s.r2_account_id}.r2.cloudflarestorage.com",
        aws_access_key_id=s.r2_access_key_id,
        aws_secret_access_key=s.r2_secret_access_key,
        config=BotoConfig(
            signature_version="s3v4",
            retries={"max_attempts": 3, "mode": "standard"},
        ),
        region_name="auto",
    )
    return _client


def compute_file_hash(data: bytes) -> str:
    """Return hex-encoded SHA-256 hash of file contents."""
    return hashlib.sha256(data).hexdigest()


async def upload_file(
    *,
    user_id: uuid.UUID,
    file_data: bytes,
    filename: str,
    content_type: str,
    prefix: str = "documents",
    settings: Settings | None = None,
) -> tuple[str, str, int]:
    """Upload a file to R2 and return (s3_key, file_hash, file_size).

    The S3 key follows the pattern: ``{prefix}/{user_id}/{uuid}_{filename}``
    to ensure uniqueness and user-level isolation.
    """
    s = settings or get_settings()
    client = _get_client(s)

    file_hash = compute_file_hash(file_data)
    file_id = uuid.uuid4().hex[:12]
    # Sanitize filename — keep only the last segment and limit length
    safe_name = filename.replace("/", "_").replace("\\", "_")[:100]
    s3_key = f"{prefix}/{user_id}/{file_id}_{safe_name}"

    client.put_object(
        Bucket=s.r2_bucket_name,
        Key=s3_key,
        Body=file_data,
        ContentType=content_type,
        Metadata={
            "user_id": str(user_id),
            "original_filename": filename,
            "file_hash": file_hash,
        },
    )

    logger.info(
        "Uploaded %s (%d bytes) to R2 key=%s",
        filename,
        len(file_data),
        s3_key,
    )
    return s3_key, file_hash, len(file_data)


async def generate_presigned_url(
    s3_key: str,
    expires_in: int = 3600,
    settings: Settings | None = None,
) -> str:
    """Generate a presigned download URL (valid for ``expires_in`` seconds)."""
    s = settings or get_settings()
    client = _get_client(s)
    return client.generate_presigned_url(
        "get_object",
        Params={"Bucket": s.r2_bucket_name, "Key": s3_key},
        ExpiresIn=expires_in,
    )


async def delete_file(
    s3_key: str,
    settings: Settings | None = None,
) -> None:
    """Delete a file from R2."""
    s = settings or get_settings()
    client = _get_client(s)
    client.delete_object(Bucket=s.r2_bucket_name, Key=s3_key)
    logger.info("Deleted R2 key=%s", s3_key)
