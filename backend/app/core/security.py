"""비밀번호 해싱과 JWT 발급·검증 (CLAUDE.md 디렉토리 규격: core/security.py).

이 모듈의 책임은 **자격증명을 다루는 원시 연산** 둘뿐이다.

    1. 비밀번호  — bcrypt 해시 생성 / 검증
    2. 액세스 토큰 — HS256 발급 / 검증

**여기에 들어오지 않는 것**

| 관심사 | 소관 |
|---|---|
| 비밀번호 길이·형식 검증(8~64자, UTF-8 72바이트) | `schemas/auth.py` |
| 이메일 조회·중복 판정 | `endpoints/auth.py` |
| 요청 헤더에서 토큰 추출 | `core/dependencies.py` |

길이 검증을 여기에 두지 않는 이유: 이 모듈은 **이미 정당하다고 판정된 값**을
해시로 바꾸는 일만 한다. 입력 규격 판정은 요청 경계(Pydantic)에서 하는 것이
FastAPI의 층 구분이고, 여기서 또 하면 같은 규칙이 두 곳에 적히게 된다
(CLAUDE.md: *"한 사실이 여러 문서에 적히면 한 곳을 원본으로 삼는다"*).

---

### ⚠️ bcrypt는 72바이트를 넘는 입력을 **조용히 잘라낸다**

실측(9/11, passlib 1.7.4 + bcrypt 4.2.0): 73바이트 비밀번호를 해시하면
**예외 없이** 해시가 만들어지고, 그 해시는 **72바이트 접두사로도 검증을
통과**한다. 즉 73자째부터는 무엇을 넣어도 같은 해시다.

`hash_password`는 이것을 막지 않는다. **`PASSWORD_TOO_LONG`(400) 판정이
`schemas/auth.py`에 반드시 있어야 하는 이유가 이것**이다
(`docs/api_contract.md` 1.1절). 그 검증이 빠지면 사용자는 긴 비밀번호를
썼다고 믿지만 실제 강도는 72바이트에서 멈추며, **원인을 알 수 없는 종류의
문제**가 된다.

### ⚠️ 기동 시 passlib이 트레이스백을 한 번 뱉는다 — 정상이다

    (trapped) error reading bcrypt version
    AttributeError: module 'bcrypt' has no attribute '__about__'

`passlib 1.7.4`가 `bcrypt.__about__.__version__`으로 버전을 읽는데
`bcrypt 4.x`가 그 속성을 없앴다. **passlib이 스스로 trap해 로그로만 남기며
해시·검증은 정상 동작한다**(9/10·9/11 두 차례 실측). 버그로 오인하거나
우회를 시도하지 말 것 — 버전을 내리면 bcrypt 보안 수정이 빠지고, 경고를
끄면 진짜 백엔드 로딩 실패까지 함께 가려진다.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from jose import ExpiredSignatureError, JWTError, jwt
from passlib.context import CryptContext

from app.core.config import settings
from app.core.exceptions import AppError

logger = logging.getLogger(__name__)

# 토큰을 신뢰할 수 없을 때 내보내는 **유일한 문구**.
#
#   만료와 서명 무효를 **응답에서 구분하지 않는다.** 9/11 크로스체크(09-10)
#   에서 확인된 것 — `message`는 한국어 산문이라 클라이언트가 문자열 매칭
#   말고는 읽을 방법이 없고, 실제로 프론트는 이 값을 쓰지 않는다
#   (`client.ts`의 401 인터셉터가 `reason=expired`를 무조건 붙이고
#   `Login.tsx`는 그 쿼리로 안내 문구를 정한다). 즉 **서버가 애써 만든
#   구분이 사용자에게 전달되지 않고 버려지며, 로그와 공격자에게만 보였다.**
#
#   문구는 "다시 로그인" 쪽으로 잡는다. 사용자가 할 수 있는 행동이 그것
#   하나뿐이라, 만료든 위조든 안내가 같아야 한다.
_TOKEN_REJECTED_MESSAGE = "인증이 만료되었거나 유효하지 않습니다. 다시 로그인해 주세요."

# ──────────────────────────────────────────────────────────────────────
# 예외 — api_contract 1.1절 기준 **둘 다 401 UNAUTHORIZED**로 나간다
# ──────────────────────────────────────────────────────────────────────


class TokenError(AppError):
    """토큰을 신뢰할 수 없다.

    api_contract 1.1절은 **토큰 없음·만료·서명 무효를 모두 같은
    `401 UNAUTHORIZED`**로 규정한다. 아래 두 하위 예외로 원인을 나누는 것은
    **로그와 테스트를 위한 내부 구분**이며, 응답에서는 구분되지 않는다.

    구분을 응답으로 내보내지 않는 이유는 `INVALID_CREDENTIALS`가
    이메일/비밀번호를 구분하지 않는 것과 같다 — *"서명은 맞는데 만료됐다"*는
    답은 공격자에게 **비밀키가 유효하다는 사실**을 알려준다.
    """

    status_code = 401
    code = "UNAUTHORIZED"


class TokenExpiredError(TokenError):
    """서명은 유효하지만 `exp`가 지났다. 재로그인이 필요하다."""


class TokenInvalidError(TokenError):
    """서명 불일치·형식 오류·`sub` 누락 등. 위조이거나 다른 키로 만든 토큰이다."""


# ──────────────────────────────────────────────────────────────────────
# 비밀번호
# ──────────────────────────────────────────────────────────────────────

_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    """평문 비밀번호를 bcrypt 해시로 바꾼다.

    **길이를 검증하지 않는다**(모듈 docstring 참고). 72바이트를 넘는 입력은
    호출 전에 `schemas/auth.py`가 이미 거부했어야 한다.

    반환값에는 알고리즘·cost·salt가 모두 들어 있어(`$2b$12$...`) 별도 salt
    컬럼이 필요 없다. `HOSTS.password_hash`는 `VARCHAR(255)`이고 bcrypt
    해시는 60자라 여유가 충분하다.
    """
    return _pwd_context.hash(password)


def verify_password(plain_password: str, password_hash: str) -> bool:
    """평문과 저장된 해시가 일치하는가.

    해시 형식이 깨져 있어도 **예외를 올리지 않고 `False`를 반환**한다.
    `INVALID_CREDENTIALS`(401)로 처리되어야 할 상황이 500으로 새어 나가면
    로그인 화면이 "서버 오류"를 띄우게 된다.
    """
    try:
        return _pwd_context.verify(plain_password, password_hash)
    except ValueError:
        # passlib이 해시를 파싱하지 못한 경우(잘린 값, 다른 알고리즘 등).
        return False


# ──────────────────────────────────────────────────────────────────────
# JWT
# ──────────────────────────────────────────────────────────────────────


def create_access_token(
    host_id: int,
    *,
    expires_delta: timedelta | None = None,
) -> str:
    """`host_id`를 담은 액세스 토큰을 발급한다.

    **클레임은 등록 클레임 3개뿐이다** — `sub`·`exp`·`iat`. 이름·이메일을
    넣지 않는 것은 의도된 선택이다. 프론트는 토큰을 디코딩하지 않고
    `GET /auth/me`로 사용자 정보를 받으며(api_contract 1.4절), 토큰에
    복제해 두면 이름을 바꿨을 때 **만료(24시간) 전까지 옛 값이 따라다닌다.**

    `sub`는 **문자열**로 넣는다(RFC 7519가 StringOrURI로 규정). 꺼낼 때
    `int()`로 되돌린다.

    :param expires_delta: 만료 간격 재정의. 기본값은
        `settings.ACCESS_TOKEN_EXPIRE_MINUTES`(1440분 = 24시간)이며,
        **테스트가 만료된 토큰을 만들 때 음수 간격을 주는 통로**이기도 하다.
        시스템 시계를 조작하는 방법(freezegun 등)을 쓰지 않기 위한 것으로,
        의존성을 늘리지 않고 순수 함수로 남길 수 있다.
    """
    now = datetime.now(timezone.utc)
    if expires_delta is None:
        expires_delta = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

    payload = {
        "sub": str(host_id),
        "iat": now,
        "exp": now + expires_delta,
    }
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def decode_access_token(token: str) -> int:
    """토큰을 검증하고 `host_id`를 복원한다.

    서명·만료를 **서버만** 판정할 수 있으므로 이 함수를 거치지 않고 토큰
    내용을 신뢰하는 경로를 만들지 않는다.

    :raises TokenExpiredError: `exp`가 지났다(서명 자체는 유효).
    :raises TokenInvalidError: 서명 불일치, 형식 오류, `sub` 누락·비정수.

    `ExpiredSignatureError`를 **먼저** 잡는다 — `JWTError`의 하위 클래스라
    순서를 바꾸면 만료가 전부 `TokenInvalidError`로 뭉개진다.

    **예외 타입은 계속 나누되 `message`는 하나로 통일한다**(9/11). 구분이
    필요한 곳은 **운영 로그**다 — "만료가 몰린다"와 "위조 시도가 들어온다"는
    대응이 완전히 다르므로 그쪽에는 남긴다. 응답에서 나누지 않는 이유는
    `_TOKEN_REJECTED_MESSAGE` 주석 참고.
    """
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
        )
    except ExpiredSignatureError as exc:
        # 만료는 정상 운영 중에도 늘 생긴다 — info로 남긴다.
        logger.info("토큰 거부: 만료(exp 경과)")
        raise TokenExpiredError(_TOKEN_REJECTED_MESSAGE) from exc
    except JWTError as exc:
        # 서명 불일치는 위조이거나 키가 갈린 것이다. 둘 다 조사가 필요하다.
        logger.warning("토큰 거부: 서명·형식 무효 (%s)", type(exc).__name__)
        raise TokenInvalidError(_TOKEN_REJECTED_MESSAGE) from exc

    subject = payload.get("sub")
    if subject is None:
        logger.warning("토큰 거부: sub 클레임 없음")
        raise TokenInvalidError(_TOKEN_REJECTED_MESSAGE)

    try:
        return int(subject)
    except (TypeError, ValueError) as exc:
        logger.warning("토큰 거부: sub가 정수가 아님")
        raise TokenInvalidError(_TOKEN_REJECTED_MESSAGE) from exc
