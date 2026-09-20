# KRIC 라이브러리 구현 계획

## 목적과 범위

`python-kric-api`는 국내 여행 통합 교통정보를 위한 철도 provider다. KRIC의 역 위치,
노선 정보, 운행 시간표, 편의시설을 API·공개 파일의 계약에 맞게 파싱한다. 이 저장소는
스케줄러·PostgreSQL·FastAPI를 구현하지 않으며, 소비자 `kor-travel-transport`가 주기 저장과
즉시 조회를 맡는다.

서비스키는 아직 발급되지 않았다. JSON client와 네트워크 없는 parser/test scaffold는
구현됐으며, 실제 성공 응답 envelope와 역 편의시설 세부 필드는 아래 API 신청 뒤 키를
제거한 fixture로 확정해야 한다.

## 공개 파일 우선 기준정보

서비스키가 필요 없고 갱신 주기가 낮은 데이터는 Open API보다 파일 데이터를 우선한다.
포털의 파일과 Open API를 같은 원본이나 같은 코드 체계로 가정하지 않는다.

| 우선순위 | 파일 dataset | 현재 확인한 계약 | 라이브러리 제공 방식 | 소비 서비스 수집 권장 |
|---|---:|---|---|---|
| P0 | `1294` | 전국 도시광역철도 역사정보, XLSX, 29개 열, 수정일 2026-06-29, 포털상 업데이트 주기 없음 | `KricFileClient.get_nationwide_station_info()` → `FileStationInfo` | 월 1회와 포털 수정 감지 시 |
| P1 | `916` 이후 전국 역사 편의시설 XLSX | ATM·고객센터·무빙워크·보관함 등 시설별 분리 파일 | 공통 XLSX 다운로드 후 각 파일 계약 확인 뒤 typed parser 추가 | 월 1회와 포털 수정 감지 시 |

`1294`의 운영기관명·운영노선·역 번호는 화면용 값이며, API의
`railOprIsttCd`/`lnCd`/`stinCd`로 변환하거나 조인하지 않는다. 좌표는 파일에 명시된
경도·위도 열만 `float`으로 해석하고, API의 `mapCordX`/`mapCordY`와 결합하지 않는다.

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

1. `src/kric`의 client, exceptions, models, parse와 `files`를 구현했다. `files`는 공개 XLSX의
   무인증 다운로드와 dataset `1294` 역사정보 typed parser를 제공한다. 시설별 파일은 실제
   헤더·갱신 계약을 확인한 뒤 각 typed parser를 추가한다.
2. 서비스키가 제거된 실제 성공 fixture로 JSON/XML의 목록·단일 객체·빈 값·오류 payload를 테스트한다.
3. 코드 선행 0, 노선 반복역, 순서, `dayCd`, 시간 문자열, CRS 미확정 좌표를 회귀 테스트한다.
4. 공식 샘플 또는 허가된 1회 live 호출을 fixture로 정리한 뒤 `@pytest.mark.live` smoke를 추가한다.
5. README·구현 상태·변경 기록을 갱신하고 두 적대적 리뷰와 CI를 통과한다.

## 수용 기준

- 안정 API별 요청 파라미터 사전 검증과 오류 타입이 있다.
- 공개 모델은 typed dataclass이며 코드·순서·시간·원시 좌표 계약을 잃지 않는다.
- 기본 테스트는 네트워크와 키 없이 동작하며 90% 이상의 커버리지를 만족한다.
- CRS가 확인되기 전 `mapCordX`/`mapCordY`의 좌표 변환을 제공하지 않는다.
- KRIC 응답의 파싱 책임이 소비 서비스에 중복 구현되지 않는다.
