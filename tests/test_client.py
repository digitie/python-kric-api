import httpx
import pytest
import respx

from kric import (
    KricAuthError,
    KricClient,
    KricInvalidParameterError,
    KricNetworkError,
    KricRateLimitError,
    KricServerError,
    ServiceDayCode,
)
from kric.parse import (
    extract_items,
    float_or_none,
    integer_or_none,
    parse_station_facility,
    parse_subway_timetable_entry,
    service_day_code,
)


@respx.mock
async def test_station_info_sends_documented_json_parameters():
    route = respx.get("https://openapi.kric.go.kr/openapi/convenientInfo/stationInfo").mock(
        return_value=httpx.Response(200, json={"header": {"resultCode": "00"}, "body": {"items": {"item": {
            "railOprIsttCd": "S1", "lnCd": "1", "stinCd": "150", "stinNm": "서울역",
            "stinLocLat": "37.554648", "stinLocLon": "126.970606", "mapCordX": "198000", "mapCordY": "451000",
        }}}})
    )
    async with KricClient("test-key") as client:
        rows = await client.get_station_info(rail_operator_code="S1", line_code="1", station_code="150")

    assert route.called
    assert route.calls[0].request.url.params["format"] == "json"
    assert route.calls[0].request.url.params["serviceKey"] == "test-key"
    assert rows[0].station_code == "150"
    assert rows[0].latitude == 37.554648
    assert rows[0].map_x == "198000"


@respx.mock
async def test_route_keeps_route_groups_order_and_repeated_station():
    respx.get("https://openapi.kric.go.kr/openapi/trainUseInfo/subwayRouteInfo").mock(
        return_value=httpx.Response(200, json={"header": {"resultCode": "00"}, "body": {"items": {"item": [
            {"mreaWideCd": "01", "lnCd": "2", "routCd": "R1", "stinCd": "201", "stinNm": "순환역", "stinConsOrdr": "1"},
            {"mreaWideCd": "01", "lnCd": "2", "routCd": "R1", "stinCd": "201", "stinNm": "순환역", "stinConsOrdr": "44"},
        ]}}})
    )
    async with KricClient("test-key") as client:
        rows = await client.get_subway_route_info(metro_area_code="01", line_code="2")

    assert [(row.route_code, row.station_code, row.station_sequence) for row in rows] == [
        ("R1", "201", 1), ("R1", "201", 44)
    ]


@respx.mock
async def test_timetable_preserves_time_strings_and_day_code():
    respx.get("https://openapi.kric.go.kr/openapi/convenientInfo/stationTimetable").mock(
        return_value=httpx.Response(200, json={"header": {"resultCode": "00"}, "body": {"items": {"item": {
            "railOprIsttCd": "S1", "lnCd": "3", "stinCd": "312", "dayCd": "8", "dayNm": "평일",
            "arvTm": "05:31", "dptTm": "05:32", "orgStinCd": "310", "tmnStinCd": "330", "trnNo": "1001",
        }}}})
    )
    async with KricClient("test-key") as client:
        rows = await client.get_station_timetable(
            rail_operator_code="S1", line_code="3", station_code="312", day_code=ServiceDayCode.WEEKDAY
        )

    row = rows[0]
    assert row.day_code is ServiceDayCode.WEEKDAY
    assert (row.arrival_time, row.departure_time, row.origin_station_code, row.terminal_station_code) == (
        "05:31", "05:32", "310", "330"
    )


@respx.mock
async def test_error_envelope_maps_invalid_service_key():
    respx.get("https://openapi.kric.go.kr/openapi/convenientInfo/stationInfo").mock(
        return_value=httpx.Response(200, json={"header": {"resultCode": "30", "resultMsg": "등록되지 않은 서비스키입니다."}})
    )
    async with KricClient("invalid") as client:
        with pytest.raises(KricAuthError, match="서비스키"):
            await client.get_station_info(station_code="150")


@respx.mock
async def test_error_envelope_maps_quota_message():
    respx.get("https://openapi.kric.go.kr/openapi/convenientInfo/stationInfo").mock(
        return_value=httpx.Response(200, json={"header": {"resultCode": "99", "resultMsg": "호출 횟수 초과"}})
    )
    async with KricClient("test-key") as client:
        with pytest.raises(KricRateLimitError):
            await client.get_station_info(station_code="150")


@respx.mock
@pytest.mark.parametrize(
    ("status_code", "error_type"),
    [(401, KricAuthError), (429, KricRateLimitError), (500, KricServerError)],
)
async def test_http_errors_are_not_treated_as_empty_results(status_code, error_type):
    respx.get("https://openapi.kric.go.kr/openapi/convenientInfo/stationInfo").mock(
        return_value=httpx.Response(status_code)
    )
    async with KricClient("test-key") as client:
        with pytest.raises(error_type):
            await client.get_station_info(station_code="150")


@respx.mock
async def test_non_json_and_network_errors_are_explicit():
    route = respx.get("https://openapi.kric.go.kr/openapi/convenientInfo/stationInfo")
    route.mock(return_value=httpx.Response(200, text="not-json"))
    async with KricClient("test-key") as client:
        with pytest.raises(KricServerError, match="not JSON"):
            await client.get_station_info(station_code="150")

    route.mock(side_effect=httpx.ConnectError("offline"))
    async with KricClient("test-key") as client:
        with pytest.raises(KricNetworkError):
            await client.get_station_info(station_code="150")


@respx.mock
async def test_subway_timetable_and_facilities_keep_documented_codes():
    timetable = respx.get("https://openapi.kric.go.kr/openapi/trainUseInfo/subwayTimetable").mock(
        return_value=httpx.Response(200, json={"header": {"resultCode": "00"}, "response": {"body": {"items": {"item": [{
            "railOprIsttCd": "S1", "lnCd": "1", "stinCd": "0150", "dayCd": "9", "arvTm": "24:01", "dptTm": "24:02", "trnNo": "0007"
        }]}}}})
    )
    facilities = respx.get("https://openapi.kric.go.kr/openapi/convenientInfo/stationCnvFacl").mock(
        return_value=httpx.Response(200, json={"header": {"resultCode": "00"}, "body": {"items": {"item": {
            "railOprIsttCd": "S1", "lnCd": "1", "stinCd": "0150", "facilityCode": "ELV", "unknown": "keep"
        }}}})
    )
    async with KricClient("test-key") as client:
        timetable_rows = await client.get_subway_timetable(
            rail_operator_code="S1", line_code="1", station_code="0150", day_code="9"
        )
        facility_rows = await client.get_station_facilities(
            rail_operator_code="S1", line_code="1", station_code="0150"
        )

    assert timetable.called and facilities.called
    assert timetable_rows[0].day_code is ServiceDayCode.HOLIDAY
    assert timetable_rows[0].departure_time == "24:02"
    assert timetable_rows[0].station_code == "0150"
    assert facility_rows[0].values["unknown"] == "keep"


def test_parser_rejects_bad_shapes_and_numeric_contracts():
    assert extract_items({"items": {"item": {"code": "001"}}}) == ({"code": "001"},)
    assert float_or_none(" ", "latitude") is None
    assert integer_or_none(None, "order") is None
    assert service_day_code("new-code") == "new-code"
    assert parse_subway_timetable_entry({"dayCd": "7", "trnNo": "001"}).train_number == "001"
    assert parse_station_facility({"stinCd": "0150", "blank": " "}).values["blank"] is None
    with pytest.raises(KricServerError, match="numeric"):
        float_or_none("north", "latitude")
    with pytest.raises(KricServerError, match="integer"):
        integer_or_none("first", "order")
    with pytest.raises(KricServerError, match="does not contain"):
        extract_items({"header": {"resultCode": "00"}})


async def test_client_rejects_blank_or_unsafe_requests_before_network():
    with pytest.raises(KricInvalidParameterError):
        KricClient(" ")
    async with KricClient("test-key") as client:
        with pytest.raises(KricInvalidParameterError):
            await client.get_station_info()
        with pytest.raises(KricInvalidParameterError):
            await client.get_subway_route_info(metro_area_code=" ", line_code="1")
        with pytest.raises(KricInvalidParameterError):
            await client.get_station_timetable(
                rail_operator_code="S1", line_code="1", station_code="150", day_code="0"
            )
    with pytest.raises(KricInvalidParameterError):
        KricClient("test-key", timeout=0)
