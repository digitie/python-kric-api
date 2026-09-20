"""KRIC JSON envelope와 항목을 공개 모델로 변환한다."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any, TypeVar

from .exceptions import KricServerError
from .models import (
    ServiceDayCode,
    StationFacility,
    StationInfo,
    StationTimetableEntry,
    SubwayRouteStop,
    SubwayTimetableEntry,
)

T = TypeVar("T")


def string_or_none(value: Any) -> str | None:
    """KRIC의 빈 문자열을 None으로 정규화하되 코드의 선행 0은 보존한다."""
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def float_or_none(value: Any, field_name: str) -> float | None:
    """문서화된 위경도 숫자를 float으로 변환한다."""
    text = string_or_none(value)
    if text is None:
        return None
    try:
        return float(text)
    except ValueError as exc:
        raise KricServerError(f"invalid KRIC numeric field {field_name}: {text!r}") from exc


def integer_or_none(value: Any, field_name: str) -> int | None:
    """노선 구성 순서처럼 문서화된 정수 필드를 변환한다."""
    text = string_or_none(value)
    if text is None:
        return None
    try:
        return int(text)
    except ValueError as exc:
        raise KricServerError(f"invalid KRIC integer field {field_name}: {text!r}") from exc


def as_raw_mapping(value: Mapping[str, Any]) -> dict[str, str | None]:
    """원시 객체의 값들을 직렬화 가능한 문자열 또는 None으로 보존한다."""
    return {str(key): string_or_none(item) for key, item in value.items()}


def extract_items(payload: Mapping[str, Any]) -> tuple[Mapping[str, Any], ...]:
    """KRIC의 일반적인 JSON envelope에서 item 하나 또는 목록을 꺼낸다."""
    candidates: list[Any] = [payload]
    for key in ("response", "body", "items"):
        candidates.extend(
            item[key] for item in tuple(candidates) if isinstance(item, Mapping) and key in item
        )
    for candidate in candidates:
        if not isinstance(candidate, Mapping):
            continue
        item = candidate.get("item")
        if isinstance(item, Mapping):
            return (item,)
        if isinstance(item, list) and all(isinstance(row, Mapping) for row in item):
            return tuple(item)
    raise KricServerError("KRIC response does not contain an item object or item list")


def service_day_code(value: Any) -> ServiceDayCode | str | None:
    """공식 7/8/9 코드는 enum으로, 새 provider 값은 문자열로 보존한다."""
    code = string_or_none(value)
    if code is None:
        return None
    try:
        return ServiceDayCode(code)
    except ValueError:
        return code


def parse_station_info(row: Mapping[str, Any]) -> StationInfo:
    raw = as_raw_mapping(row)
    return StationInfo(
        rail_operator_code=raw.get("railOprIsttCd"), line_code=raw.get("lnCd"),
        station_code=raw.get("stinCd"), station_name=raw.get("stinNm"),
        lot_address=raw.get("lonmAdr"), road_address=raw.get("roadNmAdr"),
        latitude=float_or_none(row.get("stinLocLat"), "stinLocLat"),
        longitude=float_or_none(row.get("stinLocLon"), "stinLocLon"),
        map_x=raw.get("mapCordX"), map_y=raw.get("mapCordY"),
        administrative_zone_code=raw.get("strkZone"), english_name=raw.get("stinNmEng"),
        romanized_name=raw.get("stinNmRom"), japanese_name=raw.get("stinNmJpn"),
        simplified_chinese_name=raw.get("stinNmSimpcina"),
        traditional_chinese_name=raw.get("stinNmTradcina"), raw=raw,
    )


def parse_subway_route_stop(row: Mapping[str, Any]) -> SubwayRouteStop:
    raw = as_raw_mapping(row)
    return SubwayRouteStop(
        metro_area_code=raw.get("mreaWideCd"), rail_operator_code=raw.get("railOprIsttCd"),
        line_code=raw.get("lnCd"), route_code=raw.get("routCd"), route_name=raw.get("routNm"),
        station_code=raw.get("stinCd"), station_name=raw.get("stinNm"),
        station_sequence=integer_or_none(row.get("stinConsOrdr"), "stinConsOrdr"), raw=raw,
    )


def parse_station_timetable_entry(row: Mapping[str, Any]) -> StationTimetableEntry:
    raw = as_raw_mapping(row)
    return StationTimetableEntry(
        rail_operator_code=raw.get("railOprIsttCd"), line_code=raw.get("lnCd"),
        station_code=raw.get("stinCd"), day_code=service_day_code(raw.get("dayCd")),
        day_name=raw.get("dayNm"), arrival_time=raw.get("arvTm"), departure_time=raw.get("dptTm"),
        origin_station_code=raw.get("orgStinCd"), terminal_station_code=raw.get("tmnStinCd"),
        train_number=raw.get("trnNo"), raw=raw,
    )


def parse_subway_timetable_entry(row: Mapping[str, Any]) -> SubwayTimetableEntry:
    raw = as_raw_mapping(row)
    return SubwayTimetableEntry(
        rail_operator_code=raw.get("railOprIsttCd"), line_code=raw.get("lnCd"),
        station_code=raw.get("stinCd"), day_code=service_day_code(raw.get("dayCd")),
        day_name=raw.get("dayNm"), arrival_time=raw.get("arvTm"), departure_time=raw.get("dptTm"),
        train_number=raw.get("trnNo"), raw=raw,
    )


def parse_station_facility(row: Mapping[str, Any]) -> StationFacility:
    raw = as_raw_mapping(row)
    return StationFacility(
        rail_operator_code=raw.get("railOprIsttCd"), line_code=raw.get("lnCd"),
        station_code=raw.get("stinCd"), values=raw,
    )


def parse_many(
    payload: Mapping[str, Any], parser: Callable[[Mapping[str, Any]], T]
) -> tuple[T, ...]:
    """공통 envelope 추출 후 항목별 parser를 적용한다."""
    return tuple(parser(row) for row in extract_items(payload))
