# 현재 상태

- JSON 요청·오류 envelope·typed parser의 초기 구현이 완료됐다.
- 인증키가 없는 공개 XLSX dataset `1294`(전국 도시광역철도 역사정보) 다운로드와 typed parser가
  완료됐다. 파일의 표시 식별자는 API 코드와 별개로 보존한다.
- 서비스키 신청 전 단계이며 실제 성공 envelope와 역 편의시설 Open API 세부 필드는 키가 제거된
  fixture로 확인되지 않았다.

# 다음 한 작업

dataset `916` 이후 전국 역사 편의시설 파일의 실제 헤더·갱신 계약을 확인하고, 우선순위 시설
파일의 typed parser를 추가한다. 서비스키가 발급되면 P0 API live smoke도 병행한다.
