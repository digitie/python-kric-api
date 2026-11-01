"""부산교통공사 공식 HTML 시간표. KRIC API 응답과 별개의 공개 원천이다."""
from __future__ import annotations

from dataclasses import dataclass, field
from hashlib import sha256
from html.parser import HTMLParser
import re
from typing import Iterator

import httpx

from .exceptions import KricAuthError, KricInvalidParameterError, KricNetworkError, KricRateLimitError, KricServerError

HUMETRO_TIMETABLE_URL = "https://data.humetro.busan.kr/homepage/default/stationtime/page/view.do?menu_no=10010103"
HUMETRO_SOURCE_URL = "https://data.humetro.busan.kr/homepage/default/stationtime/page/list.do?menu_no=1001010301"
MAX_HTML_BYTES = 2 * 1024 * 1024


class HumetroAuthError(KricAuthError):
    """부산교통공사 원천의 접근 거부. KRIC 서비스키 오류를 의미하지 않는다."""


class HumetroRateLimitError(KricRateLimitError):
    """부산교통공사 원천의 호출 제한."""


class HumetroSchemaError(KricServerError):
    """선택 역·방향·요일 열 또는 시간표 구조가 요청과 다르다."""


@dataclass(frozen=True, slots=True)
class HumetroTimetableEntry:
    """분 단위 출발 계획. 23시 뒤 00시는 서비스 시각24시이며 원래 시각도 보존한다."""

    rail_operator_code: str
    line_code: str
    station_code: str
    station_name: str
    day_code: str
    departure_time: str
    source_clock: str
    destination_name: str
    terminal_station_code: str | None
    direction: str
    time_precision: str = "minute"


@dataclass(frozen=True, slots=True)
class HumetroTimetablePage:
    line_code: str
    station_code: str
    station_name: str
    direction: str
    available_directions: tuple[str, ...]
    items: tuple[HumetroTimetableEntry, ...]
    checksum_sha256: str
    source_url: str = HUMETRO_SOURCE_URL


@dataclass
class _Node:
    tag: str
    attrs: dict[str, str]
    children: list[_Node | str] = field(default_factory=list)
    closed: bool = False

    def walk(self, tag: str) -> Iterator[_Node]:
        for child in self.children:
            if isinstance(child, _Node):
                if child.tag == tag:
                    yield child
                yield from child.walk(tag)

    def text(self) -> str:
        return "".join(child.text() if isinstance(child, _Node) else child for child in self.children)


class _Document(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.root = _Node("root", {})
        self.stack = [self.root]
        self.nodes = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.nodes += 1
        if self.nodes > 50_000 or len(self.stack) > 64:
            raise HumetroSchemaError("HUmetro HTML structure exceeds limits")
        node = _Node(tag, {key: value or "" for key, value in attrs})
        self.stack[-1].children.append(node)
        if tag not in {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"}:
            self.stack.append(node)

    def handle_endtag(self, tag: str) -> None:
        for index in range(len(self.stack) - 1, 0, -1):
            if self.stack[index].tag == tag:
                self.stack[index].closed = True
                del self.stack[index:]
                break

    def handle_data(self, data: str) -> None:
        self.stack[-1].children.append(data)


def _text(node: _Node) -> str:
    return " ".join(node.text().split())


def _one(nodes: list[_Node], description: str) -> _Node:
    if len(nodes) != 1:
        raise HumetroSchemaError(f"HUmetro {description} must occur once")
    return nodes[0]


def parse_humetro_timetable_page(raw: bytes, *, line_code: str, station_code: str,
                                direction: str | None = None) -> HumetroTimetablePage:
    """선택된 코드와 표 열을 검증한다. 모든 요일을 반환하며 절대 날짜는 만들지 않는다."""
    _validate(line_code, station_code, direction)
    if not raw or len(raw) > MAX_HTML_BYTES:
        raise HumetroSchemaError("HUmetro HTML size invalid")
    document = _Document()
    try:
        document.feed(raw.decode("utf-8"))
    except UnicodeDecodeError as error:
        raise HumetroSchemaError("HUmetro HTML is not UTF-8") from error
    root = document.root
    selected: dict[str, _Node] = {}
    station_options: list[_Node] = []
    for name in ("S_HO", "S_STATION"):
        select = _one([node for node in root.walk("select") if node.attrs.get("name") == name], name)
        options = list(select.walk("option"))
        selected[name] = _one([node for node in options if "selected" in node.attrs], "selected " + name)
        if name == "S_STATION":
            station_options = options
    if selected["S_HO"].attrs.get("value") != line_code or selected["S_STATION"].attrs.get("value") != station_code:
        raise HumetroSchemaError("HUmetro selected station identity mismatch")
    station_name = _text(selected["S_STATION"])
    if not station_name or len(station_name) > 160:
        raise HumetroSchemaError("HUmetro station name absent")
    chosen = _one([node for node in root.walk("input") if node.attrs.get("name") == "updown"], "direction").attrs.get("value", "")
    available: set[str] = set()
    for node in root.walk("a"):
        match = re.fullmatch(r"\s*onUpdown\(['\"]([01])['\"]\);\s*return false;?\s*", node.attrs.get("onclick", ""))
        if match:
            available.add(match[1])
    if chosen not in {"0", "1"} or chosen not in available or direction is not None and chosen != direction:
        raise HumetroSchemaError("HUmetro direction identity mismatch")
    table = _one([node for node in root.walk("table") if "timetable-detail" in node.attrs.get("class", "").split()], "timetable")
    if not table.closed:
        raise HumetroSchemaError("HUmetro timetable is incomplete")
    headers = [_text(node) for node in table.walk("th") if node.attrs.get("scope") == "col"]
    if headers != ["시간", "평일", "토요일", "일/공휴일"]:
        raise HumetroSchemaError("HUmetro weekday columns changed")
    names: dict[str, list[str]] = {}
    for option in station_options:
        names.setdefault(_text(option), []).append(option.attrs.get("value", ""))
    items: list[HumetroTimetableEntry] = []
    previous = -1
    offset = 0
    for row in table.walk("tr"):
        hours = [node for node in row.walk("th") if node.attrs.get("scope") == "row"]
        if not hours:
            continue
        if not row.closed:
            raise HumetroSchemaError("HUmetro hour row is incomplete")
        hour_text = _text(_one(hours, "hour"))
        if not re.fullmatch(r"[0-2][0-9]", hour_text) or int(hour_text) > 23:
            raise HumetroSchemaError("HUmetro clock hour invalid")
        hour = int(hour_text)
        if hour < previous:
            if previous != 23 or hour != 0 or offset:
                raise HumetroSchemaError("HUmetro service-hour order changed")
            offset = 24
        if hour == previous or hour + offset > 29:
            raise HumetroSchemaError("HUmetro repeated service hour")
        previous = hour
        cells = [node for node in row.children if isinstance(node, _Node) and node.tag == "td"]
        if len(cells) != 3:
            raise HumetroSchemaError("HUmetro weekday cell count changed")
        for day, cell in zip(("8", "7", "9"), cells):
            for node in cell.walk("span"):
                if not any(re.fullmatch(r"course-mark-\d+", part) for part in node.attrs.get("class", "").split()):
                    continue
                match = re.fullmatch(r"(.+?)행\s*([0-5][0-9])\s*분\s*출발", _text(node))
                if not match:
                    raise HumetroSchemaError("HUmetro departure minute invalid")
                destination, minute = match.groups()
                if len(destination) > 160:
                    raise HumetroSchemaError("HUmetro destination exceeds limit")
                matching_codes = names.get(destination, [])
                items.append(HumetroTimetableEntry("BS", line_code, station_code, station_name, day,
                    f"{hour + offset:02d}:{minute}", f"{hour:02d}:{minute}", destination,
                    matching_codes[0] if len(matching_codes) == 1 else None, chosen))
                if len(items) > 10_000:
                    raise HumetroSchemaError("HUmetro timetable exceeds row limit")
    return HumetroTimetablePage(line_code, station_code, station_name, chosen, tuple(sorted(available)), tuple(items), sha256(raw).hexdigest())


def _validate(line: str, station: str, direction: str | None) -> None:
    if line not in {"1", "2", "3", "4"} or not re.fullmatch(r"[0-9]{2,4}", station) or direction not in {None, "0", "1"}:
        raise KricInvalidParameterError("HUmetro line, station or direction invalid")


class HumetroClient:
    """인증키 없는 공식 조회 form만 호출한다. 평가·회원 form이나 KRIC API는 호출하지 않는다."""

    def __init__(self, *, timeout: float = 30, client: httpx.AsyncClient | None = None) -> None:
        if timeout <= 0:
            raise KricInvalidParameterError("timeout must be positive")
        self._client = client or httpx.AsyncClient(timeout=timeout)
        self._owns_client = client is None

    async def __aenter__(self) -> HumetroClient:
        return self

    async def __aexit__(self, *_: object) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def get_station_page(self, *, line_code: str, station_code: str,
                               direction: str | None = None) -> HumetroTimetablePage:
        """한 방향의 평일·토요일·공휴일 표를 한 번 읽는다. 다른 방향의 재호출은 소비자가 제어한다."""
        _validate(line_code, station_code, direction)
        data = {"s_ho": line_code, "s_station": station_code}
        if direction is not None:
            data["updown"] = direction
        try:
            async with self._client.stream("POST", HUMETRO_TIMETABLE_URL, data=data) as response:
                if response.status_code in {401, 403}:
                    raise HumetroAuthError("HUmetro access denied")
                if response.status_code == 429:
                    raise HumetroRateLimitError("HUmetro rate limited")
                if response.status_code != 200:
                    raise HumetroSchemaError(f"HUmetro HTTP {response.status_code}")
                if "text/html" not in response.headers.get("content-type", "").lower():
                    raise HumetroSchemaError("HUmetro response is not HTML")
                content = bytearray()
                async for chunk in response.aiter_bytes():
                    content.extend(chunk)
                    if len(content) > MAX_HTML_BYTES:
                        raise HumetroSchemaError("HUmetro response exceeds size limit")
        except httpx.HTTPError as error:
            raise KricNetworkError("HUmetro request failed") from error
        return parse_humetro_timetable_page(bytes(content), line_code=line_code, station_code=station_code, direction=direction)
