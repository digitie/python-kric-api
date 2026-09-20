# CLAUDE.md — python-kric-api 진입 요약

정식 작업 정책은 `AGENTS.md`, 상세 구현 규칙은 `SKILL.md`, 현재 순서는
`docs/implementation-plan.md`와 `docs/resume.md`가 갖는다.

`python-kric-api`는 KRIC의 역 위치, 노선 구성, 운행 시간표, 역 편의시설을 파싱하는
Python provider 라이브러리다. 국내 여행 통합 교통정보의 주기 수집·자체 DB 저장·즉시 제공과
통계는 소비자인 `kor-travel-transport`의 책임이며, KRIC 응답 계약과 파싱은 이 저장소의
책임이다.

1. `codex/` 브랜치와 Draft PR로 작업한다.
2. 서비스키를 커밋하거나 fixture에 남기지 않는다.
3. 코드·순서·원시 좌표를 추정 변환하지 않는다.
4. fixture 테스트, 타입 검사, 적대적 리뷰 두 건, 허가된 live 검증 후에만 머지한다.

우선 구현 계획과 신청 대상 API는 `docs/implementation-plan.md`에서 확인한다.
