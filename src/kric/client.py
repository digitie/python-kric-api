"""KRIC Open API의 JSON 요청과 오류 envelope를 처리한다."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import httpx

from .exceptions import (
    KricAuthError,
    KricInvalidParameterError,
    KricNetworkError,
    KricRateLimitError,
    KricServerError,
)
from .models import (
    ServiceDayCode,
    StationFacility,
    StationInfo,
    StationTimetableEntry,
    SubwayRouteStop,
    SubwayTimetableEntry,
)
from .parse import (
    parse_many,
    parse_station_facility,
    parse_station_info,
    parse_station_timetable_entry,
    parse_subway_route_stop,
    parse_subway_timetable_entry,
)

BASE_URL = "https://openapi.kric.go.kr/openapi"


class KricClient:
    """KRIC JSON API client. 호출자는 async with로 수명주기를 관리한다."""

    def __init__(
        self,
        service_key: str,
        *,
        base_url: str = BASE_URL,
        timeout: float = 30.0,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        key = service_key.strip()
        if not key:
            raise KricInvalidParameterError("service_key must not be blank")
        if timeout <= 0:
            raise KricInvalidParameterError("timeout must be positive")
        self.service_key = key
        self.base_url = base_url.rstrip("/")
        self._client = client or httpx.AsyncClient(timeout=timeout)
        self._owns_client = client is None

    async def __aenter__(self) -> "KricClient":
        return self

    async def __aexit__(self, *_: object) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        """내부에서 만든 HTTP client만 닫는다."""
        if self._owns_client:
            await self._client.aclose()

    async def get_station_info(
        self,
        *,
        rail_operator_code: str | None = None,
        line_code: str | None = None,
        station_code: str | None = None,
        station_name: str | None = None,
    ) -> tuple[StationInfo, ...]:
        """역 위치·주소·다국어 명칭을 반환한다. 최소 하나의 역 선택 인자가 필요하다."""
        params = _station_params(rail_operator_code, line_code, station_code, station_name)
        return parse_many(await self._get("convenientInfo/stationInfo", params), parse_station_info)

    async def get_subway_route_info(
        self, *, metro_area_code: str, line_code: str
    ) -> tuple[SubwayRouteStop, ...]:
        """권역·노선의 구성역을 route code별 station sequence 순서로 반환한다."""
        rows = parse_many(await self._get("trainUseInfo/subwayRouteInfo", {
            "mreaWideCd": _required(metro_area_code, "metro_area_code"),
            "lnCd": _required(line_code, "line_code"),
        }), parse_subway_route_stop)
        return tuple(sorted(rows, key=lambda row: (row.route_code or "", row.station_sequence or 0)))

    async def get_station_timetable(
        self, *, rail_operator_code: str, line_code: str, station_code: str, day_code: ServiceDayCode | str
    ) -> tuple[StationTimetableEntry, ...]:
        """역 기준 시간표를 원시 시각 문자열과 공식 요일 코드로 반환한다."""
        return parse_many(await self._get("convenientInfo/stationTimetable", _timetable_params(
            rail_operator_code, line_code, station_code, day_code
        )), parse_station_timetable_entry)

    async def get_subway_timetable(
        self, *, rail_operator_code: str, line_code: str, station_code: str, day_code: ServiceDayCode | str
    ) -> tuple[SubwayTimetableEntry, ...]:
        """도시철도 열차별 시간표를 원시 시각 문자열과 공식 요일 코드로 반환한다."""
        return parse_many(await self._get("trainUseInfo/subwayTimetable", _timetable_params(
            rail_operator_code, line_code, station_code, day_code
        )), parse_subway_timetable_entry)

    async def get_station_facilities(
        self, *, rail_operator_code: str, line_code: str, station_code: str
    ) -> tuple[StationFacility, ...]:
        """역 편의시설 항목을 확인된 식별자와 모든 원시 필드로 반환한다."""
        params = {
            "railOprIsttCd": _required(rail_operator_code, "rail_operator_code"),
            "lnCd": _required(line_code, "line_code"),
            "stinCd": _required(station_code, "station_code"),
        }
        return parse_many(await self._get("convenientInfo/stationCnvFacl", params), parse_station_facility)

    async def _get(self, operation: str, params: Mapping[str, str]) -> Mapping[str, Any]:
        request_params = {"serviceKey": self.service_key, "format": "json", **params}
        try:
            response = await self._client.get(f"{self.base_url}/{operation}", params=request_params)
        except httpx.HTTPError as exc:
            raise KricNetworkError("KRIC request failed") from exc
        if response.status_code in (401, 403):
            raise KricAuthError(f"KRIC request denied: HTTP {response.status_code}")
        if response.status_code == 429:
            raise KricRateLimitError("KRIC request rate limited: HTTP 429")
        if response.status_code >= 400:
            raise KricServerError(f"KRIC request failed: HTTP {response.status_code}")
        try:
            payload = response.json()
        except ValueError as exc:
            raise KricServerError("KRIC response is not JSON") from exc
        if not isinstance(payload, Mapping):
            raise KricServerError("KRIC JSON response must be an object")
        _raise_for_error_envelope(payload)
        return payload


def _required(value: str, name: str) -> str:
    text = value.strip()
    if not text:
        raise KricInvalidParameterError(f"{name} must not be blank")
    return text


def _station_params(
    rail_operator_code: str | None, line_code: str | None, station_code: str | None, station_name: str | None
) -> dict[str, str]:
    values = {
        "railOprIsttCd": rail_operator_code,
        "lnCd": line_code,
        "stinCd": station_code,
        "stinNm": station_name,
    }
    params = {key: _required(value, key) for key, value in values.items() if value is not None}
    if not params:
        raise KricInvalidParameterError("at least one station selector is required")
    return params


def _timetable_params(
    rail_operator_code: str, line_code: str, station_code: str, day_code: ServiceDayCode | str
) -> dict[str, str]:
    day = _required(str(day_code), "day_code")
    if day not in {member.value for member in ServiceDayCode}:
        raise KricInvalidParameterError("day_code must be one of '7', '8', '9'")
    return {
        "railOprIsttCd": _required(rail_operator_code, "rail_operator_code"),
        "lnCd": _required(line_code, "line_code"),
        "stinCd": _required(station_code, "station_code"),
        "dayCd": day,
    }


def _raise_for_error_envelope(payload: Mapping[str, Any]) -> None:
    header = payload.get("header")
    if not isinstance(header, Mapping):
        return
    code = str(header.get("resultCode") or "").strip()
    if not code or code in {"00", "0", "200"}:
        return
    message = str(header.get("resultMsg") or "KRIC API returned an error")
    normalized = message.lower()
    if "키" in message or "key" in normalized or "인증" in message:
        raise KricAuthError(message)
    if "초과" in message or "limit" in normalized or "quota" in normalized:
        raise KricRateLimitError(message)
    raise KricServerError(message)
