"""공공데이터포털 국내·연안 여객선 API를 위한 비동기 client."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date, datetime
import math
from typing import Any

import httpx

from .exceptions import (
    KricAuthError,
    KricInvalidParameterError,
    KricNetworkError,
    KricRateLimitError,
    KricServerError,
)
from .models import (
    CoastalFerrySchedule,
    DomesticFerryPort,
    DomesticShipOperation,
    FerryShipType,
    FerryTerminal,
)
from .parse import as_raw_mapping, require_fields

DOMESTIC_SHIP_BASE_URL = "https://apis.data.go.kr/1613000/DmstcShipNvgInfo"
COASTAL_SCHEDULE_BASE_URL = "https://apis.data.go.kr/B554035/oprt-schd-info-v2"


class DataGoKrMaritimeClient:
    """공공데이터포털의 국내선박·연안여객선 API client.

    ``service_key``에는 KRIC 키가 아니라 ``DATA_GO_KR_SERVICE_KEY``를 전달한다.
    호출량을 예측하기 어렵기 때문에 모든 목록 API는 요청한 한 페이지만 반환하며,
    자동 재시도나 자동 페이지 순회는 하지 않는다.
    """

    def __init__(
        self,
        service_key: str,
        *,
        domestic_ship_base_url: str = DOMESTIC_SHIP_BASE_URL,
        coastal_schedule_base_url: str = COASTAL_SCHEDULE_BASE_URL,
        timeout: float = 30.0,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self.service_key = _required_text(service_key, "service_key")
        if not isinstance(timeout, (int, float)) or isinstance(timeout, bool) or not math.isfinite(timeout) or timeout <= 0:
            raise KricInvalidParameterError("timeout must be a positive finite number")
        self.domestic_ship_base_url = _base_url(domestic_ship_base_url, "domestic_ship_base_url")
        self.coastal_schedule_base_url = _base_url(coastal_schedule_base_url, "coastal_schedule_base_url")
        self._client = client or httpx.AsyncClient(timeout=timeout)
        self._owns_client = client is None

    async def __aenter__(self) -> "DataGoKrMaritimeClient":
        return self

    async def __aexit__(self, *_: object) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        """내부에서 생성한 HTTP client만 닫는다."""
        if self._owns_client:
            await self._client.aclose()

    async def search_ports(
        self, *, name: str | None = None, page_no: int = 1, num_of_rows: int = 100
    ) -> tuple[DomesticFerryPort, ...]:
        """국내선박운항정보의 항구 목록을 이름으로 선택 조회한다."""
        params = _page_params(page_no, num_of_rows)
        if name is not None:
            params["nodeNm"] = _required_text(name, "name")
        payload = await self._get(self.domestic_ship_base_url, "GetPortList", params, response_type="_type")
        return tuple(_parse_port(row) for row in _extract_items_or_empty(payload))

    async def get_domestic_ship_operations(
        self, *, departure_port_id: str, departure_date: date | str, page_no: int = 1, num_of_rows: int = 100
    ) -> tuple[DomesticShipOperation, ...]:
        """출항 항구와 계획일 기준의 국내 여객선 운항 계획을 조회한다."""
        params = _page_params(page_no, num_of_rows)
        params.update({
            "depNodeId": _required_text(departure_port_id, "departure_port_id"),
            "depPlandTime": _date_text(departure_date, "departure_date"),
        })
        payload = await self._get(
            self.domestic_ship_base_url, "GetShipOpratInfoList", params, response_type="_type"
        )
        return tuple(_parse_domestic_operation(row) for row in _extract_items_or_empty(payload))

    async def get_ferry_terminals(self) -> tuple[FerryTerminal, ...]:
        """국내선박운항정보가 제공하는 여객선 터미널 기준정보를 조회한다."""
        payload = await self._get(
            self.domestic_ship_base_url, "GetPsnshipTrminlList", {}, response_type="_type"
        )
        return tuple(_parse_terminal(row) for row in _extract_items_or_empty(payload))

    async def get_ferry_ship_types(self) -> tuple[FerryShipType, ...]:
        """국내선박운항정보가 제공하는 여객선 종류 기준정보를 조회한다."""
        payload = await self._get(self.domestic_ship_base_url, "GetShipKndList", {}, response_type="_type")
        return tuple(_parse_ship_type(row) for row in _extract_items_or_empty(payload))

    async def get_coastal_ferry_schedules(
        self,
        *,
        schedule_date: date | str,
        vessel_name: str,
        page_no: int = 1,
        num_of_rows: int = 100,
        filters: str | None = None,
    ) -> tuple[CoastalFerrySchedule, ...]:
        """KOMSA 연안여객선의 특정 날짜·여객선 운항 스케줄을 조회한다."""
        params = _page_params(page_no, num_of_rows)
        params.update({
            "rlvtYmd": _date_text(schedule_date, "schedule_date"),
            "psnshpNm": _required_text(vessel_name, "vessel_name"),
        })
        if filters is not None:
            params["filters"] = _required_text(filters, "filters")
        payload = await self._get(
            self.coastal_schedule_base_url, "get-oprt-schd-info-v2", params, response_type="dataType"
        )
        return tuple(_parse_coastal_schedule(row) for row in _extract_items_or_empty(payload))

    async def _get(
        self, base_url: str, operation: str, params: Mapping[str, str], *, response_type: str
    ) -> Mapping[str, Any]:
        request_params = {"serviceKey": self.service_key, response_type: "JSON", **params}
        try:
            response = await self._client.get(f"{base_url}/{operation}", params=request_params)
        except httpx.HTTPError as exc:
            raise KricNetworkError("data.go.kr maritime request failed") from exc
        if response.status_code in (401, 403):
            raise KricAuthError(f"data.go.kr maritime request denied: HTTP {response.status_code}")
        if response.status_code == 429:
            raise KricRateLimitError("data.go.kr maritime request rate limited: HTTP 429")
        if response.status_code >= 400:
            raise KricServerError(f"data.go.kr maritime request failed: HTTP {response.status_code}")
        try:
            payload = response.json()
        except ValueError as exc:
            raise KricServerError("data.go.kr maritime response is not JSON") from exc
        if not isinstance(payload, Mapping):
            raise KricServerError("data.go.kr maritime JSON response must be an object")
        if _raise_for_error_envelope(payload):
            return {"body": {"items": [], "totalCount": 0}}
        return payload


def _base_url(value: str, name: str) -> str:
    url = _required_text(value, name).rstrip("/")
    if not url.startswith("https://"):
        raise KricInvalidParameterError(f"{name} must be an HTTPS URL")
    return url


def _required_text(value: str, name: str) -> str:
    if not isinstance(value, str):
        raise KricInvalidParameterError(f"{name} must be a non-blank string")
    text = value.strip()
    if not text:
        raise KricInvalidParameterError(f"{name} must not be blank")
    return text


def _date_text(value: date | str, name: str) -> str:
    if isinstance(value, datetime):
        raise KricInvalidParameterError(f"{name} must be a date or YYYYMMDD string")
    if isinstance(value, date):
        return value.strftime("%Y%m%d")
    text = _required_text(value, name)
    try:
        parsed = datetime.strptime(text, "%Y%m%d")
    except ValueError as exc:
        raise KricInvalidParameterError(f"{name} must be a valid YYYYMMDD date") from exc
    if parsed.strftime("%Y%m%d") != text:
        raise KricInvalidParameterError(f"{name} must be a valid YYYYMMDD date")
    return text


def _page_params(page_no: int, num_of_rows: int) -> dict[str, str]:
    if isinstance(page_no, bool) or not isinstance(page_no, int) or page_no < 1:
        raise KricInvalidParameterError("page_no must be a positive integer")
    if isinstance(num_of_rows, bool) or not isinstance(num_of_rows, int) or num_of_rows < 1:
        raise KricInvalidParameterError("num_of_rows must be a positive integer")
    return {"pageNo": str(page_no), "numOfRows": str(num_of_rows)}


def _raise_for_error_envelope(payload: Mapping[str, Any]) -> bool:
    candidates: tuple[Any, ...] = (payload, payload.get("response"))
    for candidate in candidates:
        if not isinstance(candidate, Mapping):
            continue
        header = candidate.get("header")
        if not isinstance(header, Mapping):
            continue
        code = str(header.get("resultCode") or "").strip()
        if not code or code in {"00", "0", "200", "NORMAL_SERVICE"}:
            return False
        if code == "153":
            return True
        message = str(header.get("resultMsg") or "data.go.kr maritime API returned an error")
        if code in {"20", "30", "31"}:
            raise KricAuthError(message)
        if code in {"22", "23", "117"}:
            raise KricRateLimitError(message)
        if code in {"10", "130", "131", "132", "157", "158"}:
            raise KricInvalidParameterError(message)
        raise KricServerError(message)
    return False


def _extract_items_or_empty(payload: Mapping[str, Any]) -> tuple[Mapping[str, Any], ...]:
    root = payload.get("response")
    envelope = root if isinstance(root, Mapping) else payload
    body = envelope.get("body") if isinstance(envelope, Mapping) else None
    if not isinstance(body, Mapping):
        raise KricServerError("data.go.kr maritime response does not contain a body object")
    items = body.get("items")
    if items in (None, "", []):
        return _empty_or_invalid(body)
    if not isinstance(items, Mapping):
        raise KricServerError("data.go.kr maritime response items must be an object")
    item = items.get("item")
    if item in (None, "", []):
        return _empty_or_invalid(body)
    if isinstance(item, Mapping):
        return (item,)
    if isinstance(item, list) and all(isinstance(row, Mapping) for row in item):
        return tuple(item)
    raise KricServerError("data.go.kr maritime response item must be an object or list")


def _empty_or_invalid(body: Mapping[str, Any]) -> tuple[Mapping[str, Any], ...]:
    total = body.get("totalCount")
    if total is None:
        raise KricServerError("data.go.kr maritime empty response must contain totalCount")
    try:
        if int(str(total)) > 0:
            raise KricServerError("data.go.kr maritime response has a positive count without items")
    except ValueError as exc:
        raise KricServerError("data.go.kr maritime response totalCount must be an integer") from exc
    return ()


def _parse_port(row: Mapping[str, Any]) -> DomesticFerryPort:
    raw = as_raw_mapping(row)
    require_fields(raw, "GetPortList item", "nodeId", "nodeNm")
    return DomesticFerryPort(port_id=raw.get("nodeId"), port_name=raw.get("nodeNm"), raw=raw)


def _parse_terminal(row: Mapping[str, Any]) -> FerryTerminal:
    raw = as_raw_mapping(row)
    require_fields(raw, "GetPsnshipTrminlList item", "terminalId", "terminalNm")
    return FerryTerminal(
        terminal_id=raw.get("terminalId"), terminal_name=raw.get("terminalNm"),
        address=raw.get("address"), telephone=raw.get("tel"), raw=raw,
    )


def _parse_ship_type(row: Mapping[str, Any]) -> FerryShipType:
    raw = as_raw_mapping(row)
    require_fields(raw, "GetShipKndList item", "shipKndId", "shipKndNm")
    return FerryShipType(ship_type_id=raw.get("shipKndId"), ship_type_name=raw.get("shipKndNm"), raw=raw)


def _parse_domestic_operation(row: Mapping[str, Any]) -> DomesticShipOperation:
    raw = as_raw_mapping(row)
    require_fields(raw, "GetShipOpratInfoList item", "vihicleNm", "depPlaceNm", "arrPlaceNm", "depPlandTime", "arrPlandTime")
    return DomesticShipOperation(
        vessel_name=raw.get("vihicleNm"), departure_port_name=raw.get("depPlaceNm"),
        arrival_port_name=raw.get("arrPlaceNm"), departure_planned_time=raw.get("depPlandTime"),
        arrival_planned_time=raw.get("arrPlandTime"), fare=raw.get("charge"), raw=raw,
    )


def _parse_coastal_schedule(row: Mapping[str, Any]) -> CoastalFerrySchedule:
    raw = as_raw_mapping(row)
    require_fields(raw, "get-oprt-schd-info-v2 item", "rlvt_ymd", "sail_tm", "psnshp_cd", "psnshp_nm", "oport_cd")
    return CoastalFerrySchedule(
        schedule_date=raw.get("rlvt_ymd"), departure_time=raw.get("sail_tm"),
        vessel_code=raw.get("psnshp_cd"), vessel_name=raw.get("psnshp_nm"),
        departure_port_code=raw.get("oport_cd"), departure_port_name=raw.get("oport_nm"),
        destination_port_code=raw.get("dest_cd"), destination_port_name=raw.get("dest_nm"),
        licensed_route_code=raw.get("lcns_seawy_cd"), licensed_route_name=raw.get("lcns_seawy_nm"),
        operating_route_code=raw.get("nvg_seawy_cd"), operating_route_name=raw.get("nvg_seawy_nm"),
        direction_code=raw.get("nvg_drc_cd"), direction_name=raw.get("nvg_drc_nm"),
        operation_type_code=raw.get("nvg_se_cd"), operation_type_name=raw.get("nvg_se_nm"),
        operation_status_code=raw.get("nvg_stts_cd"), operation_status_name=raw.get("nvg_stts_nm"),
        control_reason_code=raw.get("cntrl_rsn_cd"), control_reason_name=raw.get("cntrl_rsn_nm"),
        non_operation_reason_code=raw.get("nnavi_rsn_cd"), non_operation_reason_name=raw.get("nnavi_rsn_nm"),
        vessel_number=raw.get("vsl_no"), cancellation_other_reason=raw.get("cnls_etc_rsn"),
        route_category_code=raw.get("seawy_se_cd"), route_category_name=raw.get("seawy_se_nm"), raw=raw,
    )
