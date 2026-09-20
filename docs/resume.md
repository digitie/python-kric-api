# 현재 상태

- JSON 요청·오류 envelope·typed parser의 초기 구현이 완료됐다.
- 서비스키 신청 전 단계이며 실제 성공 envelope, 역 편의시설 세부 필드, 공개 파일 parser는
  키가 제거된 fixture로 확인되지 않았다.

# 다음 한 작업

서비스키를 신청하고 P0 API의 실제 성공 응답을 키가 제거된 fixture로 확보해 parser 계약과
`@pytest.mark.live` smoke를 확정한다.
