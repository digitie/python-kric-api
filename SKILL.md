# SKILL — python-kric-api 에이전트 매뉴얼

## 1. 데이터 모델 원칙

- 역 식별은 운영기관·노선·역 코드의 provider 문맥을 보존한다. 표시 이름만으로 동일성을
  판단하지 않는다.
- 노선 구성은 `routCd`별로 묶고 `stinConsOrdr`를 정렬 키로 사용한다. 같은 역이 순환선이나
  분기에서 반복될 수 있으므로 중복을 제거하지 않는다.
- 시간표는 원본 `dayCd`, 도착·출발 문자열, 기점·종점·열차번호를 보존한다. 서비스 날짜가 없는
  시각은 aware datetime으로 추정하지 않는다.
- 편의시설의 분류 코드와 설명을 함께 보존한다. 알 수 없는 값은 제거하지 않고 원시 값과 함께
  안전하게 노출한다.

## 2. 계층과 책임

```text
src/kric/client.py       요청·서비스키·HTTP 오류
src/kric/models.py       공개 typed dataclass
src/kric/parse.py        API·파일 원시 응답 → 모델 변환
src/kric/files.py        공개 파일 다운로드/형식별 parser
src/kric/exceptions.py   인증·할당량·네트워크·서버·스키마 오류
tests/fixtures/          키가 제거된 실제 구조의 네트워크 없는 fixture
```

HTTP 상태/body 오류 변환은 `client.py`의 한 경계에 둔다. 파서는 원시 문자열을 공개 모델에
그대로 흘리지 않되, 코드와 원시 좌표처럼 의미가 보존돼야 하는 값은 `str`/원시 필드로 유지한다.

## 3. 구현 금지

1. 인증키·쿠키·사용자 데이터·원문 비밀값을 커밋하지 않는다.
2. `mapCordX`/`mapCordY`를 CRS 근거 없이 WGS84로 변환하지 않는다.
3. 재시도로 401/403/429 또는 할당량 제한을 숨기지 않는다.
4. 빈 결과와 스키마 오류를 같은 것으로 취급하지 않는다.
5. 외부 앱의 DB 저장·스케줄링·FastAPI adapter를 이 provider에 넣지 않는다.

## 4. 검증 게이트

```bash
python -m compileall src/kric tests
python -m mypy src/kric
python -m pytest --cov=kric --cov-fail-under=90
```

live 테스트는 서비스키가 명시적으로 제공된 경우에만 실행하고, 호출량과 결과 식별자를
로그/문서에 과도하게 남기지 않는다.
