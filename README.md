# python-kric-api

KRIC(철도산업정보센터) Open API와 공개 파일 데이터의 역 위치, 도시철도 노선 구성, 운행
시간표와 역 편의시설을 파싱하는 비동기 Python client입니다. 주기 수집·PostgreSQL 저장·즉시 조회 API·통계는
`kor-travel-transport`가 담당하며, 이 패키지는 provider 응답 계약을 보존합니다.

## 설치

```bash
pip install -e ".[dev]"
```

현재는 API 신청 전 초기 구현 단계입니다. 오류 envelope는 실제 무효 키 응답으로 확인했지만,
성공 응답 envelope와 역 편의시설 세부 필드는 서비스키 발급 후 키를 제거한 fixture로
확정해야 합니다. KRIC 서비스키를 코드·로그·fixture에 넣지 마세요.

## 사용 예시

```python
import asyncio

from kric import KricClient, ServiceDayCode


async def main():
    async with KricClient("발급받은-서비스키") as client:
        station = await client.get_station_info(
            rail_operator_code="S1", line_code="1", station_code="150"
        )
        timetable = await client.get_station_timetable(
            rail_operator_code="S1",
            line_code="1",
            station_code="150",
            day_code=ServiceDayCode.WEEKDAY,
        )
        print(station[0].station_name, timetable[0].departure_time)


asyncio.run(main())
```

`map_x`와 `map_y`는 KRIC가 CRS·단위를 명시하기 전까지 원문 문자열로 제공합니다. 시간표의
시각도 서비스 날짜 없이 datetime으로 추정하지 않고 원문 문자열로 제공합니다.

## 제공 API

- `get_station_info()` → `convenientInfo/stationInfo`
- `get_subway_route_info()` → `trainUseInfo/subwayRouteInfo`
- `get_station_timetable()` → `convenientInfo/stationTimetable`
- `get_subway_timetable()` → `trainUseInfo/subwayTimetable`
- `get_station_facilities()` → `convenientInfo/stationCnvFacl`

## 공공데이터포털 여객선 API

국내선박운항정보와 연안여객선 운항 스케줄은 KRIC와 다른 제공자이므로
`DataGoKrMaritimeClient`로 분리합니다. KRIC 서비스키를 재사용하지 말고, 공공데이터포털에
신청한 `DATA_GO_KR_SERVICE_KEY`를 전달하세요. 이 client는 저장·스케줄링·FastAPI를 포함하지
않고, 한 번의 호출에서 요청한 페이지 하나만 반환합니다. 제공자 endpoint는 고정하며 외부 URL을
받지 않고 redirect도 거부하므로 서비스키가 다른 호스트로 전송되지 않습니다.

```python
import os

from kric import DataGoKrMaritimeClient


async with DataGoKrMaritimeClient(os.environ["DATA_GO_KR_SERVICE_KEY"]) as client:
    ports = await client.search_ports(name="인천")
    sailings = await client.get_domestic_ship_operations(
        departure_port_id=ports[0].port_id,
        departure_date="20260921",
    )
    schedules = await client.get_coastal_ferry_schedules(
        schedule_date="20260921", vessel_name="여객선명",
    )
```

- `search_ports()` → 국토교통부 `(TAGO) 국내선박운항정보`의 `GetPortList`
- `get_domestic_ship_operations()` → `GetShipOpratInfoList`
- `get_ferry_terminals()` → `GetPsnshipTrminlList`
- `get_ferry_ship_types()` → `GetShipKndList`
- `get_coastal_ferry_schedules()` → 한국해양교통안전공단 `운항 스케줄 정보`의
  `get-oprt-schd-info-v2`

TAGO 운항정보의 제공 필드 오탈자인 `vihicleNm`은 원문 `raw`에 그대로 보존하고,
공개 모델에서는 `vessel_name`으로 제공합니다. 날짜·시각·요금·코드는 추정 변환하지 않습니다.
KOMSA의 선택 응답열 `filters`는 typed 모델의 필수 계약과 충돌할 수 있어 노출하지 않습니다.
운항 스케줄 API는 개발계정 기준 일일 100건으로 안내되므로, 운영 호출량은 승인 범위에 맞춰
소비 서비스에서 제한해야 합니다. 키·응답에 포함될 수 있는 민감한 값을 로그나 fixture에 남기지
마세요. KOMSA가 `153` (`NOT_FOUND_DATA`)를 반환하면 이는 해당 날짜·여객선의 빈 결과로
간주해 빈 tuple을 반환합니다.

## 공개 파일 데이터

API 키가 필요 없고 갱신 주기가 낮은 기준정보는 공개 파일을 우선 사용합니다. 현재
`KricFileClient.get_nationwide_station_info()`는 포털의 **전국 도시광역철도 역사정보**
(dataset `1294`, XLSX)를 인증키 없이 내려받아 `FileStationInfo`로 반환합니다.

```python
from kric import KricFileClient


async with KricFileClient() as client:
    stations = await client.get_nationwide_station_info()
    print(stations[0].station_name)
```

파일의 `철도운영기관명`, `운영노선`, `역 번호`는 표시값이며 Open API의 운영기관·노선·역
**코드로 추정하지 않습니다**. 원문 열은 `raw`에 보존합니다. 소비 서비스는 파일의
수정일/데이터 기준일을 기록하고 월 1회 또는 포털 수정 감지 시에만 재수집해야 합니다.
운행시각표·실시간성 있는 정보는 파일이 아닌 해당 Open API를 사용합니다.

다른 XLSX 파일은 `download_dataset()`과 `parse_xlsx_table()`로 먼저 원문 헤더·행을 안전하게
읽을 수 있습니다. 시설별 typed 모델은 포털의 파일 계약을 실제로 확인한 뒤 추가합니다.
다운로드는 기본 10 MiB, XLSX 압축 해제 크기는 64 MiB, 첫 worksheet는 100,000행·256열로
제한합니다. 숫자 셀의 `0000` 형식과 `\\I000` 같은 이스케이프 접두사 형식은 표시 문자열로
보존하므로 역 번호의 선행 0·문자 접두사가 사라지지 않습니다.
다운로드 주소는 SSRF 방지를 위해 `https://data.kric.go.kr`으로만 제한합니다.
주입한 HTTP client가 redirect를 따르도록 설정돼도 공개 파일 요청은 redirect를 따르지 않습니다.

실제 공개 파일 계약은 서비스키 없이 다음처럼 선택적으로 확인할 수 있습니다.

```bash
KRIC_LIVE_FILES=1 python -m pytest -m live tests/test_live_files.py -q
```

공공데이터포털 여객선 API의 승인·빈 결과 계약은 다음처럼 선택적으로 확인합니다. 테스트는
항구 1건과 당일 `코리아프라이드` 연안 스케줄 1건만 요청합니다. 다른 승인된 운항 선박을
검증하려면 `DATA_GO_KR_LIVE_MARITIME_VESSEL_NAME`을 지정하세요. 당일 스케줄이 없으면
실패가 아니라 skip으로 끝납니다.

```bash
DATA_GO_KR_LIVE_MARITIME=1 DATA_GO_KR_SERVICE_KEY="..." \
  python -m pytest -m live tests/test_live_maritime.py -q
```

신청 대상과 구현 순서는 [docs/implementation-plan.md](docs/implementation-plan.md)를 참고하세요.
