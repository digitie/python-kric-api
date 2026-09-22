# 현재 상태

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
  운항 시간표·계획 운항은 quota를 예측할 수 없으므로 요청한 한 페이지만 반환한다.
- 서비스키 신청 전 단계이며 실제 성공 envelope와 역 편의시설 Open API 세부 필드는 키가 제거된
  fixture로 확인되지 않았다.

# 다음 한 작업

RustFS 공개 파일 저장 변경의 CI·독립 리뷰·머지 뒤 소비 서비스의 공용 RustFS 설정을 연결하고,
dataset `916` 이후 전국 역사 편의시설 파일의 실제 헤더·갱신 계약을 확인한다.
