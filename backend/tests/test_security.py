"""`core/security.py` 회귀 테스트 — 비밀번호 해싱과 JWT 발급·검증.

**DB를 쓰지 않는다.** 대상이 전부 순수 함수라 `conftest.py`의 `db`/`host`
픽스처가 필요 없고, 붙이면 Docker가 떠 있어야만 도는 테스트가 된다.

### 만료 토큰을 만드는 방법

`create_access_token(expires_delta=...)`에 **음수 간격**을 준다. 시스템
시계를 조작하지 않는다 —

- `freezegun`은 `requirements.txt`에 없다. 만료 테스트 하나를 위해
  의존성을 늘리지 않는다.
- `datetime`을 monkeypatch하면 `jose` 내부가 보는 시각까지 함께 바뀌어
  **무엇을 검증하는 테스트인지 흐려진다.**

음수 간격은 `exp < iat`인 토큰을 실제로 발급해 `jose`의 만료 판정을
**있는 그대로** 통과시킨다. 프로덕션 코드에 테스트 전용 우회로를 뚫는
것이 아니라, 만료 간격을 인자로 받는 **일반적인 서명**을 쓰는 것이다.
"""

from __future__ import annotations

from datetime import timedelta

import pytest
from jose import jwt

from app.core.config import settings
from app.core.security import (
    TokenExpiredError,
    TokenInvalidError,
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)

PASSWORD = "hoston-dev-1234"


# ── 비밀번호 ──────────────────────────────────────────────────────────


def test_hash_then_verify_passes():
    """해시를 만들고 같은 평문으로 검증하면 통과한다."""
    assert verify_password(PASSWORD, hash_password(PASSWORD)) is True


def test_wrong_password_is_rejected():
    """틀린 비밀번호는 거부된다."""
    assert verify_password("wrong-password", hash_password(PASSWORD)) is False


def test_hash_is_not_plaintext_and_is_salted():
    """해시에 평문이 남지 않으며, 같은 비밀번호라도 매번 다른 해시가 나온다.

    salt가 빠지면 같은 비밀번호를 쓴 계정이 해시만 봐도 드러난다.
    """
    first = hash_password(PASSWORD)
    second = hash_password(PASSWORD)

    assert PASSWORD not in first
    assert first.startswith("$2b$")
    assert first != second
    # 서로 다른 해시가 둘 다 같은 평문을 검증한다(salt가 해시에 포함된 증거).
    assert verify_password(PASSWORD, first)
    assert verify_password(PASSWORD, second)


def test_malformed_hash_returns_false_not_raises():
    """깨진 해시는 예외가 아니라 False다.

    `INVALID_CREDENTIALS`(401)여야 할 상황이 500으로 새어 나가면 로그인
    화면이 "서버 오류"를 띄운다.
    """
    assert verify_password(PASSWORD, "not-a-real-hash") is False


# ── JWT 발급·검증 ─────────────────────────────────────────────────────


def test_token_roundtrip_restores_host_id():
    """발급한 토큰을 검증하면 host_id가 그대로 복원된다."""
    assert decode_access_token(create_access_token(42)) == 42


def test_token_claims_are_registered_only():
    """클레임은 `sub`·`exp`·`iat` 셋뿐이고, `sub`는 문자열이다.

    이름·이메일을 토큰에 복제하지 않는다는 설계를 고정한다(api_contract
    1.4절 — 사용자 정보는 `GET /auth/me`로 받는다).
    """
    payload = jwt.decode(
        create_access_token(7),
        settings.JWT_SECRET_KEY,
        algorithms=[settings.JWT_ALGORITHM],
    )

    assert set(payload) == {"sub", "exp", "iat"}
    assert payload["sub"] == "7"
    assert payload["exp"] > payload["iat"]


def test_default_expiry_follows_settings():
    """만료 간격을 하드코딩하지 않고 `ACCESS_TOKEN_EXPIRE_MINUTES`를 따른다."""
    payload = jwt.decode(
        create_access_token(1),
        settings.JWT_SECRET_KEY,
        algorithms=[settings.JWT_ALGORITHM],
    )

    expected = settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
    # iat/exp는 초 단위 정수라 반올림으로 1초까지 어긋날 수 있다.
    assert abs((payload["exp"] - payload["iat"]) - expected) <= 1


def test_expired_token_is_rejected():
    """만료된 토큰은 `TokenExpiredError`다(서명 자체는 유효하다)."""
    expired = create_access_token(42, expires_delta=timedelta(minutes=-1))

    with pytest.raises(TokenExpiredError):
        decode_access_token(expired)


def test_bad_signature_is_rejected():
    """다른 키로 서명한 토큰은 `TokenInvalidError`다."""
    forged = jwt.encode(
        {"sub": "42"},
        "a-different-secret-key",
        algorithm=settings.JWT_ALGORITHM,
    )

    with pytest.raises(TokenInvalidError):
        decode_access_token(forged)


def test_garbage_token_is_rejected():
    """JWT 형태가 아닌 문자열도 `TokenInvalidError`다."""
    with pytest.raises(TokenInvalidError):
        decode_access_token("not.a.token")


def test_token_without_sub_is_rejected():
    """서명은 맞아도 `sub`가 없으면 거부한다.

    `sub`가 없으면 `int(None)`에서 500이 나거나, 더 나쁘게는 호출부가
    `None`을 host_id로 쓰게 된다.
    """
    no_sub = jwt.encode(
        {"foo": "bar"},
        settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )

    with pytest.raises(TokenInvalidError):
        decode_access_token(no_sub)


def test_non_integer_sub_is_rejected():
    """`sub`가 정수로 복원되지 않으면 거부한다."""
    bad_sub = jwt.encode(
        {"sub": "not-a-number"},
        settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )

    with pytest.raises(TokenInvalidError):
        decode_access_token(bad_sub)


# ── 응답 매핑 ─────────────────────────────────────────────────────────


@pytest.mark.parametrize("error_cls", [TokenExpiredError, TokenInvalidError])
def test_both_token_errors_map_to_401_unauthorized(error_cls):
    """만료와 서명 오류를 내부적으로는 나누되 **응답에서는 구분하지 않는다.**

    api_contract 1.1절: 토큰 없음·만료·서명 무효는 모두 `401 UNAUTHORIZED`.
    *"서명은 맞는데 만료됐다"*는 답은 공격자에게 비밀키가 유효하다는
    사실을 알려준다.
    """
    exc = error_cls("무시되는 메시지")

    assert exc.status_code == 401
    assert exc.code == "UNAUTHORIZED"
    assert exc.to_error_body()["code"] == "UNAUTHORIZED"
