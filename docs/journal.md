# 작업 기록

## 2026-09-20

- `kor-travel-transport`의 에이전트 진입·문서·리뷰 구조를 KRIC provider 책임에 맞춰 도입했다.
- 코드 구현 전 역 위치·노선·시간표·편의시설 P0 범위와 사용자 신청 API를 문서화했다.
- 서비스키 신청·실제 호출·좌표 CRS 변환은 수행하지 않았다.
- `KricClient`와 역 위치·노선·시간표·편의시설 typed parser를 추가했다. 무효 서비스키의
  실제 JSON 오류 envelope는 확인했지만, 실제 성공 응답 fixture와 공개 파일 parser는
  서비스키 발급 뒤 별도 검증한다.
