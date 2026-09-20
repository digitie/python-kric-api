# KRIC 라이브러리 구현 계획

## 목적과 범위

`python-kric-api`는 국내 여행 통합 교통정보를 위한 철도 provider다. KRIC의 역 위치,
노선 정보, 운행 시간표, 편의시설을 API·공개 파일의 계약에 맞게 파싱한다. 이 저장소는
스케줄러·PostgreSQL·FastAPI를 구현하지 않으며, 소비자 `kor-travel-transport`가 주기 저장과
즉시 조회를 맡는다.

현재는 서비스키가 발급되지 않았고, 라이브러리 구현은 시작하지 않았다. 아래 API 신청과
fixture 확보가 선행 조건이다.

## 1단계: 안정 파서 대상

| 우선순위 | KRIC service / operation | 제공 모델 | 주의점 |
|---|---|---|---|
| P0 | `convenientInfo/stationInfo` | `StationInfo` | 운영기관·노선·역 코드와 주소, 위경도, 원시 map coordinate 보존 |
| P0 | `trainUseInfo/subwayRouteInfo` | `SubwayRouteStop` | `routCd` 그룹과 `stinConsOrdr` 순서·반복역 보존 |
| P0 | `convenientInfo/stationTimetable` | `StationTimetableEntry` | `dayCd` 7/8/9와 시간 문자열 의미 보존 |
| P0 | `trainUseInfo/subwayTimetable` | `SubwayTimetableEntry` | 광역/도시철도 시간표의 응답 차이를 fixture로 확인 |
| P1 | `convenientInfo/stationCnvFacl` | `StationFacility` | 시설 분류 코드/설명과 알 수 없는 값 보존 |

## 2단계: 사용자 신청 대상

기본 5개 외에 다음 API를 함께 신청한다. 신청 전에는 경로·필드·할당량을 구현 사실로
표기하지 않는다.

- `subwayTimetableExp`: 시간표 확장 정보
- `stPlf`: 승강장 정보
- `stationCongestion`: 서울교통공사 평일·분기 수집 범위의 혼잡도
- 환승·역간 이동·엘리베이터 관련 API

KRIC의 신청 절차는 [Open API 이용 절차](https://data.kric.go.kr/rips/serviceInfo/openapi/process.do)를
따른다. 공식 안내는 한 키로 여러 API 사용이 가능하다고 설명하지만, 고정 TPS/일일 할당량을
명시하지 않는다. 실제 승인 범위와 호출 제한은 발급 후 기록한다.

## 3단계: 패키지와 테스트

1. `src/kric`에 client, exceptions, models, parse, files를 만든다.
2. 서비스키가 제거된 fixture로 JSON/XML의 목록·단일 객체·빈 값·오류 payload를 테스트한다.
3. 코드 선행 0, 노선 반복역, 순서, `dayCd`, 시간 문자열, CRS 미확정 좌표를 회귀 테스트한다.
4. 공식 샘플 또는 허가된 1회 live 호출을 fixture로 정리한 뒤 `@pytest.mark.live` smoke를 추가한다.
5. README·구현 상태·변경 기록을 갱신하고 두 적대적 리뷰와 CI를 통과한다.

## 수용 기준

- 안정 API별 요청 파라미터 사전 검증과 오류 타입이 있다.
- 공개 모델은 typed dataclass이며 코드·순서·시간·원시 좌표 계약을 잃지 않는다.
- 기본 테스트는 네트워크와 키 없이 동작하며 90% 이상의 커버리지를 만족한다.
- CRS가 확인되기 전 `mapCordX`/`mapCordY`의 좌표 변환을 제공하지 않는다.
- KRIC 응답의 파싱 책임이 소비 서비스에 중복 구현되지 않는다.
