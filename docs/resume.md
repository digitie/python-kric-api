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
