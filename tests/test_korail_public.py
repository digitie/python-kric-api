import httpx
import pytest
import respx

from kric import KorailPublicClient, KricAuthError, KricInvalidParameterError, KricRateLimitError, KricServerError, parse_korail_public_stations, parse_korail_guide_page


def payload(items=None, total=1):
    return {"strResult": "SUCC", "totcnt": total, "lineList": [{"ccode": "gyeongbu", "cname": "경부선"}],
        "resultList": items if items is not None else [{"stationSeq": "0001", "title": "서울", "addr": "서울특별시", "tel": "1588-7788", "mainLine": "gyeongbu,", "ktxLine": "ktx1,"}]}


def test_guide_keeps_provider_identifiers_routes_and_public_contact():
    result = parse_korail_guide_page(payload(), kind="main", page=1)
    assert result.categories[0].name == "경부선"
    assert result.stations[0].station_sequence == "0001"
    assert result.stations[0].phone == "1588-7788"
    assert result.stations[0].category_codes == ("gyeongbu",)


@pytest.mark.parametrize("update", [{"strResult": "FAIL"}, {"totcnt": None}, {"totcnt": True}, {"resultList": None}, {"resultList": []}, {"lineList": None}])
def test_bad_guide_contract_does_not_turn_into_a_normal_empty_result(update):
    with pytest.raises(KricServerError):
        parse_korail_guide_page({**payload(), **update}, kind="main", page=1)


def test_explicit_empty_guide_is_preserved():
    assert parse_korail_guide_page(payload([], total=0), kind="main", page=1).stations == ()


def test_public_coordinates_and_codes_are_not_guessed():
    rows = parse_korail_public_stations({"stns": {"stn": [
        {"stn_cd": "0001", "stn_nm": "서울", "longitude": "126.97", "latitude": "37.55"},
        {"stn_cd": "0002", "stn_nm": "위치 미제공", "longitude": "NaN", "latitude": "37.55"},
    ]}})
    assert rows[0].station_code == "0001" and rows[0].longitude == 126.97
    assert rows[1].longitude is None and rows[1].latitude is None


@pytest.mark.asyncio
@respx.mock
async def test_client_reads_only_fixed_public_paths_and_returns_typed_data():
    endpoint = respx.get("https://www.korail.com/com/userStation.do").mock(return_value=httpx.Response(200, json=payload()))
    async with KorailPublicClient() as client:
        page = await client.get_category_stations(kind="main", category_code="gyeongbu")
    assert page.total == 1
    assert endpoint.calls[0].request.url.params["mode"] == "list"
    assert endpoint.calls[0].request.url.params["schFld"] == "gyeongbu"


@pytest.mark.asyncio
@pytest.mark.parametrize("status,error", [(401, KricAuthError), (403, KricAuthError), (429, KricRateLimitError), (302, KricServerError), (500, KricServerError)])
@respx.mock
async def test_denials_are_not_retried_or_followed(status, error):
    endpoint = respx.get("https://www.korail.com/public/st_info/station_data.json").mock(return_value=httpx.Response(status, headers={"location": "https://example.com/"}))
    async with KorailPublicClient() as client:
        with pytest.raises(error):
            await client.get_stations()
    assert endpoint.call_count == 1


@pytest.mark.asyncio
@respx.mock
async def test_incomplete_pagination_fails_instead_of_publishing_first_page():
    respx.get("https://www.korail.com/com/userStation.do").mock(return_value=httpx.Response(200, json=payload(total=2)))
    async with KorailPublicClient() as client:
        with pytest.raises(KricServerError):
            await client.get_category_stations(kind="main", category_code="gyeongbu", max_pages=1)


@pytest.mark.asyncio
async def test_invalid_page_is_rejected_before_network():
    async with KorailPublicClient() as client:
        with pytest.raises(KricInvalidParameterError):
            await client.get_guide_page(kind="main", page=True)


@pytest.mark.asyncio
@respx.mock
async def test_located_guides_use_unique_same_provider_names_only():
    guide = payload(items=[
        {"stationSeq": 1, "title": "서울", "mainLine": "gyeongbu,"},
        {"stationSeq": 2, "title": "중복", "mainLine": "gyeongbu,"},
    ], total=2)
    respx.get("https://www.korail.com/com/userStation.do").mock(return_value=httpx.Response(200, json=guide))
    respx.get("https://www.korail.com/public/st_info/station_data.json").mock(return_value=httpx.Response(200, json={"stns": {"stn": [
        {"stn_cd": "0001", "stn_nm": "서울", "longitude": "126.97", "latitude": "37.55"},
        {"stn_cd": "0002", "stn_nm": "중복", "longitude": "127", "latitude": "36"},
        {"stn_cd": "0003", "stn_nm": "중복", "longitude": "128", "latitude": "35"},
    ]}}))
    async with KorailPublicClient() as client:
        result = await client.get_located_category_stations(kind="main", category_code="gyeongbu")
    assert result.stations[0].station_code == "0001"
    assert result.stations[0].longitude == 126.97
    assert result.stations[1].station_code is None and result.stations[1].longitude is None


@pytest.mark.asyncio
@respx.mock
async def test_pagination_completes_and_rejects_category_drift():
    first = payload(total=2)
    second = payload(items=[{"stationSeq": 2, "title": "부산", "mainLine": "gyeongbu,"}], total=2)
    endpoint = respx.get("https://www.korail.com/com/userStation.do").mock(side_effect=[httpx.Response(200, json=first), httpx.Response(200, json=second)])
    async with KorailPublicClient() as client:
        result = await client.get_category_stations(kind="main", category_code="gyeongbu")
    assert len(result.stations) == 2 and endpoint.call_count == 2
    second["totcnt"] = 3
    endpoint.mock(side_effect=[httpx.Response(200, json=first), httpx.Response(200, json=second)])
    async with KorailPublicClient() as client:
        with pytest.raises(KricServerError):
            await client.get_category_stations(kind="main", category_code="gyeongbu")


@pytest.mark.asyncio
@respx.mock
async def test_bad_body_and_network_errors_are_sanitized():
    from kric import KricNetworkError
    endpoint = respx.get("https://www.korail.com/public/st_info/station_data.json")
    for body in [b"not json", b"[]", b"x" * (1024 * 1024 + 1)]:
        endpoint.mock(return_value=httpx.Response(200, content=body))
        async with KorailPublicClient() as client:
            with pytest.raises(KricServerError):
                await client.get_stations()
    endpoint.mock(side_effect=httpx.ConnectError("private transport detail"))
    async with KorailPublicClient() as client:
        with pytest.raises(KricNetworkError, match="^KORAIL public station request failed$"):
            await client.get_stations()



def test_extreme_numeric_values_stay_inside_provider_contract():
    with pytest.raises(KricServerError):
        parse_korail_guide_page(payload(total="9" * 5000), kind="main", page=1)
    with pytest.raises(KricServerError):
        parse_korail_guide_page(payload(total=10**5000), kind="main", page=1)
    result = parse_korail_public_stations({"stns": {"stn": [{"stn_cd": "0001", "stn_nm": "서울", "longitude": 10**400, "latitude": 37}]}})
    assert result[0].longitude is None


@pytest.mark.asyncio
@respx.mock
async def test_repeating_pages_stop_as_soon_as_duplicate_is_proven():
    endpoint = respx.get("https://www.korail.com/com/userStation.do").mock(return_value=httpx.Response(200, json=payload(total=100)))
    async with KorailPublicClient() as client:
        with pytest.raises(KricServerError):
            await client.get_category_stations(kind="main", category_code="gyeongbu")
    assert endpoint.call_count == 2


@pytest.mark.asyncio
@respx.mock
async def test_duplicate_guide_names_do_not_share_one_coordinate_record():
    guide = payload(items=[{"stationSeq": 1, "title": "동명", "addr": "지역 A", "mainLine": "gyeongbu,"}, {"stationSeq": 2, "title": "동명", "addr": "지역 B", "mainLine": "gyeongbu,"}], total=2)
    respx.get("https://www.korail.com/com/userStation.do").mock(return_value=httpx.Response(200, json=guide))
    respx.get("https://www.korail.com/public/st_info/station_data.json").mock(return_value=httpx.Response(200, json={"stns": {"stn": [{"stn_cd": "0001", "stn_nm": "동명", "longitude": "127", "latitude": "37"}]}}))
    async with KorailPublicClient() as client:
        result = await client.get_located_category_stations(kind="main", category_code="gyeongbu")
    assert all(row.station_code is None and row.longitude is None and row.latitude is None for row in result.stations)
