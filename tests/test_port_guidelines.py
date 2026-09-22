from __future__ import annotations

import hashlib

import httpx
import pytest
import respx

from kric import KricInvalidParameterError, KricRateLimitError, KricServerError, PortGuidelineFileClient, RustfsObjectStore, parse_port_guideline_locations
from kric.port_guidelines import PORT_GUIDELINE_LOCATION_URL


def _csv() -> bytes:
    return "테이블 구분,행 구분,위치 순서,항구 명,위도,경도,선수방위,등록자ID,등록 일시\r\n103,3,2,인천,37.11,126.3183333,23,masked,2020-07-31 11:19\r\n".encode("cp949")


def test_port_guideline_parser_preserves_raw_order_and_coordinates() -> None:
    row = parse_port_guideline_locations(_csv())[0]
    assert (row.port_name, row.position_order, row.latitude, row.longitude) == ("인천", "2", 37.11, 126.3183333)
    assert row.raw["등록자ID"] == "masked"


@respx.mock
async def test_port_guideline_download_is_keyless_and_archives_verified_csv() -> None:
    route = respx.get(PORT_GUIDELINE_LOCATION_URL).mock(return_value=httpx.Response(200, content=_csv()))

    class FakeS3:
        def __init__(self) -> None: self.objects: dict[str, dict] = {}
        def put_object(self, **kwargs): self.objects[kwargs["Key"]] = kwargs; return {"ETag": "etag"}
        def close(self) -> None: pass

    store = RustfsObjectStore(FakeS3(), bucket="raw", prefix="provider-raw")
    async with PortGuidelineFileClient() as client:
        locations, stored = await client.get_locations_to_rustfs(store)

    assert route.called and len(locations) == 1
    assert stored.object_key.endswith(hashlib.sha256(_csv()).hexdigest() + ".csv")


def test_port_guideline_parser_rejects_missing_or_invalid_coordinates() -> None:
    with pytest.raises(KricServerError, match="required headers"):
        parse_port_guideline_locations("항구 명,위도\r\n인천,37.1\r\n".encode("cp949"))
    with pytest.raises(KricServerError, match="invalid WGS84"):
        parse_port_guideline_locations("항구 명,위도,경도\r\n인천,91,126\r\n".encode("cp949"))


@respx.mock
async def test_port_guideline_download_rejects_quota_redirect_and_empty_body() -> None:
    route = respx.get(PORT_GUIDELINE_LOCATION_URL)
    async with PortGuidelineFileClient() as client:
        route.mock(return_value=httpx.Response(429))
        with pytest.raises(KricRateLimitError):
            await client.get_locations()
        route.mock(return_value=httpx.Response(302, headers={"location": "https://evil.example/file.csv"}))
        with pytest.raises(KricServerError, match="redirect"):
            await client.get_locations()
        route.mock(return_value=httpx.Response(200, content=b""))
        with pytest.raises(KricServerError, match="empty"):
            await client.get_locations()


def test_port_guideline_client_rejects_invalid_limits() -> None:
    with pytest.raises(KricInvalidParameterError):
        PortGuidelineFileClient(timeout=0)
    with pytest.raises(KricInvalidParameterError):
        PortGuidelineFileClient(max_download_bytes=0)
