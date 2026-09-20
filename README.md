# python-kric-api

KRIC(철도산업정보센터) Open API의 역 위치, 도시철도 노선 구성, 운행 시간표와 역 편의시설을
파싱하는 비동기 Python client입니다. 주기 수집·PostgreSQL 저장·즉시 조회 API·통계는
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

신청 대상과 구현 순서는 [docs/implementation-plan.md](docs/implementation-plan.md)를 참고하세요.
