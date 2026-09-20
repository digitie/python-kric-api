from __future__ import annotations

import hashlib

import pytest

from kric import KricInvalidParameterError, RustfsObjectStore


class FakeS3Client:
    def __init__(self) -> None:
        self.objects: dict[tuple[str, str], dict] = {}

    def put_object(self, **kwargs):
        self.objects[(kwargs["Bucket"], kwargs["Key"])] = kwargs
        return {"ETag": '"etag-1"'}


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
