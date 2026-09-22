"""무인증 해양수산부 항만가이드라인 CSV의 비동기 다운로드·파싱 경계."""

from __future__ import annotations

import csv
import hashlib
from io import StringIO
from math import isfinite
from typing import Any, Mapping

import httpx

from .exceptions import KricInvalidParameterError, KricNetworkError, KricRateLimitError, KricServerError
from .models import PortGuidelineLocation
from .parse import as_raw_mapping, float_or_none, require_fields
from .storage import RustfsObjectStore, StoredObject

PORT_GUIDELINE_LOCATION_URL = (
    "https://www.data.go.kr/cmm/cmm/fileDownload.do?"
    "atchFileId=FILE_000000003666431&fileDetailSn=1&insertDataPrcus=N"
)
PORT_GUIDELINE_SOURCE_ID = "15121268"
DEFAULT_MAX_PORT_GUIDELINE_BYTES = 2 * 1024 * 1024
_REQUIRED_HEADERS = ("항구 명", "위도", "경도")


class PortGuidelineFileClient:
    """서비스키 없이 고정된 공식 CSV를 받아 RustFS에 보관할 수 있는 client."""

    def __init__(
        self,
        *,
        timeout: float = 30.0,
        max_download_bytes: int = DEFAULT_MAX_PORT_GUIDELINE_BYTES,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        if isinstance(timeout, bool) or not isinstance(timeout, (int, float)) or not isfinite(timeout) or timeout <= 0:
            raise KricInvalidParameterError("timeout must be positive")
        if isinstance(max_download_bytes, bool) or not isinstance(max_download_bytes, int) or max_download_bytes <= 0:
            raise KricInvalidParameterError("max_download_bytes must be positive")
        self.max_download_bytes = max_download_bytes
        self._client = client or httpx.AsyncClient(timeout=timeout)
        self._owns_client = client is None

    async def __aenter__(self) -> "PortGuidelineFileClient":
        return self

    async def __aexit__(self, *_: object) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def get_locations(self) -> tuple[PortGuidelineLocation, ...]:
        """공개 CSV를 다운로드해 원문 문자열과 WGS84 숫자 좌표를 함께 반환한다."""
        return parse_port_guideline_locations(await self._download())

    async def get_locations_to_rustfs(
        self, store: RustfsObjectStore
    ) -> tuple[tuple[PortGuidelineLocation, ...], StoredObject]:
        """검증한 CSV를 RustFS에 보관한 뒤 같은 bytes에서 파싱한 위치를 반환한다."""
        content = await self._download()
        locations = parse_port_guideline_locations(content)
        checksum = hashlib.sha256(content).hexdigest()
        stored = await store.put_bytes(
            object_key=store.prefixed_key("data-go-kr", f"dataset-{PORT_GUIDELINE_SOURCE_ID}", f"{checksum}.csv"),
            body=content,
            content_type="text/csv",
        )
        return locations, stored

    async def _download(self) -> bytes:
        try:
            async with self._client.stream("GET", PORT_GUIDELINE_LOCATION_URL, follow_redirects=False) as response:
                if response.status_code in (401, 403):
                    raise KricServerError(f"port guideline file request denied: HTTP {response.status_code}")
                if response.status_code == 429:
                    raise KricRateLimitError("port guideline file request rate limited: HTTP 429")
                if 300 <= response.status_code < 400:
                    raise KricServerError(f"port guideline file redirect denied: HTTP {response.status_code}")
                if response.status_code >= 400:
                    raise KricServerError(f"port guideline file request failed: HTTP {response.status_code}")
                chunks = bytearray()
                async for chunk in response.aiter_bytes():
                    chunks.extend(chunk)
                    if len(chunks) > self.max_download_bytes:
                        raise KricServerError("port guideline file response exceeds max_download_bytes")
        except httpx.HTTPError as exc:
            raise KricNetworkError("port guideline file request failed") from exc
        if not chunks:
            raise KricServerError("port guideline file response is empty")
        return bytes(chunks)


def parse_port_guideline_locations(content: bytes) -> tuple[PortGuidelineLocation, ...]:
    """CP949로 제공되는 공식 CSV를 읽는다. 헤더/좌표 불일치는 빈 결과로 숨기지 않는다."""
    if not isinstance(content, bytes) or not content:
        raise KricInvalidParameterError("content must be non-empty bytes")
    try:
        text = content.decode("cp949")
    except UnicodeDecodeError as exc:
        raise KricServerError("port guideline CSV is not CP949") from exc
    reader = csv.DictReader(StringIO(text))
    if reader.fieldnames is None:
        raise KricServerError("port guideline CSV has no header")
    headers = tuple(header.strip() for header in reader.fieldnames if header)
    missing = [header for header in _REQUIRED_HEADERS if header not in headers]
    if missing:
        raise KricServerError("port guideline CSV is missing required headers: " + ", ".join(missing))
    locations: list[PortGuidelineLocation] = []
    for raw_row in reader:
        raw = as_raw_mapping({str(key).strip(): value for key, value in raw_row.items() if key is not None})
        if not any(value and value.strip() for value in raw.values()):
            continue
        require_fields(raw, "port-guideline CSV row", *_REQUIRED_HEADERS)
        latitude = float_or_none(raw.get("위도"), "위도")
        longitude = float_or_none(raw.get("경도"), "경도")
        if latitude is None or longitude is None or not -90 <= latitude <= 90 or not -180 <= longitude <= 180:
            raise KricServerError("port-guideline CSV row has an invalid WGS84 coordinate")
        locations.append(
            PortGuidelineLocation(
                table_kind=raw.get("테이블 구분"), row_kind=raw.get("행 구분"),
                position_order=raw.get("위치 순서"), port_name=raw.get("항구 명"),
                latitude=latitude, longitude=longitude, heading=raw.get("선수방위"),
                registered_at=raw.get("등록 일시"), raw=raw,
            )
        )
    if not locations:
        raise KricServerError("port guideline CSV contains no locations")
    return tuple(locations)
