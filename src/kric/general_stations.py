"""KRIC 일반철도·KTX 역 목록과 공식 연결 역 안내를 완결 수집한다."""
from __future__ import annotations

import asyncio
import hashlib
import json
import math
import re
from dataclasses import dataclass
from html.parser import HTMLParser
from time import monotonic
from collections.abc import Callable
from typing import Any, Literal
from urllib.parse import parse_qs, urlsplit

import httpx

from .exceptions import KricAuthError, KricNetworkError, KricRateLimitError, KricServerError
from .korail_public import GuideKind, KorailPublicClient, KorailStationGuide

DirectoryKind = Literal["general", "ktx"]
_URL = "https://file.kric.go.kr/jsp/board/portal/sub05/est/estationList.jsp"
_KINDS = {"general": ("A020240002", "일반철도"), "ktx": ("A020240001", "KTX역")}


@dataclass(frozen=True, slots=True)
class KricDirectoryRow:
    ordinal: int
    name: str
    route_label: str
    address: str
    kind: str
    station_sequence: str | None


@dataclass(frozen=True, slots=True)
class KricDirectoryPage:
    total: int
    page: int
    pages: int
    rows: tuple[KricDirectoryRow, ...]


@dataclass(frozen=True, slots=True)
class KricGeneralStation:
    reference_id: str
    station_name: str
    station_sequence: str | None
    station_code: str | None
    route_labels: tuple[str, ...]
    station_kinds: tuple[str, ...]
    address: str | None
    latitude: float | None
    longitude: float | None
    directory_rows: tuple[KricDirectoryRow, ...]


class _DirectoryParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.text: list[str] = []
        self.rows: list[tuple[list[str], str | None]] = []
        self.cells: list[str] = []
        self.cell: list[str] | None = None
        self.link: str | None = None
        self.numbered = False
        self.hidden = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        if tag in {"script", "style"}: self.hidden += 1
        if tag == "tr": self.cells, self.link, self.numbered = [], None, False
        if tag == "td":
            self.cell = []
            self.numbered |= "bd_num" in (values.get("class") or "").split()
        if tag == "a" and self.cell is not None and len(self.cells) == 5:
            self.link = values.get("href")

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style"}: self.hidden = max(0, self.hidden - 1)
        if tag == "td" and self.cell is not None:
            self.cells.append(" ".join("".join(self.cell).split())); self.cell = None
        if tag == "tr" and self.numbered:
            self.rows.append((self.cells, self.link))

    def handle_data(self, value: str) -> None:
        if not self.hidden: self.text.append(value)
        if self.cell is not None and not self.hidden: self.cell.append(value)


def parse_kric_directory_page(html: str, *, kind: DirectoryKind, page: int) -> KricDirectoryPage:
    if kind not in _KINDS or type(page) is not int or not 1 <= page <= 100:
        raise ValueError("KRIC directory kind/page is invalid")
    parser = _DirectoryParser(); parser.feed(html)
    found = re.findall(r"총\s*([\d,]+)\s*건\s*\(현재\s*(\d+)\s*페이지\s*/\s*(\d+)\s*페이지\)", " ".join(parser.text))
    if len(found) != 1: raise KricServerError("KRIC directory count receipt is missing")
    total, actual, pages = (int(v.replace(",", "")) for v in found[0])
    if not 0 < total <= 10000 or actual != page or pages != math.ceil(total / 10) or page > pages:
        raise KricServerError("KRIC directory page/count receipt is inconsistent")
    if len(parser.rows) != min(10, total - (page - 1) * 10):
        raise KricServerError("KRIC directory page is incomplete")
    rows = []
    for offset, (cells, link) in enumerate(parser.rows):
        if len(cells) != 6 or not cells[0].isascii() or not cells[0].isdigit():
            raise KricServerError("KRIC directory columns are invalid")
        ordinal = int(cells[0])
        if ordinal != total - (page - 1) * 10 - offset or not cells[1] or cells[4] != _KINDS[kind][1]:
            raise KricServerError("KRIC directory order/name/kind is inconsistent")
        sequence = None
        if link:
            url = urlsplit(link)
            if (url.scheme != "https" or url.hostname != "www.korail.com"
                    or url.path != "/ticket/train/stationGuide/station/view"):
                raise KricServerError("KRIC directory detail link is outside the official contract")
            values = parse_qs(url.query).get("stationSeq", [])
            if len(values) != 1 or not values[0].isascii() or not values[0].isdigit() or len(values[0]) > 40:
                raise KricServerError("KRIC directory detail identifier is invalid")
            sequence = values[0]
        rows.append(KricDirectoryRow(ordinal, cells[1], cells[2], cells[3], cells[4], sequence))
    return KricDirectoryPage(total, page, pages, tuple(rows))


class KricGeneralStationClient:
    """KRIC이 회원 인증 없이 공개하는 목록. 좌표는 KRIC의 코레일 공식 연결만 사용한다."""
    def __init__(self, *, timeout: float = 30, before_request: Callable[[], None] | None = None) -> None:
        self._before_request = before_request
        self._client = httpx.AsyncClient(timeout=timeout, follow_redirects=False, event_hooks={"request": [self._guard]})
        self._timeout = timeout
        self._lock = asyncio.Lock()
        self._last: float | None = None

    async def __aenter__(self) -> KricGeneralStationClient: return self
    async def __aexit__(self, *_: Any) -> None: await self.aclose()
    async def aclose(self) -> None: await self._client.aclose()

    async def _guard(self, request: httpx.Request) -> None:
        if self._before_request is not None:
            self._before_request()

    async def get_page(self, *, kind: DirectoryKind, page: int = 1) -> KricDirectoryPage:
        if kind not in _KINDS or type(page) is not int or not 1 <= page <= 100:
            raise ValueError("KRIC directory kind/page is invalid")
        async with self._lock:
            if self._last is not None: await asyncio.sleep(max(0, 1 - (monotonic() - self._last)))
            try:
                async with self._client.stream("GET", _URL, params={"q_train_type_cd": _KINDS[kind][0], "pageNo": str(page)}) as response:
                    if response.status_code in (401, 403): raise KricAuthError("KRIC directory access denied")
                    if response.status_code == 429: raise KricRateLimitError("KRIC directory rate limited")
                    if response.status_code != 200: raise KricServerError(f"KRIC directory HTTP {response.status_code}")
                    data = bytearray()
                    async for chunk in response.aiter_bytes():
                        data.extend(chunk)
                        if len(data) > 1024 * 1024: raise KricServerError("KRIC directory exceeds 1 MiB")
            except httpx.HTTPError:
                raise KricNetworkError("KRIC directory request failed") from None
            finally: self._last = monotonic()
        try: html = data.decode("utf-8")
        except UnicodeError: raise KricServerError("KRIC directory encoding is invalid") from None
        return parse_kric_directory_page(html, kind=kind, page=page)

    async def get_general_stations(self) -> tuple[KricGeneralStation, ...]:
        rows: list[KricDirectoryRow] = []
        kinds: tuple[DirectoryKind, ...] = ("general", "ktx")
        for kind in kinds:
            first = await self.get_page(kind=kind)
            rows.extend(first.rows)
            for page in range(2, first.pages + 1):
                later = await self.get_page(kind=kind, page=page)
                if later.total != first.total or later.pages != first.pages:
                    raise KricServerError("KRIC directory changed during pagination")
                rows.extend(later.rows)
        groups: dict[str, list[KricDirectoryRow]] = {}
        for row in rows:
            key = ("korail:" + row.station_sequence) if row.station_sequence else "kric:" + hashlib.sha256(
                json.dumps([row.kind, row.route_label, row.name, row.address], ensure_ascii=False).encode()).hexdigest()
            groups.setdefault(key, []).append(row)
        linked: dict[str, KorailStationGuide] = {}
        async with KorailPublicClient(timeout=self._timeout) as korail:
            korail._client.event_hooks["request"].append(self._guard)
            guide_kinds: tuple[GuideKind, ...] = ("main", "ktx")
            for guide_kind in guide_kinds:
                guide = await korail.get_located_category_stations(kind=guide_kind, category_code="")
                for item in guide.stations:
                    previous = linked.get(item.station_sequence)
                    if previous and previous.latitude is not None and item.latitude is not None and (
                            previous.latitude != item.latitude or previous.longitude != item.longitude):
                        raise KricServerError("Linked official station coordinates conflict")
                    if previous is None or item.latitude is not None: linked[item.station_sequence] = item
        result = []
        for key, members in sorted(groups.items()):
            if len({r.name for r in members}) != 1: raise KricServerError("KRIC linked station names conflict")
            first_row = members[0]
            linked_item = linked.get(first_row.station_sequence) if first_row.station_sequence else None
            if linked_item is not None and linked_item.station_name != first_row.name: linked_item = None
            address = linked_item.address if linked_item and linked_item.address else max((r.address for r in members), key=len)
            result.append(KricGeneralStation(key, first_row.name, first_row.station_sequence,
                linked_item.station_code if linked_item else None, tuple(sorted({r.route_label for r in members})),
                tuple(sorted({r.kind for r in members})), address or None,
                linked_item.latitude if linked_item else None, linked_item.longitude if linked_item else None, tuple(members)))
        return tuple(result)
