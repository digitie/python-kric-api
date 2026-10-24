# 코레일 공개 역 안내

예약·로그인 API와 구분한 키 없는 `KorailPublicClient`를 제공한다. 공개 웹의 실제 요청 계약을
확인한 두 GET 경로만 사용한다. 요청 간 최소 1초, 응답 1MiB 상한, 자동 재시도·redirect 없음이다.
401/403/429는 실패로 구분하고 우회하지 않는다. 기존 KRIC API의 인증·호출 보호는 바꾸지 않는다.

- [공식 역 안내](https://www.korail.com/ticket/train/stationGuide/station/view?stationSeq=10281321)
- 공개 좌표: `https://www.korail.com/public/st_info/station_data.json`, `stns.stn`.
- 공개 안내: `https://www.korail.com/com/userStation.do`, `mode=list`, `page`, `schOpt2`, `schFld`, 빈 `schStr`.
- `strResult=SUCC`, `totcnt`, `lineList`, `resultList`를 검증한다. 누락·잘린 페이지는 정상 빈 결과가 아니다.
- `kind=ktx`의 분류는 경부선 등 노선이다. `kind=main`의 분류는 수도권·충청권 등 권역이며 선로 노선으로 표시하지 않는다.
- 전체 분류 목록 조회는 첫 페이지만 사용한다. 선택 분류의 역은 페이지를 모두 확인하고 중복·분류 불일치를 거절한다.
- 같은 코레일 공개 자료의 정확히 같은 역명이 유일할 때만 좌표를 연결한다. 중복·누락은 빈 좌표로 남긴다.
- `stationSeq`, 공개 좌표 `stn_cd`, TAGO `nodeid`, KRIC 역 코드는 서로 다른 식별자다. 코드 변환을 추정하지 않는다.
- 주소·전화번호는 공개 안내 문자열을 보존한다. HTML 본문·예약·요금·실시간 운행 정보는 파싱하지 않는다.

2026-10-24 실제 공개 조회에서 KTX 분류 7개·전체 65역, 경부선 19역의 주소·전화번호 19개를 확인했다.
일반철도는 전체 316역과 5개 권역 분류를 확인했다. 좌표는 선로 경로나 정차 순서를 뜻하지 않는다.
운영 반영과 소비자 지도 UI 검증은 Transport에서 별도로 수행한다.
