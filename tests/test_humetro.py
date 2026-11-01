"""공식 조회 구조를 줄인 합성 fixture. 실제 사이트/시간표와 전체 원문은 별도 확인한다."""
import httpx
import pytest

from kric import HumetroClient, HumetroAuthError, HumetroRateLimitError, HumetroSchemaError, KricInvalidParameterError, KricNetworkError, parse_humetro_timetable_page
from kric.humetro import HUMETRO_TIMETABLE_URL, MAX_HTML_BYTES


def page() -> bytes:
    return b'''<html><select name="S_HO"><option value="1" selected>1</option></select>
    <select name="S_STATION"><option value="100" selected>'''+"동매".encode()+b'''</option><option value="95">'''+"다대포해수욕장".encode()+b'''</option></select>
    <input name="updown" value="0"><a onclick="onUpdown('0'); return false;"></a><a onclick="onUpdown('1'); return false;"></a>
    <table class="timetable-detail"><thead><tr>'''+"<th scope='col'>시간</th><th scope='col'>평일</th><th scope='col'>토요일</th><th scope='col'>일/공휴일</th>".encode()+b'''</tr></thead><tbody>'''+hour("23", ("10", "20", "30"))+hour("00", ("11", "21", "31"))+b'''</tbody></table></html>'''


def hour(value: str, minutes: tuple[str, str, str]) -> bytes:
    return (f'<tr><th scope="row">{value}</th>'+''.join(f'<td><span class="course-mark-5"><span class="blind">다대포해수욕장행</span>{minute}<span class="blind">분 출발</span></span></td>' for minute in minutes)+'</tr>').encode()


def parse(raw: bytes):
    return parse_humetro_timetable_page(raw,line_code="1",station_code="100",direction="0")


def test_weekdays_minute_precision_and_service_midnight():
    result=parse(page())
    assert result.station_code=="100" and result.station_name=="동매" and result.available_directions==("0","1")
    assert [(r.day_code,r.departure_time) for r in result.items]==[("8","23:10"),("7","23:20"),("9","23:30"),("8","24:11"),("7","24:21"),("9","24:31")]
    assert result.items[-1].source_clock=="00:31" and result.items[-1].time_precision=="minute"
    assert all(r.rail_operator_code=="BS" and r.terminal_station_code=="95" for r in result.items)
    assert len(result.checksum_sha256)==64


def test_unknown_or_ambiguous_destination_name_never_guesses_code():
    raw=page().replace('다대포해수욕장</option>'.encode(),'확인불가</option>'.encode())
    assert parse(raw).items[0].terminal_station_code is None


def test_last_train_inline_script_is_not_departure_text():
    # 신평역 공식 표의 막차 안내는 출발 span 안에 script로 삽입된다.
    script = b'<script>$(document).ready(function(){$("#last-train").text("00:37");});</script>'
    raw = page().replace(b'</span></span></td>', b'</span>' + script + b'<style>.x{color:red}</style></span></td>')
    result = parse(raw)
    assert [(v.day_code, v.departure_time) for v in result.items] == [(v.day_code, v.departure_time) for v in parse(page()).items]
    raw=page().replace(b'</select>\n    <input',b'<option value="999">'+"다대포해수욕장".encode()+b'</option></select>\n    <input')
    assert parse(raw).items[0].terminal_station_code is None


@pytest.mark.parametrize("old,new",[
 (b'value="100" selected',b'value="101" selected'),(b'value="1" selected',b'value="2" selected'),
 (b'name="updown" value="0"',b'name="updown" value="1"'),(b'name="S_HO"',b'name="other"'),
 (b'class="timetable-detail"',b'class="other"'),(b'onUpdown',b'notUpdown'),
 (b'>23</th>',b'>30</th>'),(b'>00</th>',b'>23</th>'),(b'>00</th>',b'>22</th>'),
 (b'</td></tr>',b'</td><td></td></tr>'),(b'</span>10<',b'</span>60<'),
 ('토요일'.encode(),'일요일'.encode()),('동매</option>'.encode(),b'</option>'),
])
def test_changed_identity_or_structure_is_error(old,new):
    with pytest.raises(HumetroSchemaError):parse(page().replace(old,new))


def test_multiple_selected_or_multiple_tables_is_error():
    with pytest.raises(HumetroSchemaError):parse(page().replace(b'value="95"',b'selected value="95"'))
    with pytest.raises(HumetroSchemaError):parse(page()+b'<table class="timetable-detail"></table>')


@pytest.mark.parametrize("raw",[b'',b'\xff',b'x'*(MAX_HTML_BYTES+1),b'<div>'*66,b'<br>'*50_001])
def test_document_limits(raw):
    with pytest.raises(HumetroSchemaError):parse(raw)


def test_nested_unrelated_elements_and_closing_tags_are_not_timetable():
    result=parse(b'<!doctype html><div><p>unrelated</p></div></absent>'+page())
    assert len(result.items)==6


def test_row_size_limit_and_empty_valid_direction():
    minute=b'<span class="course-mark-5"><span class="blind">'+"다대포해수욕장행".encode()+b'</span>01<span class="blind">'+"분 출발".encode()+b'</span></span>'
    # 문서 노드 상한 아래에서 시간표 행 상한을 별도로 검산한다.
    raw=page().split(b'<tbody>')[0]+b'<tbody><tr><th scope="row">05</th><td>'+minute*10_001+b'</td><td></td><td></td></tr></tbody></table>'
    with pytest.raises(HumetroSchemaError):parse(raw)
    empty=page().split(b'<tbody>')[0]+b'<tbody></tbody></table>'
    assert parse(empty).items==()


def test_truncated_table_or_row_and_long_labels_rejected():
    for raw in [page().replace(b'</table>',b''),page().replace(b'</td></tr>',b'</td>'),page().replace('동매'.encode(),b'x'*161),page().replace('다대포해수욕장행'.encode(),b'x'*161+'행'.encode())]:
        with pytest.raises(HumetroSchemaError):parse(raw)


@pytest.mark.parametrize("line,station,direction",[("9","100",None),("1","A100",None),("1","100","2")])
def test_invalid_request(line,station,direction):
    with pytest.raises(KricInvalidParameterError):parse_humetro_timetable_page(page(),line_code=line,station_code=station,direction=direction)


@pytest.mark.asyncio
async def test_client_posts_only_public_query_fields_and_does_not_own_injected_client():
    def send(request):
        assert str(request.url)==HUMETRO_TIMETABLE_URL and request.method=="POST"
        assert request.content==b's_ho=1&s_station=100&updown=0'
        assert b'serviceKey' not in request.content
        return httpx.Response(200,content=page(),headers={"Content-Type":"text/html;charset=UTF-8"})
    async with httpx.AsyncClient(transport=httpx.MockTransport(send)) as http:
        async with HumetroClient(client=http) as client:assert len((await client.get_station_page(line_code="1",station_code="100",direction="0")).items)==6
        assert not http.is_closed


@pytest.mark.asyncio
async def test_auto_direction_and_owned_client_lifecycle():
    client=HumetroClient();await client.aclose()
    assert client._client.is_closed
    with pytest.raises(KricInvalidParameterError):HumetroClient(timeout=0)
    def send(request):
        assert b'updown' not in request.content
        return httpx.Response(200,content=page(),headers={"Content-Type":"text/html"})
    async with httpx.AsyncClient(transport=httpx.MockTransport(send)) as http:
        assert (await HumetroClient(client=http).get_station_page(line_code="1",station_code="100")).direction=="0"


@pytest.mark.asyncio
@pytest.mark.parametrize("status,error",[(401,HumetroAuthError),(403,HumetroAuthError),(429,HumetroRateLimitError),(500,HumetroSchemaError),(302,HumetroSchemaError)])
async def test_http_failures_not_empty(status,error):
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda request:httpx.Response(status))) as http:
        with pytest.raises(error):await HumetroClient(client=http).get_station_page(line_code="1",station_code="100")


@pytest.mark.asyncio
@pytest.mark.parametrize("body,content_type",[(b'{}','application/json'),(b'x'*(MAX_HTML_BYTES+1),'text/html')])
async def test_body_limits(body,content_type):
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda request:httpx.Response(200,content=body,headers={'content-type':content_type}))) as http:
        with pytest.raises(HumetroSchemaError):await HumetroClient(client=http).get_station_page(line_code="1",station_code="100")


@pytest.mark.asyncio
async def test_network_failure():
    def send(request):raise httpx.ConnectError('unavailable',request=request)
    async with httpx.AsyncClient(transport=httpx.MockTransport(send)) as http:
        with pytest.raises(KricNetworkError):await HumetroClient(client=http).get_station_page(line_code="1",station_code="100")
