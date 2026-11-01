## 2026-11-01 — 막차 안내 script와 파서 버전

신평역 실제 HTML의 출발 span 안에 막차 안내 JavaScript가 포함되어 있었다. DOM 글자 추출은 script/style 본문을 제외하고 실행하지 않는다. 시간·행선지·역·요일 검증을 완화하지 않으며 실제 원문은 별도 보존한다. `HUMETRO_PARSER_REVISION`은 소비자의 수정 전 파서 실패와 수정 후 한 번의 재시도를 구분한다. 인증·호출 제한 보호와 정상본 재사용은 소비자가 유지한다. WSL 248개·mypy 통과다.

## 2026-11-01 부산교통공사 공식 시간표

`HumetroClient`는 인증키 없는 [부산교통공사 공식 시간표](https://data.humetro.busan.kr/homepage/default/stationtime/page/list.do?menu_no=1001010301)를 조회한다. KRIC 자료 없음과 구분되는 별도 원천이며 HTML 파싱은 SDK가 소유한다.

```python
from kric import HumetroClient

async with HumetroClient() as client:
    page = await client.get_station_page(line_code="1", station_code="100")
    # available_directions의 다른 방향은 소비자의 호출 예산 아래 별도로 조회한다.
```

한 방향의 평일(8)·토요일(7)·일/공휴일(9)을 반환한다. 선택 역·노선·방향·요일 열과 시간표 구조를 검증하며 형식 오류를 정상 빈 결과로 바꾸지 않는다. 분 단위 출발 계획만 제공하며 열차 번호·도착 시각·서비스 날짜·실시간 도착은 추정하지 않는다. 원문의 23시 뒤 00:24는 `departure_time="24:24"`, `source_clock="00:24"`로 보존한다. 행선지 코드는 같은 페이지의 역 목록에서 이름이 유일하게 일치할 때만 제공한다. 응답 SHA-256과 원천 URL을 반환하며 수집 주기·양방향 원자 저장·실패 후 정상본 보존은 소비자 책임이다.

동매역 실제 양방향 조회는 토요일 334행·평일 359행·휴일 320행을 확인했다. 이는 2026-11-01 관측이며 다른 날짜의 고정 기대값이 아니다. WSL 오프라인 247개 통과·live 2개 제외, 전체 커버리지 93.07%, 새 모듈 100%, mypy 오류 0개다. 운영 DB 저장과 UI 수용은 소비자 배포에서 별도 확인한다.

# 현재 작업 — 코레일 공개 역 안내

- 별도 키 없는 client로 KTX 노선·일반철도 권역과 역 주소·전화·좌표를 제공한다.
- TAGO/KRIC 식별자를 추정 연결하지 않는다. 호출·파싱·좌표 연결은 provider가 소유한다.
- WSL 검증·독립 리뷰 후 소비자 pin을 갱신한다. 운영 빌드·배포는 하지 않는다.

# 현재 작업 — 2026-10-24

- `codex/station-file-amenities`: 공개 역사 파일 시설명을 typed 모델과 독립 파서에 추가했다.
- WSL mypy·오프라인 179개(필드별 회귀 추가 전), 커버리지 91.55%, James/Popper 독립 리뷰에서 잔여 P0/P1/P2 없음.
- 공개 파일 live: 1,108역, 전화번호 1,089역, 명시적 시설 긍정값 1,097역. O/X는 추가 추정하지 않는다.
- 최종 추가 회귀·CI 확인 후 소비자 pin을 반영한다.

# 현재 상태

- 2026-09-29 `codex/maglev-file-coordinates`: 원본 6역만 제한적으로 축 보정했다.
  [근거·보정 범위](maglev-coordinate-correction.md). WSL 169개 통과·live 2개 제외,
  커버리지 91.52%, mypy/compileall 통과. `07d91ca` CI·James/Popper 독립 리뷰 P0/P1 없음.
  공개 파일 opt-in live 1개 통과. P2 위도 단독 변형·XLSX 숫자 셀 테스트를 보강했다.
  소비자 pin은 반영했지만 운영 배포/지도 검증과 머지는 미완료다.

- 2026-09-28 KOMSA 기항지 API `15142297`의 `get_port_calls(name, province)`를 추가했다.
  기항지 코드·행정구역·위경도를 보존하고, 누락된 필드·잘린 페이지는 실패로 구분한다.
  WSL 테스트 163개 통과·live opt-in 2개 제외, 커버리지 91.49%, mypy 통과다.
  PR #9 후보 `1c1bb09`의 CI와 James/Popper 독립 재리뷰를 통과했다. 선택 필드 누락과
  잘못된 식별자 타입·성공 상태 누락 지적을 해결했다. typed client로 인천 기항지를 1회
  조회해 정상 좌표를 확인했다. 소비 서비스 운영 배포는 transport PR #51에서 별도 검증한다.

- 2026-09-27 공개 역사 파일의 위경도 범위 검증을 추가했다. 범위 밖 좌표는 원본을
  보존한 채 지도용 두 값만 비우며, 실제 운영 용유역 오류의 회귀를 검증한다.

- 2026-09-27 역사정보 34행·불광역 휴일 시간표 344행의 정상 응답을 확인했다.
  기존 `items.item` 파서가 실제 `body` 배열을 거부하던 결함을 고치고 행 수·빈 응답·자정
  문자열 보존 회귀 테스트를 추가했다. 재호출 대신 축약한 공개 응답 구조로 검증한다.

- JSON 요청·오류 envelope·typed parser의 초기 구현이 완료됐다.
- 해양수산부 항만가이드라인 위치 CSV(`15121268`)는 서비스키 없이 비동기 다운로드·RustFS 보관·typed
  좌표 파싱이 가능하다. transport 소비자는 항구명 연결 결과와 원본 점 자료의 차이를 명시해 지도에 제공한다.
- 인증키가 없는 공개 XLSX dataset `1294`(전국 도시광역철도 역사정보) 다운로드와 typed parser가
  완료됐다. 파일의 표시 식별자는 API 코드와 별개로 보존한다.
- 공공데이터포털의 국내선박운항정보와 KOMSA 연안여객선 운항 스케줄 provider를
  `DataGoKrMaritimeClient`로 분리 구현했다. `DATA_GO_KR_SERVICE_KEY`로 서비스별 최소
  live 호출과 KOMSA 빈 결과(`153`) 계약을 검증했다.
- 공개 XLSX 원문을 공용 RustFS에 비동기 보관할 수 있다. `RustfsObjectStore`는 S3 호환
  boto3 client를 `asyncio.to_thread`로 감싸고, file client는 dataset·operation·SHA-256
  기반의 idempotent object key를 반환한다. HTTPS endpoint가 기본이며, 검증한 XLSX만 `.xlsx`
  객체로 보관한다. store는 async context manager로 연결 풀을 닫는다.
- 여객선 기준정보는 명시적 호출 상한을 가진 비동기 pagination iterator로 전량을 읽는다.
  실제 확인된 비페이지 터미널·선박종류 응답만 `totalCount` 없이 허용한다. 항구 목록의 count
  누락은 오류로 유지하며, 페이지 메타데이터가 남은 불완전한 응답도 거부한다.
  운항 시간표·계획 운항은 quota를 예측할 수 없으므로 요청한 한 페이지만 반환한다.
- 노선·열차별 시간표·역 편의시설 세부 필드의 실제 성공 응답은 아직 별도 검증 대상이다.

# 다음 한 작업

RustFS 공개 파일 저장 변경의 CI·독립 리뷰·머지 뒤 소비 서비스의 공용 RustFS 설정을 연결하고,
dataset `916` 이후 전국 역사 편의시설 파일의 실제 헤더·갱신 계약을 확인한다.

## 2026-11-01 전체 공개 역 조회

분류를 고르기 전 전체 역을 조회할 수 있다. 204건·92% 확인, 소비자 Transport pin 반영 후 운영 지도에서 수용한다.
