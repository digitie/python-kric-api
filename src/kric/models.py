"""KRIC 응답을 원시 코드와 순서를 보존해 표현하는 공개 모델."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from types import MappingProxyType
from typing import Mapping


class ServiceDayCode(StrEnum):
    """KRIC 시간표의 공식 요일 코드."""

    SATURDAY = "7"
    WEEKDAY = "8"
    HOLIDAY = "9"


def _freeze_raw(value: Mapping[str, str | None]) -> Mapping[str, str | None]:
    return MappingProxyType(dict(value))


@dataclass(frozen=True, slots=True)
class StationInfo:
    """역 위치·명칭·주소 정보. map coordinate의 CRS는 제공자가 명시하기 전까지 변환하지 않는다."""

    rail_operator_code: str | None
    line_code: str | None
    station_code: str | None
    station_name: str | None
    lot_address: str | None
    road_address: str | None
    latitude: float | None
    longitude: float | None
    map_x: str | None
    map_y: str | None
    administrative_zone_code: str | None
    english_name: str | None
    romanized_name: str | None
    japanese_name: str | None
    simplified_chinese_name: str | None
    traditional_chinese_name: str | None
    raw: Mapping[str, str | None] = field(default_factory=dict, repr=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "raw", _freeze_raw(self.raw))


@dataclass(frozen=True, slots=True)
class SubwayRouteStop:
    """도시철도 노선 구성의 역 한 건. 같은 역의 반복도 노선 계약상 보존한다."""

    metro_area_code: str | None
    rail_operator_code: str | None
    line_code: str | None
    route_code: str | None
    route_name: str | None
    station_code: str | None
    station_name: str | None
    station_sequence: int | None
    raw: Mapping[str, str | None] = field(default_factory=dict, repr=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "raw", _freeze_raw(self.raw))


@dataclass(frozen=True, slots=True)
class StationTimetableEntry:
    """역 기준 시간표. 시각은 KRIC 원문 문자열이며 서비스 날짜를 추정하지 않는다."""

    rail_operator_code: str | None
    line_code: str | None
    station_code: str | None
    day_code: ServiceDayCode | str | None
    day_name: str | None
    arrival_time: str | None
    departure_time: str | None
    origin_station_code: str | None
    terminal_station_code: str | None
    train_number: str | None
    raw: Mapping[str, str | None] = field(default_factory=dict, repr=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "raw", _freeze_raw(self.raw))


@dataclass(frozen=True, slots=True)
class SubwayTimetableEntry:
    """열차별 도시철도 시간표. 시각 형식은 실제 provider fixture가 확정할 때까지 원문으로 둔다."""

    rail_operator_code: str | None
    line_code: str | None
    station_code: str | None
    day_code: ServiceDayCode | str | None
    day_name: str | None
    arrival_time: str | None
    departure_time: str | None
    train_number: str | None
    raw: Mapping[str, str | None] = field(default_factory=dict, repr=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "raw", _freeze_raw(self.raw))


@dataclass(frozen=True, slots=True)
class StationFacility:
    """역 편의시설 원시 항목. 공개 상세 문서가 확정하지 않은 필드는 보존해 제공한다."""

    rail_operator_code: str | None
    line_code: str | None
    station_code: str | None
    values: Mapping[str, str | None]

    def __post_init__(self) -> None:
        object.__setattr__(self, "values", _freeze_raw(self.values))
