# AGENTS.md

`python-kric-api`는 한국철도공사 철도산업정보센터(KRIC) Open API와 공개 파일 자료를
Python 네이티브 타입으로 제공하는 provider 라이브러리다. `kor-travel-transport`가
주기 수집·PostgreSQL 저장·외부 API·통계를 담당하고, 이 저장소는 KRIC 응답의 요청,
검증, 파싱 책임만 가진다.

## 작업 순서와 우선순위

작업 시작 시 `CLAUDE.md` → `AGENTS.md` → `SKILL.md` →
`docs/architecture/architecture.md` → `docs/implementation-plan.md` → 대상 코드를 읽는다.

지시 우선순위는 사용자 요청 > `AGENTS.md` > `SKILL.md` > 구조/계획 문서 > 코드와
테스트다. 모든 Markdown과 Python 문서·주석은 한국어로 작성하며, URL·API operation·필드명
등 원문 식별자는 보존한다.

## 핵심 원칙

- `main`에 직접 push하지 않는다. `codex/` 브랜치, Draft PR, CI, 독립 적대적 리뷰 2건,
  live 검증을 거친 뒤에만 머지한다.
- `serviceKey`와 실제 응답의 개인정보성 값은 코드, fixture, 로그, 문서에 남기지 않는다.
- KRIC 원시 코드(`operatorCd`, `lnCd`, `stinCd`, `routCd`, 열차번호)는 정수로 바꾸지 않는다.
  선행 0과 provider 식별 의미를 보존한다.
- 시간표의 `dayCd`는 공식 의미(7 토요일, 8 평일, 9 공휴일)를 코드와 문서에 함께 보존한다.
  문서화되지 않은 시간 문자열·날짜 문자열을 임의 timezone datetime으로 만들지 않는다.
- `mapCordX`/`mapCordY`의 CRS와 단위는 확정 전 변환하지 않는다. 원시 값을 노출하고
  문서화된 근거가 생긴 뒤에만 변환을 추가한다.
- `routCd`와 `stinConsOrdr`는 노선 구성의 묶음·순서를 함께 나타낸다. 역 이름을 키로
  재구성하거나 순서를 잃지 않는다.
- API와 파일 자료는 서로 다른 원본이다. 파일을 API 응답처럼 추정하거나 API로 덮어쓰지 않는다.
- 접근 거부, 할당량 초과, 스키마 불일치는 빈 결과로 바꾸지 않는다. 명시적 예외로 노출한다.

## 책임 경계

```text
KRIC Open API / 공개 파일 → python-kric-api (요청·파싱·모델·검증)
                           → kor-travel-transport (주기 수집·PostgreSQL·즉시 API·통계)
```

`kor-travel-transport` 안에 KRIC 파서 wrapper를 만들지 않는다. provider 데이터 의미,
필드 정규화, 응답 스키마 검증 문제가 보이면 이 저장소에서 고친다.

## 검증

```bash
python -m compileall src/kric tests
python -m mypy src/kric
python -m pytest --cov=kric --cov-fail-under=90
```

기본 테스트는 fixture 기반이며 네트워크를 사용하지 않는다. 실제 KRIC 호출은 사용자가
발급한 키를 명시적으로 설정한 뒤 `@pytest.mark.live`로만 실행한다.

## 문서와 작업 기록

사용자 가시 API, 데이터 모델, 오류 처리, 수집 계약이 바뀌면 README와 관련 계획/구조 문서를
갱신한다. 작업 완료 시 `docs/journal.md`, `docs/resume.md`, `docs/tasks.md`를 갱신하고
완료 항목은 `docs/tasks-done.md`로 옮긴다.
