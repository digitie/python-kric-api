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


@dataclass(frozen=True, slots=True)
class FileStationInfo:
    """공개 XLSX 역사정보 한 건.

    파일의 운영기관명·운영노선·역 번호는 Open API의 코드 필드와 별개다. 제공자가
    코드라고 명시하지 않은 표시값을 API 식별자로 추정하지 않는다.
    """

    rail_operator_name: str | None
    operating_line_name: str | None
    station_type: str | None
    station_number: str | None
    station_name: str | None
    english_name: str | None
    romanized_name: str | None
    japanese_name: str | None
    simplified_chinese_name: str | None
    traditional_chinese_name: str | None
    sub_station_name: str | None
    longitude: float | None
    latitude: float | None
    lot_address: str | None
    road_address: str | None
    station_phone_number: str | None
    data_reference_date: str | None
    raw: Mapping[str, str | None] = field(default_factory=dict, repr=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "raw", _freeze_raw(self.raw))


@dataclass(frozen=True, slots=True)
class KricFileDownload:
    """인증키 없이 내려받은 KRIC 공개 파일과 출처 식별자."""

    dataset_id: int
    operation: int
    source_url: str
    content_type: str | None
    content: bytes = field(repr=False)


@dataclass(frozen=True, slots=True)
class DomesticFerryPort:
    """TAGO 국내선박운항정보의 출항·도착 항구 식별자."""

    port_id: str | None
    port_name: str | None
    raw: Mapping[str, str | None] = field(default_factory=dict, repr=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "raw", _freeze_raw(self.raw))


@dataclass(frozen=True, slots=True)
class FerryTerminal:
    """TAGO 여객선 터미널 기준정보."""

    terminal_id: str | None
    terminal_name: str | None
    address: str | None
    telephone: str | None
    raw: Mapping[str, str | None] = field(default_factory=dict, repr=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "raw", _freeze_raw(self.raw))


@dataclass(frozen=True, slots=True)
class FerryShipType:
    """TAGO 여객선 종류 기준정보."""

    ship_type_id: str | None
    ship_type_name: str | None
    raw: Mapping[str, str | None] = field(default_factory=dict, repr=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "raw", _freeze_raw(self.raw))


@dataclass(frozen=True, slots=True)
class DomesticShipOperation:
    """출항 항구·계획일 기준의 국내 여객선 운항 계획. 시각과 요금은 원문 문자열이다."""

    vessel_name: str | None
    departure_port_name: str | None
    arrival_port_name: str | None
    departure_planned_time: str | None
    arrival_planned_time: str | None
    fare: str | None
    raw: Mapping[str, str | None] = field(default_factory=dict, repr=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "raw", _freeze_raw(self.raw))


@dataclass(frozen=True, slots=True)
class CoastalFerrySchedule:
    """KOMSA 연안여객선 운항 스케줄. 날짜·시각·코드는 제공 원문을 보존한다."""

    schedule_date: str | None
    departure_time: str | None
    vessel_code: str | None
    vessel_name: str | None
    departure_port_code: str | None
    departure_port_name: str | None
    destination_port_code: str | None
    destination_port_name: str | None
    licensed_route_code: str | None
    licensed_route_name: str | None
    operating_route_code: str | None
    operating_route_name: str | None
    direction_code: str | None
    direction_name: str | None
    operation_type_code: str | None
    operation_type_name: str | None
    operation_status_code: str | None
    operation_status_name: str | None
    control_reason_code: str | None
    control_reason_name: str | None
    non_operation_reason_code: str | None
    non_operation_reason_name: str | None
    vessel_number: str | None
    cancellation_other_reason: str | None
    route_category_code: str | None
    route_category_name: str | None
    raw: Mapping[str, str | None] = field(default_factory=dict, repr=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "raw", _freeze_raw(self.raw))


@dataclass(frozen=True, slots=True)
class KricFileTable:
    """공개 XLSX 첫 worksheet의 헤더와 원문 행."""

    worksheet_title: str
    headers: tuple[str, ...]
    rows: tuple[Mapping[str, str | None], ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "rows", tuple(_freeze_raw(row) for row in self.rows))
