import pytest

from kric import parse_station_file_facilities
from kric.files import parse_nationwide_station_info_row


def test_file_facilities_preserve_explicit_positive_flags_without_changing_raw():
    raw = {"철도운영기관명": "공항철도", "운영노선": "공항철도선", "역 번호": "A01", "역명(한글)": "서울역",
        "환승역 여부": "가능", "스크린도어 설치유무": "있음", "유실물 취급여부": "없음", "안전발판 유무": None,
        "승강장 연결여부": "있음", "역사 전화번호": "032-745-7400"}
    parsed = parse_nationwide_station_info_row(raw)
    assert parsed.facilities == ("환승 가능", "스크린도어", "승강장 연결")
    assert parsed.raw == raw
    assert parsed.station_phone_number == "032-745-7400"
    assert parse_station_file_facilities(raw) == parsed.facilities


@pytest.mark.parametrize("value", [None, "", "없음", "불가능", "알수없음", "Y", "가능", True, 1])
def test_unknown_or_negative_values_are_not_reported_as_present(value):
    assert parse_station_file_facilities({"스크린도어 설치유무": value}) == ()


def test_trimmed_verified_positive_values_are_supported():
    assert parse_station_file_facilities({"안전발판 유무": " 있음 "}) == ("안전발판",)
