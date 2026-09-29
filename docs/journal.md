# 작업 기록

## 2026-09-29 자기부상 공개 파일 좌표

- dataset 1294 원본과 인천공항 공식 노선 안내를 대조해 6역의 경위도 축 오류를 확인했다.
- 기관·노선·역 번호·역명·원시 좌표쌍이 일치할 때만 typed 좌표를 교환한다. raw는 보존한다.
- WSL 단위 169개 통과·명시적 live 2개 제외, 커버리지 91.52%다. mypy/compileall도 통과했다.
  최초 mypy의 Optional 키 오류를 수정했다. `07d91ca`의 CI와 James/Popper 독립 리뷰에서
  P0/P1 지적은 없었다. Popper의 P2 테스트 보강을 반영해 위도 단독 변경과 숫자 셀 XLSX
  왕복 파싱까지 6역 회귀로 고정했다(6개 통과). 런타임 코드는 바뀌지 않았다.
- 서비스키 없는 opt-in 공개 파일 live 1개 통과(7.21초). 소비자 운영 반영은 아직 대기 중이다.


## 2026-09-28 기항지 좌표 API

- `15142297` 승인 후 `get_port_calls`와 불변 `PortCall` 모델을 추가했다.
- 필수 이름·시도, 응답 개수 정합성, 코드 보존, null/잘못된 좌표, 153/117 오류를 검증한다.
- WSL pytest 163개 통과·live opt-in 2개 제외, 커버리지 91.49%, mypy 통과다.
- 후보 `1c1bb09`의 Python 3.11/3.12/3.13 CI와 두 적대적 재리뷰를 통과했다.
  James: 선택 좌표/행정구역 누락 및 식별자 타입 검증 수정 확인, 추가 모의 응답 74건 통과.
  Popper: 잘못된 식별자 타입 및 명시적 성공 상태 누락 수정 확인, 추가 모의 응답 119건 통과.
  두 리뷰어 모두 새로운 P0/P1/P2 지적이 없었다.
- typed client로 인천 기항지 1회 성공을 확인했다(초기 API 조사 1회와 별도).
  키/요청 URL은 기록하지 않았고 KRIC 철도 API는 호출하지 않았다.
  소비 서비스 배포는 transport PR #51에서 별도로 검증한다.

## 2026-09-28

- 미머지 PR #6을 최신 main과 통합했다. 독립 James/Popper 리뷰가 지적한 P1인
  `totalCount` 누락의 무조건 성공 처리를 재현했으며, 비페이지 예외를 실제 검증된
  operation과 메타데이터 없는 명시적 성공 응답으로 한정한다.
- n150에서 TAGO 터미널·선박종류를 각 1회, 30초 간격으로 확인했다. HTTP 200/`00`,
  body는 `items`만 가지며 각각 27/7행이다. 키와 요청 URL은 기록하지 않았다.

## 2026-09-27

- transport 실제 화면에서 용유역의 경도 37.424805/위도 126.423637 때문에 지도 카메라가
  실패하는 것을 재현했다. 공개 파일 파서의 범위 밖 위경도는 둘 다 `None`으로 반환하고
  원본 열과 역 정보는 보존한다. 근거 없는 축 교환은 하지 않는다. 소비 UI도 기존 DB의
  범위 밖 좌표를 지도에서 제외하되 목록·시간표 선택은 유지한다. 인증 API는 재호출하지 않는다.

- 적대 리뷰에서 발견한 잘못된 header/resultCode의 빈 성공 오인과 긴 count 문자열의
  일반 ValueError 누출을 재현해 수정했다. 존재하는 오류 필드는 타입을 검증하며, count는
  선행 0을 제거한 문자열로 비교해 Python 정수 변환 길이 제한에 의존하지 않는다.

- 정상 KRIC JSON의 `body` 배열을 지원하고 선택적 `resultCnt`의 정수/행 수 계약을 검증했다.
  승인 키를 사용한 단일 역사정보·단일 시간표 진단에서 HTTP 200과 각각 34/344행을 확인했다.
  키·요청 URL은 저장하지 않았으며 테스트는 공개 필드만 축약한 오프라인 응답을 사용한다.
  라이브러리 오류를 transport 파서 우회로 해결하지 않는다. 48시간 수집 간격은 소비자 책임이다.

## 2026-09-23

- TAGO `GetPsnshipTrminlList`의 정상 응답에서 `totalCount` 없는 기준정보를 확인했다.
  페이지를 추측 호출하지 않되 불완전한 페이지와 구별하는 검증이 필요하다.

## 2026-09-21

- 해양수산부 파일 `15121268`의 무인증 항만가이드라인 CSV provider를 추가했다. CP949 원문에서
  항구명·위도·경도·순서·선수방위를 typed model로 보존하고, 검증된 파일을 RustFS에 checksum key로
  비동기 보관한다. 항만 중심점을 임의 추정하지 않으며 좌표 불일치는 오류로 처리한다.

- 여객선 기준정보 소비자가 첫 페이지를 성공으로 저장하지 않도록 `iter_ports()`,
  `iter_ferry_terminals()`, `iter_ferry_ship_types()`를 추가했다. iterator는 명시적인
  `page_size`·`max_pages` 호출 예산 안에서만 순회하며, 상한을 모두 채우면 불완전한 결과를
  성공으로 가장하지 않고 `KricServerError`를 낸다. `totalCount`를 누적 행 수와 비교해
  page size의 정확한 배수도 다음 빈 페이지를 요청하지 않고 종료한다. 페이지 간 provider
  식별자 중복도 오류로 처리한다. 실시간 운항 조회는 기존 단일 페이지 API로 유지한다.

## 2026-09-21

- RustFS 적대적 리뷰의 P1을 반영했다. HTTPS endpoint를 기본으로 강제하고 private
  loopback HTTP는 explicit opt-in으로만 허용한다. S3 인증·권한·bucket 설정·quota·서버·네트워크
  오류를 재시도 정책에 맞는 KRIC 예외로 구분했으며, timeout·retry·동시 업로드 상한과 `aclose()`를
  추가했다. dataset `1294`는 XLSX 검증 성공 뒤에만 업로드하고 범용 파일은 형식을 `.xlsx`로
  단정하지 않는다.
- 공용 RustFS를 S3 호환 object store로 사용하는 `RustfsObjectStore`를 추가했다. 공개 API는
  모두 async이며 boto3 `put_object`만 `asyncio.to_thread`에서 실행한다.
- `KricFileClient.download_dataset_to_rustfs()`와
  `get_nationwide_station_info_to_rustfs()`가 공개 XLSX의 원문을
  `dataset/operation/SHA-256` 결정적 key로 보관한다. endpoint URL의 credential 포함,
  unsafe object key, 빈 object body는 요청 전에 거부한다.

## 2026-09-20

- 공공데이터포털의 국토교통부 `(TAGO) 국내선박운항정보`와 한국해양교통안전공단 `운항 스케줄 정보`의 공식 요청·응답 계약을 확인했다.
- KRIC 서비스키와 분리된 `DataGoKrMaritimeClient`를 추가해 항구, 터미널, 선박종류, 국내선박 계획 운항, 연안여객선 운항 스케줄을 typed model로 반환한다.
- `DATA_GO_KR_SERVICE_KEY`는 로컬 `python-datagokr-api` 설정에 존재함만 확인했고, 값·실제 응답은 문서나 fixture에 남기지 않았다.
- KOMSA 운항 스케줄은 개발계정 일일 100건 안내를 문서화했으며, 라이브러리는 자동 재시도나 자동 페이지 순회를 구현하지 않았다.
- 공용 키로 항구·국내선박 운항은 각각 1건의 성공 응답을, KOMSA 운항 스케줄은 공식 `153` 빈 결과를 확인했다. `153`은 스키마/인증 오류와 구분해 빈 tuple로 반환한다.
- 적대적 리뷰에서 지적된 임의 endpoint·redirect 키 유출 경계를 제거했다. maritime client는 고정 공식 endpoint만 사용하고 요청별 redirect를 거부한다. typed 필수 필드와 충돌하는 KOMSA `filters`도 public API에서 제외했다.
- KOMSA 성공 응답 live 검증은 공식 운항 정보에 기재된 공개 여객선명 `코리아프라이드`를 기본 대상으로 사용하고, 환경변수로 교체할 수 있게 했다. 스케줄이 존재하면 날짜·출항시각·여객선 코드·명칭을 함께 검증한다.
- `kor-travel-transport`의 에이전트 진입·문서·리뷰 구조를 KRIC provider 책임에 맞춰 도입했다.
- 코드 구현 전 역 위치·노선·시간표·편의시설 P0 범위와 사용자 신청 API를 문서화했다.
- 서비스키 신청·실제 호출·좌표 CRS 변환은 수행하지 않았다.
- `KricClient`와 역 위치·노선·시간표·편의시설 typed parser를 추가했다. 무효 서비스키의
  실제 JSON 오류 envelope는 확인했지만, 실제 성공 응답 fixture와 공개 파일 parser는
  서비스키 발급 뒤 별도 검증한다.
- KRIC 파일데이터를 재조사해 업데이트 주기가 없는 `1294` 전국 도시광역철도 역사정보 XLSX를
  저빈도 기준정보의 우선 원본으로 정했다. 인증키 없는 다운로드·typed parser를 추가했고,
  파일 표시 식별자와 Open API 코드를 섞지 않도록 분리했다.
- 적대적 리뷰에서 확인한 Excel 역 번호 0 패딩 손실과 대용량 XLSX 위험을 수정했다. 스트리밍
  다운로드, 압축 해제·행·열 상한, 입력 예외 정규화를 추가해 주기 수집 경계를 강화했다.
- 공개 파일 URL을 KRIC `data.kric.go.kr` HTTPS 호스트로 제한하고, 잘못된 URL·timeout을
  provider 예외로 정규화했다.
- 주입된 HTTP client의 redirect 설정으로 호스트 제한이 우회되지 않도록, 파일 다운로드의
  redirect를 명시적으로 거부했다.
