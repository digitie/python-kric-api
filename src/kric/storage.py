"""RustFS 등 S3 호환 저장소에 provider 원본 파일을 비동기로 보관한다."""

from __future__ import annotations

import asyncio
import hashlib
import importlib
import re
from dataclasses import dataclass
from typing import Any, Protocol
from urllib.parse import urlparse

from .exceptions import KricInvalidParameterError, KricNetworkError

_BUCKET_RE = re.compile(r"^[a-z0-9][a-z0-9.-]{1,61}[a-z0-9]$")


class S3Client(Protocol):
    """boto3 S3 client의 이 모듈이 사용하는 최소 표면."""

    def put_object(self, **kwargs: Any) -> dict[str, Any]: ...


@dataclass(frozen=True, slots=True)
class StoredObject:
    """S3 호환 저장소에 기록한 원본 객체의 식별·무결성 메타데이터."""

    bucket: str
    object_key: str
    content_type: str
    byte_size: int
    checksum_sha256: str
    etag: str | None


class RustfsObjectStore:
    """boto3 호환 RustFS client를 async API로 감싼 객체 저장소.

    RustFS/MinIO/AWS S3의 endpoint 차이를 `s3_client` 생성 시점으로 한정한다.
    제공자 파일의 다운로드와 DB 저장은 소비 서비스가 맡고, 이 클래스는 바이트를
    idempotent object key에 보관하는 책임만 가진다.
    """

    def __init__(self, s3_client: S3Client, *, bucket: str, prefix: str = "provider-raw") -> None:
        self.s3_client = s3_client
        self.bucket = _bucket_name(bucket)
        self.prefix = _prefix(prefix)

    @classmethod
    def from_s3_compatible_settings(
        cls,
        *,
        endpoint_url: str,
        bucket: str,
        access_key_id: str,
        secret_access_key: str,
        region_name: str = "us-east-1",
        prefix: str = "provider-raw",
    ) -> "RustfsObjectStore":
        """명시적 공용 RustFS 설정으로 store를 만든다.

        키를 환경에서 자동으로 읽지 않아 provider 호출자가 비밀값의 소유 경계를
        명확히 유지한다. 생성된 boto3 client의 호출은 `put_bytes`에서 thread로 실행한다.
        """
        endpoint = _endpoint_url(endpoint_url)
        if not access_key_id.strip() or not secret_access_key.strip():
            raise KricInvalidParameterError("RustFS access key and secret key must not be blank")
        boto3 = importlib.import_module("boto3")
        client = boto3.client(
            "s3",
            endpoint_url=endpoint,
            aws_access_key_id=access_key_id,
            aws_secret_access_key=secret_access_key,
            region_name=region_name,
        )
        return cls(client, bucket=bucket, prefix=prefix)

    async def put_bytes(
        self,
        *,
        object_key: str,
        body: bytes,
        content_type: str = "application/octet-stream",
    ) -> StoredObject:
        """바이트를 저장하고 SHA-256 기반 무결성 메타데이터를 반환한다."""
        key = _object_key(object_key)
        if not isinstance(body, bytes) or not body:
            raise KricInvalidParameterError("RustFS object body must be non-empty bytes")
        content_type = content_type.strip() or "application/octet-stream"
        checksum = hashlib.sha256(body).hexdigest()
        try:
            response = await asyncio.to_thread(
                self.s3_client.put_object,
                Bucket=self.bucket,
                Key=key,
                Body=body,
                ContentType=content_type,
                Metadata={"sha256": checksum},
            )
        except Exception as exc:  # boto3 client의 구체 오류는 호출자 dependency에 노출하지 않는다.
            raise KricNetworkError("RustFS object upload failed") from exc
        etag = response.get("ETag") if isinstance(response, dict) else None
        return StoredObject(
            bucket=self.bucket,
            object_key=key,
            content_type=content_type,
            byte_size=len(body),
            checksum_sha256=checksum,
            etag=str(etag) if etag is not None else None,
        )

    def prefixed_key(self, *parts: str) -> str:
        """provider가 공유 prefix 아래의 결정적 object key를 만들 때 사용한다."""
        suffix = "/".join(_object_key(part) for part in parts)
        return f"{self.prefix}/{suffix}" if self.prefix else suffix


def _endpoint_url(value: str) -> str:
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc or parsed.username or parsed.password:
        raise KricInvalidParameterError("RustFS endpoint_url must be an http(s) URL without credentials")
    return value.rstrip("/")


def _bucket_name(value: str) -> str:
    bucket = value.strip()
    if not _BUCKET_RE.fullmatch(bucket):
        raise KricInvalidParameterError("RustFS bucket must be a valid S3 bucket name")
    return bucket


def _prefix(value: str) -> str:
    if not isinstance(value, str):
        raise KricInvalidParameterError("RustFS prefix must be a string")
    return value.strip().strip("/")


def _object_key(value: str) -> str:
    if not isinstance(value, str):
        raise KricInvalidParameterError("RustFS object_key must be a string")
    key = value.strip().strip("/")
    if not key or ".." in key.split("/"):
        raise KricInvalidParameterError("RustFS object_key must be a non-empty relative path")
    return key
