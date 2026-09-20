"""KRIC 요청·응답 오류를 호출자가 구분할 수 있게 한다."""


class KricError(Exception):
    """KRIC provider의 모든 예외 기반 클래스."""


class KricAuthError(KricError):
    """서비스키가 없거나 유효하지 않거나 접근이 거부된 경우."""


class KricRateLimitError(KricError):
    """호출량 또는 할당량 제한을 받은 경우."""


class KricInvalidParameterError(KricError):
    """요청 전에 발견한 잘못된 인자."""


class KricNetworkError(KricError):
    """KRIC 서버까지 연결하거나 응답을 읽지 못한 경우."""


class KricServerError(KricError):
    """KRIC 오류 응답 또는 문서화되지 않은 응답 구조."""
