"""공식 목록의 전체 페이지·식별자·연결 좌표 계약을 합성 응답으로 검증한다."""
from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import pytest
import respx

from kric import KricGeneralStationClient, parse_kric_directory_page
from kric.exceptions import KricAuthError, KricNetworkError, KricRateLimitError, KricServerError
from kric.general_stations import KricDirectoryPage, KricDirectoryRow
from kric.korail_public import KorailStationGuide

URL = "https://file.kric.go.kr/jsp/board/portal/sub05/est/estationList.jsp"


def html(total=12, page=1, *, kind="일반철도"):
    rows = []
    for i in range((page - 1) * 10, min(page * 10, total)):
        rows.append(f'<tr><td class="bd_num">{total-i}</td><td>역{i}</td><td>권역</td><td>테스트 주소</td>'
                    f'<td>{kind}</td><td><a href="https://www.korail.com/ticket/train/stationGuide/station/view?stationSeq={i+1:04d}">상세</a></td></tr>')
    return f'<p>총 <strong>{total}</strong>건 (현재 {page} 페이지 / {(total+9)//10} 페이지)</p><table>' + ''.join(rows) + '</table>'


def test_page_receipt_order_and_identifier_zeroes():
    page = parse_kric_directory_page(html(), kind="general", page=1)
    assert (page.total, page.pages, len(page.rows)) == (12, 2, 10)
    assert page.rows[0].station_sequence == "0001"
    assert parse_kric_directory_page(html(page=2), kind="general", page=2).rows[0].ordinal == 2
    # script/style 안의 가짜 건수는 가시 목록의 receipt로 읽지 않는다.
    assert parse_kric_directory_page('<script>총 999건</script>'+html(total=1), kind="general", page=1).total == 1


@pytest.mark.parametrize("change", [
    lambda s: s.replace('총 <strong>12</strong>건', '목록'),
    lambda s: s.replace('현재 1 페이지', '현재 2 페이지'),
    lambda s: s.replace('/ 2 페이지', '/ 3 페이지'),
    lambda s: s.replace('>12</td>', '>11</td>'),
    lambda s: s.replace('일반철도', '광역철도'),
    lambda s: s.replace('www.korail.com', 'example.invalid'),
    lambda s: s.replace('stationSeq=0001', 'stationSeq=x'),
    lambda s: s.replace('stationSeq=0001', 'stationSeq=1&amp;stationSeq=2'),
    lambda s: s.replace('<td>역0</td>', '<td></td>'),
    lambda s: s.replace('<td>테스트 주소</td>', ''),
    lambda s: s[:s.rfind('<tr>')],
])
def test_broken_page_never_becomes_a_partial_success(change):
    with pytest.raises(KricServerError): parse_kric_directory_page(change(html()), kind="general", page=1)


@pytest.mark.parametrize("page", [True, 0, 101, "1"])
def test_invalid_page_is_rejected(page):
    with pytest.raises(ValueError): parse_kric_directory_page(html(), kind="general", page=page)


def test_no_detail_link_preserves_the_directory_row():
    text = html(total=1).replace('href="https://www.korail.com/ticket/train/stationGuide/station/view?stationSeq=0001"', '')
    assert parse_kric_directory_page(text, kind="general", page=1).rows[0].station_sequence is None
    with pytest.raises(KricServerError): parse_kric_directory_page(html(total=0), kind="general", page=1)


@pytest.mark.asyncio
@pytest.mark.parametrize(("status", "error"), [(401,KricAuthError),(403,KricAuthError),(429,KricRateLimitError),(500,KricServerError),(302,KricServerError)])
async def test_http_failures_are_not_retried_or_empty(status, error):
    with respx.mock as mock:
        route = mock.get(URL).mock(return_value=httpx.Response(status))
        async with KricGeneralStationClient() as client:
            with pytest.raises(error): await client.get_page(kind="general")
        assert route.call_count == 1


@pytest.mark.asyncio
async def test_bounded_http_encoding_network_and_page_parameters(monkeypatch):
    monkeypatch.setattr("kric.general_stations.asyncio.sleep", AsyncMock())
    with respx.mock as mock:
        route = mock.get(URL).mock(return_value=httpx.Response(200, text=html()))
        async with KricGeneralStationClient() as client:
            await client.get_page(kind="general");await client.get_page(kind="general")
            assert route.call_count == 2
            assert route.calls[0].request.url.params["q_train_type_cd"] == "A020240002"
            assert route.calls[0].request.url.params["pageNo"] == "1"
            with pytest.raises(ValueError): await client.get_page(kind="invalid")
        route.mock(return_value=httpx.Response(200, content=b'\xff'))
        async with KricGeneralStationClient() as client:
            with pytest.raises(KricServerError): await client.get_page(kind="general")
        route.mock(return_value=httpx.Response(200, content=b'x'*(1024*1024+1)))
        async with KricGeneralStationClient() as client:
            with pytest.raises(KricServerError): await client.get_page(kind="general")
        route.mock(side_effect=httpx.ConnectError("untrusted details"))
        async with KricGeneralStationClient() as client:
            with pytest.raises(KricNetworkError,match="request failed"): await client.get_page(kind="general")


def fake_directory(monkeypatch, *, changed=False, conflict=False, no_link=False, wrong_name=False, coordinate_conflict=False):
    rows = [KricDirectoryRow(2,"전주","전라권","주소","일반철도",None if no_link else "0001"),
            KricDirectoryRow(1,"순천","전라권","주소","일반철도","0002")]
    async def get_page(self, *, kind, page=1):
        if kind == "general":
            return KricDirectoryPage(2 if not changed or page == 1 else 3,page,2,(rows[page-1],))
        return KricDirectoryPage(1,1,1,(replace(rows[0],kind="KTX역",route_label="전라선",name="다른 역" if conflict else "전주"),))
    monkeypatch.setattr(KricGeneralStationClient,"get_page",get_page)
    class GuideClient:
        def __init__(self, **_): self._client = SimpleNamespace(event_hooks={"request": []})
        async def __aenter__(self): return self
        async def __aexit__(self,*_): pass
        async def get_located_category_stations(self, *, kind, category_code):
            assert category_code == ""
            return SimpleNamespace(stations=(KorailStationGuide("0001","다른 역" if wrong_name else "전주","공식 전체 주소",None,(),"001",127.1 if kind=="main" or not coordinate_conflict else 128.0,37.5),))
    monkeypatch.setattr("kric.general_stations.KorailPublicClient",GuideClient)


@pytest.mark.asyncio
async def test_full_directory_deduplicates_official_link_and_preserves_routes(monkeypatch):
    fake_directory(monkeypatch)
    async with KricGeneralStationClient() as client: rows = await client.get_general_stations()
    assert len(rows) == 2
    jeonju = next(r for r in rows if r.station_name == "전주")
    assert jeonju.reference_id == "korail:0001" and jeonju.station_code == "001"
    assert jeonju.route_labels == ("전라권","전라선") and len(jeonju.directory_rows)==2
    assert (jeonju.latitude,jeonju.longitude)==(37.5,127.1)
    assert jeonju.address=="공식 전체 주소"
    assert next(r for r in rows if r.station_name == "순천").latitude is None


@pytest.mark.asyncio
@pytest.mark.parametrize("option",["changed","conflict","coordinate_conflict"])
async def test_changed_or_conflicting_sources_fail_closed(monkeypatch,option):
    fake_directory(monkeypatch,**{option:True})
    async with KricGeneralStationClient() as client:
        with pytest.raises(KricServerError): await client.get_general_stations()


@pytest.mark.asyncio
@pytest.mark.parametrize("option",["no_link","wrong_name"])
async def test_unconfirmed_link_never_acquires_a_coordinate_by_name(monkeypatch,option):
    fake_directory(monkeypatch,**{option:True})
    async with KricGeneralStationClient() as client: rows=await client.get_general_stations()
    assert all(r.latitude is None and r.longitude is None for r in rows)


@pytest.mark.asyncio
async def test_request_guard_aborts_before_http():
    def stop(): raise RuntimeError("lease revoked")
    with respx.mock as router:
        route = router.get("https://file.kric.go.kr/jsp/board/portal/sub05/est/estationList.jsp").mock(return_value=httpx.Response(200, text=html(total=1)))
        async with KricGeneralStationClient(before_request=stop) as client:
            with pytest.raises(RuntimeError, match="lease revoked"):
                await client.get_page(kind="general")
        assert route.call_count == 0
