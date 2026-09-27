"""2026-09-27 성공 응답에서 축약한 공개 역·시간표 구조의 오프라인 회귀."""
import httpx
import pytest
import respx

from kric import KricClient, KricServerError
from kric.parse import extract_items


@respx.mock
async def test_actual_station_body_array():
    # 실제 34행 응답 중 한 행만 보존하고 resultCnt도 축약 행 수에 맞춘다.
    respx.get("https://openapi.kric.go.kr/openapi/convenientInfo/stationInfo").respond(
        json={"header": {"resultCnt": 1, "resultCode": "00"}, "body": [{
            "railOprIsttCd": "S1", "lnCd": "3", "stinCd": "312", "stinNm": "불광",
            "stinLocLon": 126.930183, "stinLocLat": 37.610154,
        }]},
    )
    async with KricClient("test-key") as client:
        rows = await client.get_station_info(rail_operator_code="S1", line_code="3")
    assert len(rows) == 1
    assert rows[0].station_name == "불광"
    assert rows[0].latitude == 37.610154


@respx.mock
async def test_actual_timetable_body_array_preserves_midnight_seconds():
    # 실제 344행 응답의 첫 행. 서비스 날짜/다음날 여부는 제공자 층에서 추정하지 않는다.
    respx.get("https://openapi.kric.go.kr/openapi/convenientInfo/stationTimetable").respond(
        json={"header": {"resultCnt": 1, "resultCode": "00"}, "body": [{
            "railOprIsttCd": "S1", "trnNo": "S3364", "dayCd": "9", "dayNm": "휴일",
            "stinCd": "312", "lnCd": "3", "arvTm": "000000", "dptTm": "000030",
            "orgStinCd": "342", "tmnStinCd": "310",
        }]},
    )
    async with KricClient("test-key") as client:
        rows = await client.get_station_timetable(
            rail_operator_code="S1", line_code="3", station_code="312", day_code="9",
        )
    assert rows[0].arrival_time == "000000"
    assert rows[0].departure_time == "000030"
    assert rows[0].terminal_station_code == "310"


@pytest.mark.parametrize("count", [0, "0", "00", None])
def test_explicit_empty_body(count):
    assert extract_items({"header": {"resultCnt": count}, "body": []}) == ()


@pytest.mark.parametrize("count", [True, False, -1, 0.5, "-1", "x", "1.0", "١", "1", 1])
def test_invalid_or_mismatched_count(count):
    with pytest.raises(KricServerError):
        extract_items({"header": {"resultCnt": count}, "body": []})


@pytest.mark.parametrize("body", [[None], [1], ["row"], [{}, None], None, "", {}])
def test_invalid_body_is_not_empty_success(body):
    with pytest.raises(KricServerError):
        extract_items({"header": {"resultCnt": 0}, "body": body})


def test_success_array_without_optional_count_and_legacy_item_remain_supported():
    assert extract_items({"body": [{"code": "001"}]}) == ({"code": "001"},)
    assert extract_items({"body": {"items": {"item": []}}}) == ()


def test_count_does_not_depend_on_python_integer_conversion_limit():
    assert extract_items({"header": {"resultCnt": "0" * 5000}, "body": []}) == ()
    with pytest.raises(KricServerError):
        extract_items({"header": {"resultCnt": "9" * 5000}, "body": []})


@respx.mock
@pytest.mark.parametrize("header", [None, [], "bad", {}, {"resultCnt": 0, "resultMsg": "server error"}, [{"resultCode": "99"}],
    {"resultCode": False}, {"resultCode": True}, {"resultCode": []},
    {"resultCode": None}, {"resultCode": {}}, {"resultCode": 0.0},
    {"resultCode": ""}, {"resultCode": " "}])
async def test_malformed_error_header_cannot_be_saved_as_empty_success(header):
    respx.get("https://openapi.kric.go.kr/openapi/convenientInfo/stationInfo").respond(
        json={"header": header, "body": []},
    )
    async with KricClient("test-key") as client:
        with pytest.raises(KricServerError):
            await client.get_station_info(station_code="312")


@respx.mock
async def test_array_without_status_header_is_not_success():
    respx.get("https://openapi.kric.go.kr/openapi/convenientInfo/stationInfo").respond(json={"body": []})
    async with KricClient("test-key") as client:
        with pytest.raises(KricServerError):
            await client.get_station_info(station_code="312")
