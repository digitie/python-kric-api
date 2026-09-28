"""기항지 요청·좌표·불완전 응답·오류 계약을 검증한다."""

import httpx
import pytest

from kric import DataGoKrMaritimeClient, KricInvalidParameterError, KricRateLimitError, KricServerError


ROW = {"portcl_cd": "D000", "portcl_nm": "인천", "admdst_ctpv_cd": "28",
       "admdst_ctpv_nm": "인천광역시", "admdst_sgg_nm": "제물포구", "lat": 37.4557, "lot": 126.598}


async def query(payload):
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda r: httpx.Response(200, json=payload))) as http:
        async with DataGoKrMaritimeClient("test-key", client=http) as client:
            return await client.get_port_calls(name="인천", province="인천광역시")


def envelope(row, total=1):
    return {"header": {"resultCode": "200"}, "body": {"items": {"item": [row]}, "totalCount": total}}


async def test_request_and_coordinates():
    calls = []
    def respond(request):
        calls.append(request)
        return httpx.Response(200, json=envelope(ROW))
    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http:
        async with DataGoKrMaritimeClient("test-key", client=http) as client:
            item, = await client.get_port_calls(name="인천", province="인천광역시")
    assert len(calls) == 1
    assert calls[0].url.path == "/B554035/port-call-info-v2/get-port-call-info-v2"
    assert dict(calls[0].url.params) == {"serviceKey": "test-key", "dataType": "JSON", "pageNo": "1", "numOfRows": "100", "portclNm": "인천", "admdstCtpvNm": "인천광역시"}
    assert (item.port_code, item.latitude, item.longitude) == ("D000", 37.4557, 126.598)
    with pytest.raises(TypeError):
        item.raw["lat"] = "0"


@pytest.mark.parametrize("lat,lon", [("NaN", 126), (37, "inf"), (91, 126), (37, 181), (126, 37), (None, 126), ("", 126), ("bad", 126)])
async def test_invalid_coordinates_keep_raw_but_clear_pair(lat, lon):
    item, = await query(envelope({**ROW, "lat": lat, "lot": lon}))
    assert (item.latitude, item.longitude) == (None, None)
    assert "lat" in item.raw


@pytest.mark.parametrize("total", [0, 2, None, -1, "bad"])
async def test_incomplete_or_invalid_count(total):
    with pytest.raises(KricServerError):
        await query(envelope(ROW, total))


async def test_not_found_is_empty_and_quota_is_not_empty():
    assert await query({"header": {"resultCode": "153"}}) == ()
    with pytest.raises(KricRateLimitError):
        await query({"header": {"resultCode": "117"}})


@pytest.mark.parametrize("name,province", [("", "인천광역시"), ("인천", " "), (None, "인천광역시")])
async def test_required_filters_fail_before_network(name, province):
    async with DataGoKrMaritimeClient("test-key") as client:
        with pytest.raises(KricInvalidParameterError):
            await client.get_port_calls(name=name, province=province)


@pytest.mark.parametrize("field", ["portcl_cd", "portcl_nm", "admdst_ctpv_cd", "admdst_ctpv_nm", "lat", "lot"])
async def test_missing_schema_is_not_empty(field):
    row = dict(ROW)
    del row[field]
    with pytest.raises(KricServerError):
        await query(envelope(row))
