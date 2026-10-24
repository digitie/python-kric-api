"""코레일 공개 역 안내와 공개 역 좌표. 예약·로그인 API는 사용하지 않는다."""
from __future__ import annotations

import asyncio
import math
import time
from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass, replace
from typing import Any, Literal

import httpx

from .exceptions import KricAuthError, KricInvalidParameterError, KricNetworkError, KricRateLimitError, KricServerError

GuideKind = Literal["ktx", "main"]
_STATIONS = "https://www.korail.com/public/st_info/station_data.json"
_GUIDE = "https://www.korail.com/com/userStation.do"


@dataclass(frozen=True, slots=True)
class KorailPublicStation:
    """코레일 공개 역 코드. TAGO nodeid와 동일한 코드가 아니다."""
    station_code: str
    station_name: str
    longitude: float | None
    latitude: float | None


@dataclass(frozen=True, slots=True)
class KorailGuideCategory:
    """KTX는 노선, 일반철도는 권역 분류다. 실제 운행 순서를 뜻하지 않는다."""
    code: str
    name: str
    kind: GuideKind


@dataclass(frozen=True, slots=True)
class KorailStationGuide:
    station_sequence: str
    station_name: str
    address: str | None
    phone: str | None
    category_codes: tuple[str, ...]
    station_code: str | None = None
    longitude: float | None = None
    latitude: float | None = None


@dataclass(frozen=True, slots=True)
class KorailGuidePage:
    kind: GuideKind
    page: int
    total: int
    stations: tuple[KorailStationGuide, ...]
    categories: tuple[KorailGuideCategory, ...]


def _text(value: Any, field: str, *, required: bool = False) -> str | None:
    if value is not None and not isinstance(value, str):
        raise KricServerError(f"KORAIL {field} must be text")
    result = value.strip() if value else None
    if required and not result:
        raise KricServerError(f"KORAIL {field} is missing")
    return result or None


def _list(value: Any, field: str) -> list[Mapping[str, Any]]:
    if not isinstance(value, list) or any(not isinstance(row, Mapping) for row in value):
        raise KricServerError(f"KORAIL {field} must be a list of objects")
    return value


def _integer(value: Any, field: str) -> int:
    if isinstance(value, int) and not isinstance(value, bool) and 0 <= value < 10**20:
        return value
    if not isinstance(value, str) or len(value) > 20 or not value.isascii() or not value.isdecimal():
        raise KricServerError(f"KORAIL {field} must be a nonnegative integer")
    return int(value)


def parse_korail_public_stations(payload: Mapping[str, Any]) -> tuple[KorailPublicStation, ...]:
    root = payload.get("stns")
    if not isinstance(root, Mapping):
        raise KricServerError("KORAIL station root is missing")
    result = []
    seen = set()
    lon: float | None
    lat: float | None
    for row in _list(root.get("stn"), "stns.stn"):
        code = _text(row.get("stn_cd"), "stn_cd", required=True)
        name = _text(row.get("stn_nm"), "stn_nm", required=True)
        assert code and name
        if code in seen:
            raise KricServerError("KORAIL station code is duplicated")
        seen.add(code)
        try:
            lon, lat = float(row["longitude"]), float(row["latitude"])
            if isinstance(row["longitude"], bool) or isinstance(row["latitude"], bool) or not (math.isfinite(lon) and math.isfinite(lat) and -180 <= lon <= 180 and -90 <= lat <= 90):
                lon = lat = None
        except (KeyError, ValueError, TypeError, OverflowError):
            lon = lat = None
        result.append(KorailPublicStation(code, name, lon, lat))
    if not result:
        raise KricServerError("KORAIL station catalog is empty")
    return tuple(result)


def parse_korail_guide_page(payload: Mapping[str, Any], *, kind: GuideKind, page: int) -> KorailGuidePage:
    if payload.get("strResult") != "SUCC":
        raise KricServerError("KORAIL station guide did not report success")
    total = _integer(payload.get("totcnt"), "totcnt")
    lines = []
    for row in _list(payload.get("lineList"), "lineList"):
        code = _text(row.get("ccode"), "ccode", required=True)
        name = _text(row.get("cname"), "cname", required=True)
        assert code and name
        lines.append(KorailGuideCategory(code, name, kind))
    stations = []
    for row in _list(payload.get("resultList"), "resultList"):
        raw_sequence = row.get("stationSeq")
        if _integer(raw_sequence, "stationSeq") < 1:
            raise KricServerError("KORAIL stationSeq must be positive")
        sequence = str(raw_sequence)
        name = _text(row.get("title"), "title", required=True)
        assert name
        codes = _text(row.get("ktxLine" if kind == "ktx" else "mainLine"), "line codes") or ""
        stations.append(KorailStationGuide(sequence, name, _text(row.get("addr"), "addr"),
            _text(row.get("tel"), "tel"), tuple(code.strip() for code in codes.split(",") if code.strip())))
    if len(stations) > total or total and not stations:
        raise KricServerError("KORAIL station guide page is incomplete")
    return KorailGuidePage(kind, page, total, tuple(stations), tuple(lines))


class KorailPublicClient:
    """공개 안내 전용 키 없는 client. 요청 간 최소 1초, redirect·자동 재시도 없음."""
    def __init__(self, *, timeout: float = 30) -> None:
        self._client = httpx.AsyncClient(timeout=timeout, follow_redirects=False)
        self._lock = asyncio.Lock()
        self._last_request: float | None = None

    async def __aenter__(self) -> KorailPublicClient:
        return self

    async def __aexit__(self, *_: Any) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        await self._client.aclose()

    async def _get(self, url: str, params: dict[str, str] | None = None) -> Mapping[str, Any]:
        async with self._lock:
            if self._last_request is not None:
                await asyncio.sleep(max(0, 1 - (time.monotonic() - self._last_request)))
            self._last_request = time.monotonic()
            try:
                async with self._client.stream("GET", url, params=params) as response:
                    if response.status_code in {401, 403}:
                        raise KricAuthError("KORAIL public station access denied")
                    if response.status_code == 429:
                        raise KricRateLimitError("KORAIL public station request rate limited")
                    if response.status_code != 200:
                        raise KricServerError(f"KORAIL public station request failed: HTTP {response.status_code}")
                    content = bytearray()
                    async for chunk in response.aiter_bytes():
                        content.extend(chunk)
                        if len(content) > 1024 * 1024:
                            raise KricServerError("KORAIL public station response exceeds 1 MiB")
            except httpx.HTTPError:
                raise KricNetworkError("KORAIL public station request failed") from None
        try:
            import json
            payload = json.loads(content)
        except (ValueError, UnicodeError):
            raise KricServerError("KORAIL public station response is not JSON") from None
        if not isinstance(payload, Mapping):
            raise KricServerError("KORAIL public station response must be an object")
        return payload

    async def get_stations(self) -> tuple[KorailPublicStation, ...]:
        return parse_korail_public_stations(await self._get(_STATIONS))

    async def get_guide_page(self, *, kind: GuideKind, page: int = 1, category_code: str = "") -> KorailGuidePage:
        if kind not in {"ktx", "main"} or isinstance(page, bool) or not isinstance(page, int) or not 1 <= page <= 50 or len(category_code) > 40 or not all(ch.isascii() and (ch.isalnum() or ch == "_") for ch in category_code):
            raise KricInvalidParameterError("KORAIL guide kind/page/line is invalid")
        payload = await self._get(_GUIDE, {"mode": "list", "page": str(page), "schOpt2": kind, "schStr": "", "schFld": category_code})
        return parse_korail_guide_page(payload, kind=kind, page=page)

    async def get_category_stations(self, *, kind: GuideKind, category_code: str, max_pages: int = 10) -> KorailGuidePage:
        if not category_code or isinstance(max_pages, bool) or not isinstance(max_pages, int) or not 1 <= max_pages <= 50:
            raise KricInvalidParameterError("KORAIL line and max_pages are required")
        first = await self.get_guide_page(kind=kind, category_code=category_code)
        if category_code not in {row.code for row in first.categories}:
            raise KricInvalidParameterError("KORAIL guide category does not exist")
        stations = list(first.stations)
        def validate_rows() -> None:
            if len(stations) > first.total or len({row.station_sequence for row in stations}) != len(stations):
                raise KricServerError("KORAIL guide contains duplicated or excess stations")
            if any(category_code not in row.category_codes for row in stations):
                raise KricServerError("KORAIL guide contains a station outside the requested category")
        validate_rows()
        for page_no in range(2, max_pages + 1):
            if len(stations) == first.total:
                break
            page = await self.get_guide_page(kind=kind, page=page_no, category_code=category_code)
            if page.total != first.total or page.categories != first.categories:
                raise KricServerError("KORAIL guide changed during pagination")
            stations.extend(page.stations)
            validate_rows()
        if len(stations) != first.total or len({row.station_sequence for row in stations}) != len(stations):
            raise KricServerError("KORAIL guide pagination is incomplete or duplicated")
        if any(category_code not in row.category_codes for row in stations):
            raise KricServerError("KORAIL guide contains a station outside the requested category")
        return KorailGuidePage(kind, 1, first.total, tuple(stations), first.categories)


    async def get_located_category_stations(self, *, kind: GuideKind, category_code: str) -> KorailGuidePage:
        """공개 안내에 포함된 역에만 동일 제공자의 유일한 역명 좌표를 연결한다."""
        page = await self.get_category_stations(kind=kind, category_code=category_code)
        locations = await self.get_stations()
        guide_name_counts = Counter(item.station_name for item in page.stations)
        by_name: dict[str, list[KorailPublicStation]] = {}
        for location_row in locations:
            by_name.setdefault(location_row.station_name, []).append(location_row)
        stations = []
        for item in page.stations:
            candidates = by_name.get(item.station_name, [])
            if len(candidates) == 1 and guide_name_counts[item.station_name] == 1:
                location = candidates[0]
                item = replace(item, station_code=location.station_code,
                    longitude=location.longitude, latitude=location.latitude)
            stations.append(item)
        return replace(page, stations=tuple(stations))
