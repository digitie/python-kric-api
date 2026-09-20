"""KRIC 공개 파일 데이터의 무인증 다운로드와 XLSX 파싱을 제공한다."""

from __future__ import annotations

from collections.abc import Mapping
from io import BytesIO
from typing import Any
from zipfile import BadZipFile

import httpx
from openpyxl import load_workbook
from openpyxl.utils.exceptions import InvalidFileException

from .exceptions import (
    KricInvalidParameterError,
    KricNetworkError,
    KricRateLimitError,
    KricServerError,
)
from .models import FileStationInfo, KricFileDownload, KricFileTable
from .parse import as_raw_mapping, float_or_none, require_fields, string_or_none

FILE_DOWNLOAD_URL = "https://data.kric.go.kr/rips/dataset/download.file"
NATIONWIDE_STATION_INFO_DATASET_ID = 1294

_STATION_INFO_REQUIRED_HEADERS = (
    "철도운영기관명",
    "운영노선",
    "역 번호",
    "역명(한글)",
)


class KricFileClient:
    """KRIC 공개 파일 client. 인증키·Open API 요청을 사용하지 않는다."""

    def __init__(
        self,
        *,
        download_url: str = FILE_DOWNLOAD_URL,
        timeout: float = 30.0,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        if timeout <= 0:
            raise KricInvalidParameterError("timeout must be positive")
        self.download_url = download_url
        self._client = client or httpx.AsyncClient(timeout=timeout)
        self._owns_client = client is None

    async def __aenter__(self) -> "KricFileClient":
        return self

    async def __aexit__(self, *_: object) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        """내부에서 만든 HTTP client만 닫는다."""
        if self._owns_client:
            await self._client.aclose()

    async def download_dataset(self, *, dataset_id: int, operation: int = 1) -> KricFileDownload:
        """공개 파일을 내려받는다. dataset/operation은 포털 상세 URL의 식별자다."""
        _positive_integer(dataset_id, "dataset_id")
        _positive_integer(operation, "operation")
        try:
            response = await self._client.get(
                self.download_url,
                params={"type": "filedata", "id": str(dataset_id), "operation": str(operation)},
            )
        except httpx.HTTPError as exc:
            raise KricNetworkError("KRIC public-file request failed") from exc
        if response.status_code == 429:
            raise KricRateLimitError("KRIC public-file request rate limited: HTTP 429")
        if response.status_code >= 400:
            raise KricServerError(f"KRIC public-file request failed: HTTP {response.status_code}")
        if not response.content:
            raise KricServerError("KRIC public-file response is empty")
        return KricFileDownload(
            dataset_id=dataset_id,
            operation=operation,
            source_url=str(response.request.url),
            content_type=response.headers.get("content-type"),
            content=response.content,
        )

    async def get_nationwide_station_info(self) -> tuple[FileStationInfo, ...]:
        """무인증 전국 도시광역철도 역사정보(XLSX, dataset 1294)를 파싱한다."""
        download = await self.download_dataset(dataset_id=NATIONWIDE_STATION_INFO_DATASET_ID)
        return parse_nationwide_station_info_xlsx(download.content)


def parse_nationwide_station_info_xlsx(content: bytes) -> tuple[FileStationInfo, ...]:
    """dataset 1294의 첫 worksheet를 typed 역사 기준정보로 변환한다."""
    table = parse_xlsx_table(content)
    missing = [header for header in _STATION_INFO_REQUIRED_HEADERS if header not in table.headers]
    if missing:
        raise KricServerError(
            "KRIC station-info workbook is missing required headers: " + ", ".join(missing)
        )
    return tuple(parse_nationwide_station_info_row(row) for row in table.rows)


def parse_xlsx_table(content: bytes) -> KricFileTable:
    """공개 XLSX의 첫 worksheet를 헤더 기반 원문 table로 읽는다.

    시설별 파일처럼 아직 typed 계약이 확정되지 않은 자료도 이 함수로 안전하게 소비할 수 있다.
    """
    try:
        workbook = load_workbook(BytesIO(content), read_only=True, data_only=True)
    except (BadZipFile, InvalidFileException, OSError, ValueError) as exc:
        raise KricServerError("KRIC public file is not a readable XLSX workbook") from exc
    try:
        if not workbook.worksheets:
            raise KricServerError("KRIC public-file workbook has no worksheet")
        sheet = workbook.worksheets[0]
        rows = sheet.iter_rows(values_only=True)
        try:
            header_values = next(rows)
        except StopIteration as exc:
            raise KricServerError("KRIC public-file workbook is empty") from exc
        headers = tuple(_header_text(value) for value in header_values)
        if not headers or any(header is None for header in headers):
            raise KricServerError("KRIC public-file workbook has a blank header")
        normalized_headers = tuple(header for header in headers if header is not None)
        if len(set(normalized_headers)) != len(normalized_headers):
            raise KricServerError("KRIC public-file workbook has duplicate headers")
        records: list[Mapping[str, str | None]] = []
        for values in rows:
            raw_row = {header: value for header, value in zip(normalized_headers, values, strict=True)}
            if all(value is None or str(value).strip() == "" for value in raw_row.values()):
                continue
            records.append(as_raw_mapping(raw_row))
        return KricFileTable(
            worksheet_title=sheet.title,
            headers=normalized_headers,
            rows=tuple(records),
        )
    finally:
        workbook.close()


def parse_nationwide_station_info_row(row: Mapping[str, Any]) -> FileStationInfo:
    """dataset 1294의 한 행을 파싱한다. 명세 밖 열도 raw에 보존한다."""
    raw = as_raw_mapping(row)
    require_fields(raw, "station-info file row", *_STATION_INFO_REQUIRED_HEADERS)
    return FileStationInfo(
        rail_operator_name=raw.get("철도운영기관명"),
        operating_line_name=raw.get("운영노선"),
        station_type=raw.get("역 종류"),
        station_number=raw.get("역 번호"),
        station_name=raw.get("역명(한글)"),
        english_name=raw.get("역명(영어)"),
        romanized_name=raw.get("역명(로마자)"),
        japanese_name=raw.get("역명(일본어)"),
        simplified_chinese_name=raw.get("역명(중국어간체)"),
        traditional_chinese_name=raw.get("역명(중국어번체)"),
        sub_station_name=raw.get("역명(부역명)"),
        longitude=float_or_none(row.get("역 위치(경도)"), "역 위치(경도)"),
        latitude=float_or_none(row.get("역 위치(위도)"), "역 위치(위도)"),
        lot_address=raw.get("역 주소(지번주소)"),
        road_address=raw.get("역 주소(도로명 주소)"),
        station_phone_number=raw.get("역사 전화번호"),
        data_reference_date=raw.get("데이터 기준일자"),
        raw=raw,
    )


def _header_text(value: object) -> str | None:
    return string_or_none(value)


def _positive_integer(value: int, name: str) -> None:
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        raise KricInvalidParameterError(f"{name} must be a positive integer")
