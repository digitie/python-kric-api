from __future__ import annotations

import asyncio
import hashlib
import threading

import pytest
from botocore.exceptions import ClientError

from kric import (
    KricAuthError,
    KricInvalidParameterError,
    KricStorageConfigurationError,
    RustfsObjectStore,
)


class FakeS3Client:
    def __init__(self) -> None:
        self.objects: dict[tuple[str, str], dict] = {}
        self.close_calls = 0

    def put_object(self, **kwargs):
        self.objects[(kwargs["Bucket"], kwargs["Key"])] = kwargs
        return {"ETag": '"etag-1"'}

    def close(self) -> None:
        self.close_calls += 1


@pytest.mark.asyncio
async def test_rustfs_store_puts_bytes_with_async_contract() -> None:
    client = FakeS3Client()
    store = RustfsObjectStore(client, bucket="kor-travel-raw", prefix="provider-raw")

    stored = await store.put_bytes(
        object_key=store.prefixed_key("kric", "dataset-1294", "station.xlsx"),
        body=b"station-data",
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )

    assert stored.bucket == "kor-travel-raw"
    assert stored.object_key == "provider-raw/kric/dataset-1294/station.xlsx"
    assert stored.checksum_sha256 == hashlib.sha256(b"station-data").hexdigest()
    assert client.objects[(stored.bucket, stored.object_key)]["Metadata"] == {"sha256": stored.checksum_sha256}


@pytest.mark.parametrize("object_key", ["", "/", "../secret", "a/../secret"])
@pytest.mark.asyncio
async def test_rustfs_store_rejects_unsafe_object_keys(object_key: str) -> None:
    store = RustfsObjectStore(FakeS3Client(), bucket="kor-travel-raw")

    with pytest.raises(KricInvalidParameterError):
        await store.put_bytes(object_key=object_key, body=b"x")


def test_rustfs_factory_requires_https_unless_explicit_internal_opt_in() -> None:
    with pytest.raises(KricStorageConfigurationError, match="HTTPS"):
        RustfsObjectStore.from_s3_compatible_settings(
            endpoint_url="http://127.0.0.1:12101",
            bucket="kor-travel-raw",
            access_key_id="access",
            secret_access_key="secret",
        )
    store = RustfsObjectStore.from_s3_compatible_settings(
        endpoint_url="http://127.0.0.1:12101",
        bucket="kor-travel-raw",
        access_key_id="access",
        secret_access_key="secret",
        allow_insecure_http=True,
    )
    assert store.bucket == "kor-travel-raw"


@pytest.mark.asyncio
async def test_rustfs_store_classifies_auth_errors_and_closes_once() -> None:
    class DeniedClient(FakeS3Client):
        def put_object(self, **kwargs):
            raise ClientError(
                {"Error": {"Code": "AccessDenied"}, "ResponseMetadata": {"HTTPStatusCode": 403}},
                "PutObject",
            )

    client = DeniedClient()
    store = RustfsObjectStore(client, bucket="kor-travel-raw")
    with pytest.raises(KricAuthError):
        await store.put_bytes(object_key="file", body=b"x")

    await store.aclose()
    await store.aclose()
    assert client.close_calls == 1
    with pytest.raises(KricStorageConfigurationError, match="closed"):
        await store.put_bytes(object_key="file", body=b"x")


@pytest.mark.asyncio
async def test_rustfs_store_classifies_missing_bucket_as_configuration_error() -> None:
    class MissingBucketClient(FakeS3Client):
        def put_object(self, **kwargs):
            raise ClientError(
                {"Error": {"Code": "NoSuchBucket"}, "ResponseMetadata": {"HTTPStatusCode": 404}},
                "PutObject",
            )

    store = RustfsObjectStore(MissingBucketClient(), bucket="kor-travel-raw")
    with pytest.raises(KricStorageConfigurationError, match="bucket"):
        await store.put_bytes(object_key="file", body=b"x")


@pytest.mark.asyncio
async def test_rustfs_store_waits_for_admitted_upload_before_closing() -> None:
    class BlockingClient(FakeS3Client):
        def __init__(self) -> None:
            super().__init__()
            self.started = threading.Event()
            self.release = threading.Event()

        def put_object(self, **kwargs):
            self.started.set()
            assert self.release.wait(timeout=2)
            return super().put_object(**kwargs)

    client = BlockingClient()
    store = RustfsObjectStore(client, bucket="kor-travel-raw")
    upload = asyncio.create_task(store.put_bytes(object_key="file", body=b"x"))
    assert await asyncio.to_thread(client.started.wait, 2)

    closing = asyncio.create_task(store.aclose())
    await asyncio.sleep(0)
    assert client.close_calls == 0

    client.release.set()
    await upload
    await closing
    assert client.close_calls == 1


@pytest.mark.asyncio
async def test_rustfs_store_drains_cancelled_caller_worker_before_closing() -> None:
    class BlockingClient(FakeS3Client):
        def __init__(self) -> None:
            super().__init__()
            self.started = threading.Event()
            self.release = threading.Event()

        def put_object(self, **kwargs):
            self.started.set()
            assert self.release.wait(timeout=2)
            return super().put_object(**kwargs)

    client = BlockingClient()
    store = RustfsObjectStore(client, bucket="kor-travel-raw")
    upload = asyncio.create_task(store.put_bytes(object_key="file", body=b"x"))
    assert await asyncio.to_thread(client.started.wait, 2)
    upload.cancel()
    with pytest.raises(asyncio.CancelledError):
        await upload

    closing = asyncio.create_task(store.aclose())
    await asyncio.sleep(0)
    assert client.close_calls == 0
    client.release.set()
    await closing
    assert client.close_calls == 1
