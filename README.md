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
제한합니다. 숫자 셀의 단순 `0000` 형식은 표시 문자열로 보존하므로 역 번호의 선행 0이
사라지지 않습니다.

실제 공개 파일 계약은 서비스키 없이 다음처럼 선택적으로 확인할 수 있습니다.

```bash
KRIC_LIVE_FILES=1 python -m pytest -m live tests/test_live_files.py -q
```

신청 대상과 구현 순서는 [docs/implementation-plan.md](docs/implementation-plan.md)를 참고하세요.
