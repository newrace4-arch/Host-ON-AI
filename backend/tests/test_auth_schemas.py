"""`schemas/auth.py` 회귀 테스트 -- 인증 DTO와 비밀번호 이중 검증.

**DB를 쓰지 않는다.** 대상이 순수한 Pydantic 모델이라 Docker가 떠 있지
않아도 돈다.

### 이 파일이 지키는 것

가장 중요한 것은 **한글 경계값 두 건**이다. `PASSWORD_MAX_LENGTH`(64자)와
`PASSWORD_MAX_BYTES`(72바이트)는 서로 다른 조건이며, 한글은 한 글자가
3바이트라 **24자(72B)는 통과하고 25자(75B)는 거부**되는 구간이 실재한다.
두 조건을 하나로 합치거나 순서를 바꾸면 이 두 테스트가 깨진다.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.schemas.auth import (
    HostResponse,
    InvalidEmailFormatError,
    InvalidPasswordFormatError,
    LoginRequest,
    PasswordTooLongError,
    SignupRequest,
    TokenResponse,
)

VALID = {"email": "host@example.com", "password": "hoston-1234", "name": "신경주"}


def _signup(**overrides):
    return SignupRequest(**{**VALID, **overrides})


# -- 정상 경로 --------------------------------------------------------


def test_valid_signup_passes():
    """정상 가입 요청이 통과한다."""
    req = _signup()

    assert req.email == "host@example.com"
    assert req.password == "hoston-1234"
    assert req.name == "신경주"


def test_valid_login_passes():
    req = LoginRequest(email="host@example.com", password="hoston-1234")

    assert req.email == "host@example.com"


# -- 비밀번호: 글자 수 (INVALID_PASSWORD_FORMAT) -----------------------


def test_seven_char_password_is_invalid_format():
    """7자는 `INVALID_PASSWORD_FORMAT`이다."""
    with pytest.raises(InvalidPasswordFormatError) as exc:
        _signup(password="a" * 7)

    assert exc.value.code == "INVALID_PASSWORD_FORMAT"
    assert exc.value.status_code == 400


def test_sixty_five_char_password_is_invalid_format():
    """65자는 `INVALID_PASSWORD_FORMAT`이다."""
    with pytest.raises(InvalidPasswordFormatError) as exc:
        _signup(password="a" * 65)

    assert exc.value.code == "INVALID_PASSWORD_FORMAT"


@pytest.mark.parametrize("length", [8, 64])
def test_character_length_boundaries_pass(length):
    """8자와 64자는 경계 안쪽이므로 통과한다(ASCII라 바이트도 같다)."""
    assert _signup(password="a" * length).password == "a" * length


# -- 비밀번호: UTF-8 바이트 (PASSWORD_TOO_LONG) ------------------------


def test_korean_25_chars_is_password_too_long():
    """**한글 25자 = 75바이트** -> `PASSWORD_TOO_LONG`.

    글자 수(25)는 8~64 안쪽이라 **글자 수 검증만으로는 절대 걸리지 않는다.**
    이 테스트가 실패하면 bcrypt가 조용히 잘라내는 구간이 열린 것이다.
    """
    password = "가" * 25
    assert len(password) == 25
    assert len(password.encode("utf-8")) == 75

    with pytest.raises(PasswordTooLongError) as exc:
        _signup(password=password)

    assert exc.value.code == "PASSWORD_TOO_LONG"
    assert exc.value.status_code == 400


def test_korean_24_chars_passes():
    """**한글 24자 = 72바이트** -> 경계값, 통과한다.

    72바이트는 bcrypt가 그대로 쓰는 마지막 길이다. 여기서 거부하면
    사용할 수 있는 비밀번호를 막는 것이 된다.
    """
    password = "가" * 24
    assert len(password.encode("utf-8")) == 72

    assert _signup(password=password).password == password


def test_two_conditions_have_different_codes():
    """두 조건이 **서로 다른 코드**로 갈린다.

    하나의 validator로 묶으면 사용자는 64자 이내인데 왜 거부됐는지 알 수
    없다. 같은 코드가 나오면 이 테스트가 깨진다.
    """
    with pytest.raises(InvalidPasswordFormatError) as short:
        _signup(password="a" * 7)
    with pytest.raises(PasswordTooLongError) as long_bytes:
        _signup(password="가" * 25)

    assert short.value.code != long_bytes.value.code


def test_both_violated_reports_character_length_first():
    """둘 다 위반하면 **글자 수**를 알려준다(고칠 수 있는 단위).

    한글 100자 = 300바이트로 두 조건을 모두 위반한다. "72바이트 초과"만
    알려주면 몇 글자를 지워야 하는지 알 수 없다.
    """
    with pytest.raises(InvalidPasswordFormatError):
        _signup(password="가" * 100)


def test_password_whitespace_is_not_stripped():
    """비밀번호의 앞뒤 공백을 조용히 다듬지 않는다.

    다듬으면 사용자가 입력한 것과 저장된 것이 달라진다.
    """
    assert _signup(password="  spaced  ").password == "  spaced  "


# -- 이메일 (INVALID_EMAIL_FORMAT) -------------------------------------


@pytest.mark.parametrize(
    "bad",
    [
        "not-an-email",
        "@example.com",
        "host@",
        "host@example",
        "host example@x.com",
        "host@@example.com",
        "host@.com",
        "",
        "   ",
    ],
)
def test_invalid_email_is_rejected(bad):
    with pytest.raises(InvalidEmailFormatError) as exc:
        _signup(email=bad)

    assert exc.value.code == "INVALID_EMAIL_FORMAT"
    assert exc.value.status_code == 400


@pytest.mark.parametrize(
    "good",
    [
        "host@example.com",
        "host+airbnb@gmail.com",
        "host.name@sub.example.co.kr",
        "h1@x-y.com",
    ],
)
def test_realistic_emails_are_accepted(good):
    """정상 주소를 막지 않는다 -- '+' 태그와 하이픈 도메인을 포함해서."""
    assert _signup(email=good).email == good


def test_email_is_normalized_to_lowercase():
    """`HOSTS.email`이 UNIQUE이므로 대소문자로 계정이 갈리면 안 된다."""
    assert _signup(email="  HOST@Example.COM  ").email == "host@example.com"


def test_login_normalizes_email_the_same_way():
    """가입과 로그인이 같은 정규화를 지나야 대문자 입력이 실패하지 않는다."""
    assert LoginRequest(email="HOST@EXAMPLE.COM", password="x").email == (
        "host@example.com"
    )


def test_login_does_not_validate_password_length():
    """로그인은 길이를 보지 않는다.

    여기서 400/401이 갈리면 **틀린 비밀번호의 길이를 외부에서 추측**할 수
    있게 된다.
    """
    assert LoginRequest(email="host@example.com", password="1").password == "1"


# -- name ---------------------------------------------------------------


def test_missing_name_is_rejected():
    """`name`이 없으면 거부한다(`HOSTS.name`이 NOT NULL).

    `name`에는 전용 에러 코드가 없으므로(1.1절 표) `AppError`가 아니라
    Pydantic의 `ValidationError`로 나가고, `main.py`가 400
    `VALIDATION_ERROR`로 감싼다.
    """
    with pytest.raises(ValidationError) as exc:
        SignupRequest(email=VALID["email"], password=VALID["password"])

    assert exc.value.errors()[0]["loc"] == ("name",)


@pytest.mark.parametrize("bad", ["", "   "])
def test_blank_name_is_rejected(bad):
    """공백만 있는 이름도 거부한다 -- strip 후 비면 NOT NULL을 만족하지 못한다."""
    with pytest.raises(ValidationError):
        _signup(name=bad)


def test_name_over_100_chars_is_rejected():
    """`HOSTS.name`이 VARCHAR(100)이라 넘으면 DB에서 터진다."""
    with pytest.raises(ValidationError):
        _signup(name="가" * 101)


def test_name_exactly_100_chars_passes():
    """경계값 -- 100자는 컬럼에 들어가므로 통과해야 한다."""
    assert _signup(name="가" * 100).name == "가" * 100


def test_name_is_stripped():
    assert _signup(name="  신경주  ").name == "신경주"


# -- 응답 DTO -----------------------------------------------------------


def test_host_response_never_exposes_password_hash():
    """**`password_hash`가 응답에 절대 포함되지 않는다.**

    ORM 객체를 흉내 낸 객체에 `password_hash`와 `created_at`을 넣어도
    선언된 3필드만 나가야 한다.
    """

    class FakeHost:
        host_id = 1
        email = "host@example.com"
        name = "신경주"
        password_hash = "$2b$12$super-secret-hash"
        created_at = "2026-09-11T00:00:00Z"

    dumped = HostResponse.model_validate(FakeHost()).model_dump()

    assert set(dumped) == {"host_id", "email", "name"}
    assert "password_hash" not in dumped
    assert "super-secret-hash" not in str(dumped)


def test_token_response_shape_matches_contract():
    """api_contract 1.2·1.3절의 응답 구조 그대로다."""
    dumped = TokenResponse(
        access_token="eyJ...",
        host=HostResponse(host_id=1, email="host@example.com", name="신경주"),
    ).model_dump()

    assert set(dumped) == {"access_token", "token_type", "host"}
    assert dumped["token_type"] == "bearer"
    assert set(dumped["host"]) == {"host_id", "email", "name"}
