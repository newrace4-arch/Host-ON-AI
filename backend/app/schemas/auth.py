"""인증 Request/Response DTO (Pydantic v2, api_contract.md 1절).

## 이 모듈이 지는 책임 — 비밀번호 길이 판정

`core/security.py`가 **일부러 길이를 검증하지 않는다.** 그 판정이 있어야 할
자리가 여기다. 그리고 이 판정은 **있으면 좋은 것이 아니라 없으면 구멍이
뚫리는 것**이다.

9/11 실측(passlib 1.7.4 + bcrypt 4.2.0): 73바이트 비밀번호를 해시하면
**예외 없이** 해시가 만들어지고, 그 해시는 **72바이트 접두사로도 검증을
통과**한다. 즉 bcrypt는 초과분을 조용히 잘라낸다.

사용자는 75바이트짜리 비밀번호를 썼다고 믿지만 실제 강도는 72바이트에서
멈추고, 73자째부터는 무엇을 넣어도 같은 해시가 된다. 게다가 bcrypt·passlib
버전이 바뀌어 절단 동작이 달라지면 **그때부터 기존 계정의 로그인이
불가능해진다.** 어느 쪽도 사용자가 원인을 알 수 없는 종류의 문제다.

### 두 조건을 하나로 묶지 않는다

| 조건 | 코드 | 성격 |
|---|---|---|
| 글자 수 8~64자 | `INVALID_PASSWORD_FORMAT` | 정책. 프론트도 같이 본다 |
| UTF-8 72바이트 초과 | `PASSWORD_TOO_LONG` | **백엔드 전용 판정** |

**서로 다른 조건이지 중복이 아니다.** 한글은 UTF-8에서 한 글자가 3바이트라
**25자만 넘어도 72바이트를 초과**한다(25x3 = 75). "8~64자"를 통과한 한글
비밀번호가 bcrypt에서 잘리는 구간이 **실재한다.** 코드를 하나로 합치면
사용자는 64자 이내인데 왜 거부됐는지 알 수 없다.

---

## 왜 `ValueError`가 아니라 `AppError`를 던지는가

`main.py`의 `RequestValidationError` 핸들러는 **모든 검증 실패를
`VALIDATION_ERROR` 하나로** 변환한다. Pydantic 관례대로 `ValueError`를
던지면 위 코드들이 전부 그 하나로 뭉개져 **api_contract 1.1절이 규정한
에러 코드를 낼 수 없다.**

Pydantic v2는 `ValueError`/`AssertionError`만 `ValidationError`로 감싸고
**그 외 예외는 그대로 통과시킨다.** 통과한 `AppError`는 FastAPI의 본문
검증을 지나 `@app.exception_handler(AppError)`에 잡혀 0절 봉투로 나간다.
9/11에 실제 FastAPI 앱을 세워 확인했다 --

    73바이트 -> 400 {"error": {"code": "PASSWORD_TOO_LONG", ...}}   (AppError)
    7글자    -> 400 {"error": {"code": "VALIDATION_ERROR", ...}}    (ValueError)

**이 예외들의 정식 자리는 `core/exceptions.py`다.** 여기 둔 것은 r47 2단계가
이 파일 하나만 만드는 범위였기 때문이며, 같은 패턴을 쓰는 스키마가 하나 더
생기면 그때 옮긴다.

## `EmailStr`을 쓰지 않는다

`pydantic.EmailStr`은 `email-validator` 패키지를 요구하는데
**`requirements.txt`에 없고 설치돼 있지도 않다**(9/11 확인). 의존성을
늘리지 않고 정규식으로 직접 판정한다. 아래 `_EMAIL_RE` 주석 참고.
"""

from __future__ import annotations

import re

from pydantic import BaseModel, ConfigDict, field_validator

from app.core.exceptions import AppError

# 비밀번호 정책 (api_contract 1.1절). 값을 바꾸면 프론트 검증도 함께 고친다.
PASSWORD_MIN_LENGTH = 8
PASSWORD_MAX_LENGTH = 64
# bcrypt가 조용히 잘라내기 시작하는 지점. 알고리즘의 물리적 한계라
#   위 두 값과 달리 **정책이 아니라 사실**이며, 우리가 정할 수 있는 값이 아니다.
PASSWORD_MAX_BYTES = 72

# HOSTS 컬럼 길이 (명세서 2.1절)
EMAIL_MAX_LENGTH = 255
NAME_MAX_LENGTH = 100

# RFC 5322를 완전히 구현하지 않는다 -- 그것은 정규식으로 할 수 있는 일이
#   아니고, 여기서 필요한 것은 **오타를 걸러내는 것**이다. 실제 배달
#   가능 여부는 어차피 형식으로 알 수 없다.
#
#   과하게 엄격한 패턴은 '+' 태그(host+airbnb@gmail.com)나 하이픈 도메인
#   같은 **정상 주소를 막는다.** 그쪽이 더 나쁜 실패이므로 관대하게 쓴다.
#   요구하는 것은 셋뿐이다 -- '@'가 정확히 하나, 양쪽이 비어 있지 않음,
#   도메인에 점과 2자 이상 TLD가 있음.
_EMAIL_RE = re.compile(
    r"[A-Za-z0-9._%+-]+"
    r"@[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?"
    r"(?:\.[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?)*"
    r"\.[A-Za-z]{2,}"
)


# ----------------------------------------------------------------------
# 예외 -- api_contract 1.1절 에러 코드 표
# ----------------------------------------------------------------------


class InvalidEmailFormatError(AppError):
    """이메일 형식 위반(400)."""

    status_code = 400
    code = "INVALID_EMAIL_FORMAT"


class InvalidPasswordFormatError(AppError):
    """비밀번호 **글자 수**가 8~64자를 벗어났다(400)."""

    status_code = 400
    code = "INVALID_PASSWORD_FORMAT"


class PasswordTooLongError(AppError):
    """비밀번호의 **UTF-8 바이트 길이**가 72를 넘었다(400).

    글자 수 상한과 별개의 조건이다. `InvalidPasswordFormatError`와 합치면
    한글 사용자가 "64자 이내인데 왜 거부됐는지" 알 수 없게 된다.
    """

    status_code = 400
    code = "PASSWORD_TOO_LONG"


# ----------------------------------------------------------------------
# 공용 검증기
# ----------------------------------------------------------------------


def _validate_email(value: str) -> str:
    """이메일을 정규화하고 형식을 판정한다.

    **소문자로 정규화한다.** `HOSTS.email`이 `UNIQUE`인데 대소문자를 그대로
    두면 `Host@x.com`과 `host@x.com`이 **서로 다른 계정**이 된다. 사용자는
    같은 주소라고 믿으므로 "가입했는데 로그인이 안 된다" 또는 "이미 가입된
    이메일인데 중복 검사를 통과한다"가 된다.

    RFC상 로컬 파트는 대소문자를 구분할 수 있으나 실제 메일 제공자는 모두
    구분하지 않는다. **가입과 로그인이 같은 이 함수를 지나므로** 정규화가
    양쪽에 동일하게 적용된다.
    """
    value = value.strip().lower()

    if not value:
        raise InvalidEmailFormatError("이메일을 입력해 주세요.")
    if len(value) > EMAIL_MAX_LENGTH:
        raise InvalidEmailFormatError("이메일이 너무 깁니다.")
    if not _EMAIL_RE.fullmatch(value):
        raise InvalidEmailFormatError("이메일 형식이 올바르지 않습니다.")

    return value


def _validate_password(value: str) -> str:
    """비밀번호의 두 조건을 **순서대로** 판정한다.

    **앞뒤 공백을 다듬지 않는다.** 비밀번호의 공백은 사용자가 의도한
    문자일 수 있고, 조용히 다듬으면 입력한 것과 저장된 것이 달라진다.

    **글자 수를 먼저 본다.** 둘 다 위반하는 경우(예: 한글 100자 = 300바이트)
    사용자가 바로 고칠 수 있는 쪽이 글자 수다 -- 화면에서 셀 수 있는 단위이고,
    64자로 줄이면 바이트 조건도 대개 함께 해소된다. 반대로 "72바이트 초과"만
    알려주면 몇 글자를 지워야 하는지 알 수 없다.
    """
    length = len(value)
    if length < PASSWORD_MIN_LENGTH or length > PASSWORD_MAX_LENGTH:
        raise InvalidPasswordFormatError(
            f"비밀번호는 {PASSWORD_MIN_LENGTH}자 이상 "
            f"{PASSWORD_MAX_LENGTH}자 이하여야 합니다."
        )

    if len(value.encode("utf-8")) > PASSWORD_MAX_BYTES:
        raise PasswordTooLongError(
            "비밀번호가 너무 깁니다. 한글은 한 글자가 3바이트라 "
            f"{PASSWORD_MAX_BYTES // 3}자를 넘으면 사용할 수 없습니다."
        )

    return value


# ----------------------------------------------------------------------
# 요청 DTO
# ----------------------------------------------------------------------


class SignupRequest(BaseModel):
    """POST /auth/signup 요청 (api_contract 1.3절).

    세 필드가 **모두 필수**다. `name`이 선택이 될 수 없는 이유는
    `HOSTS.name`이 `NOT NULL`이기 때문이다 -- 값을 받지 않으면 서버가 무엇을
    채울지 정해야 하는데, 그런 기본값을 두지 않는다(1.3절).
    """

    email: str
    password: str
    name: str

    @field_validator("email")
    @classmethod
    def _check_email(cls, v: str) -> str:
        return _validate_email(v)

    @field_validator("password")
    @classmethod
    def _check_password(cls, v: str) -> str:
        return _validate_password(v)

    @field_validator("name")
    @classmethod
    def _check_name(cls, v: str) -> str:
        # 이름은 전용 에러 코드가 없으므로(1.1절 표) 일반 검증 경로를 쓴다.
        #   ValueError -> main.py가 400 VALIDATION_ERROR로 감싼다.
        v = v.strip()
        if not v:
            raise ValueError("이름을 입력해 주세요.")
        if len(v) > NAME_MAX_LENGTH:
            raise ValueError(f"이름은 {NAME_MAX_LENGTH}자 이하여야 합니다.")
        return v


class LoginRequest(BaseModel):
    """POST /auth/login 요청 (api_contract 1.2절).

    **비밀번호 길이를 검증하지 않는다.** 로그인은 "이 값이 정책에 맞는가"가
    아니라 "저장된 해시와 일치하는가"를 묻는다. 여기서 길이로 거르면
    `INVALID_PASSWORD_FORMAT`(400)과 `INVALID_CREDENTIALS`(401)가 갈려
    **틀린 비밀번호의 길이를 외부에서 추측**할 수 있게 된다. 정책이 나중에
    바뀌어도 옛 비밀번호로 로그인할 수 있어야 한다는 이유도 있다.

    이메일 형식은 검증한다 -- 1.2절 에러 표에 `INVALID_EMAIL_FORMAT`이
    있고, 형식이 아예 아닌 값은 조회할 필요조차 없다. 정규화(소문자)도
    가입 때와 같은 함수를 지나야 **대문자로 입력한 로그인이 실패하지 않는다.**
    """

    email: str
    password: str

    @field_validator("email")
    @classmethod
    def _check_email(cls, v: str) -> str:
        return _validate_email(v)


# ----------------------------------------------------------------------
# 응답 DTO
# ----------------------------------------------------------------------


class HostResponse(BaseModel):
    """`host` 객체 -- 3필드 (api_contract 1.1절).

    **`password_hash`를 절대 포함하지 않는다.** `from_attributes=True`로
    ORM 객체에서 값을 읽지만 Pydantic은 **여기 선언된 필드만** 가져가므로
    `Host` 모델에 컬럼이 더 있어도 응답으로 새지 않는다. 이 보장이 깨지지
    않는지는 `tests/test_auth_schemas.py`가 지킨다.

    `created_at`도 넣지 않는다 -- 화면에서 쓰는 곳이 없다(1.1절).

    `GET /auth/me`(1.4절)는 이 객체를 그대로 반환한다.
    """

    model_config = ConfigDict(from_attributes=True)

    host_id: int
    email: str
    name: str


class TokenResponse(BaseModel):
    """로그인/회원가입 공통 응답 (api_contract 1.2·1.3절).

    가입(201)과 로그인(200)이 **같은 구조**를 쓴다. 가입 성공 시 토큰을
    함께 반환해 곧바로 로그인 상태가 되므로 `/signup -> /onboarding`
    흐름에 `/login`이 끼어들지 않는다(1.3절).

    `token_type`은 항상 `"bearer"`다. 응답에 포함하되 프론트는 `Bearer`를
    하드코딩한다(1.1절) -- 값이 바뀔 여지가 없어 기본값으로 고정한다.
    """

    access_token: str
    token_type: str = "bearer"
    host: HostResponse
