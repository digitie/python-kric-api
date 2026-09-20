# 구조

이 저장소는 KRIC provider 라이브러리만 제공한다. 공개 API 요청과 파일 자료의 원시 응답을
검증·파싱해 typed model로 만들고, 소비 서비스가 이를 저장·분석하도록 한다.

```text
KRIC Open API ─┐
               ├─ client/files → parse → models → 소비자
KRIC 공개 파일 ─┘                              └─ kor-travel-transport
```

API 응답은 JSON/XML 형식이 확인된 뒤 한 곳에서 정규화한다. 공개 파일은 형식(CSV/XLSX 등)과
갱신 시각을 명시적으로 기록한다. 두 원본을 암묵적으로 결합하지 않는다.
