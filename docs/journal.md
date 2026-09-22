# 작업 기록

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
