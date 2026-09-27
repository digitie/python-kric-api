"""비페이지 기준정보 예외가 페이지 손실을 숨기지 않는지 검증한다."""

import httpx
import pytest
from kric import DataGoKrMaritimeClient, KricServerError


@pytest.mark.parametrize('operation,method,row,allowed', [
    ('GetPortList', 'iter_ports', {'nodeId':'P1','nodeNm':'항구'}, False),
    ('GetPsnshipTrminlList', 'iter_ferry_terminals', {'terminalId':'T1','terminalNm':'터미널'}, True),
    ('GetShipKndList', 'iter_ferry_ship_types', {'shipKndId':'S1','shipKndNm':'선박'}, True),
])
@pytest.mark.parametrize('metadata', [{}, {'totalCount':None}, {'pageNo':1}, {'numOfRows':1}])
async def test_countless_references_are_only_verified_unpaged_operations(operation, method, row, allowed, metadata):
    calls = []
    def respond(request):
        calls.append(request.url.path)
        return httpx.Response(200, json={'response':{'header':{'resultCode':'00'},
            'body':{'items':{'item':[row]}, **metadata}}})
    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http:
        async with DataGoKrMaritimeClient('test-key', client=http) as client:
            if allowed and not metadata:
                assert len([item async for item in getattr(client,method)(page_size=1)]) == 1
            else:
                with pytest.raises(KricServerError, match='totalCount'):
                    _ = [item async for item in getattr(client,method)(page_size=1)]
    assert calls == ['/1613000/DmstcShipNvgInfo/'+operation]


@pytest.mark.parametrize('header', [None, {}, {'resultCode':''}])
async def test_unpaged_requires_explicit_success_header(header):
    payload={'response':{'header':header,'body':{'items':{'item':{'terminalId':'T1','terminalNm':'터미널'}}}}}
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda r:httpx.Response(200,json=payload))) as http:
        async with DataGoKrMaritimeClient('test-key', client=http) as client:
            with pytest.raises(KricServerError, match='totalCount'):
                _ = [item async for item in client.iter_ferry_terminals()]


async def test_count_cannot_disappear_on_second_terminal_page():
    calls = 0
    def respond(request):
        nonlocal calls
        calls += 1
        body={'items':{'item':{'terminalId':str(calls),'terminalNm':'터미널'}}}
        if calls == 1: body['totalCount']=2
        return httpx.Response(200,json={'response':{'header':{'resultCode':'00'},'body':body}})
    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http:
        async with DataGoKrMaritimeClient('test-key', client=http) as client:
            with pytest.raises(KricServerError, match='after pagination began'):
                _ = [item async for item in client.iter_ferry_terminals(page_size=1)]
    assert calls == 2
