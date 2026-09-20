# 완료 작업

## T-001 KRIC provider 라이브러리 기반

- 에이전트 진입 구조, 구현 계획, 비동기 JSON client와 typed parser scaffold를 추가했다.
- 역 위치, 도시철도 노선, 역사/열차 시간표, 역 편의시설 operation의 요청 경로와 오류 envelope를
  네트워크 없는 테스트로 검증했다.
- 실제 서비스키와 성공 응답 fixture, 공개 파일 parser는 포함하지 않았다.

## T-005 무인증 역사 기준정보 파일 수집

- 공개 XLSX dataset `1294`(전국 도시광역철도 역사정보)의 실제 다운로드 URL·29개 열·갱신
  계약을 확인했다.
- `KricFileClient`와 `FileStationInfo`를 추가해 인증키 없이 파일을 내려받고 파싱한다.
- 파일의 표시명·역 번호를 Open API 코드로 추정하지 않고, 알 수 없는 열을 원문으로 보존한다.
