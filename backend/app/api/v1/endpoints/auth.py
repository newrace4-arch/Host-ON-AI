"""인증 라우터 -- signup / login / me (api_contract.md 1절).

경로에 `/api/v1` 접두사를 붙이지 않는다(api_router.py 참고). 응답은 공통
봉투 `{"data": ..., "error": null}`로 감싼다(0절).

## 서비스 모듈을 두지 않는 이유

`channels`는 `channel_service`를 거치지만 여기는 라우터가 직접 처리한다.
인증은 **다른 도메인이 재사용할 로직이 아니고**(소유권 검증처럼 여러
라우터가 부르는 것이 아니다), 해싱·토큰이라는 진짜 알고리즘은 이미
`core/security.py`에 있다. 남는 것은 조회 한 번과 삽입 한 번뿐이라
서비스 레이어를 끼우면 위임만 하는 껍데기가 하나 더 생긴다.

## 로그아웃 엔드포인트가 없다

`POST /auth/logout`을 만들지 않는다(1.5절). JWT는 무상태라 서버가 이미
발급한 토큰을 무효화할 수 없다. 무효화하려면 폐기 목록을 두고 요청마다
조회해야 하는데 그 순간 무상태의 이점이 사라진다. 로그아웃은 프론트가
`localStorage`의 토큰을 지우는 것으로 처리한다.
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.exceptions import AppError
from app.core.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)
from app.models.host import Host
from app.schemas.auth import HostResponse, LoginRequest, SignupRequest, TokenResponse
from app.utils.db_errors import violates_constraint

router = APIRouter(prefix="/auth", tags=["auth"])

DbSession = Annotated[AsyncSession, Depends(get_db)]


# ----------------------------------------------------------------------
# 예외
# ----------------------------------------------------------------------


class EmailAlreadyExistsError(AppError):
    """이미 가입된 이메일(409).

    DB의 `hosts_email_key(email)` 제약과 짝을 이룬다(api_contract 1.1절).
    """

    status_code = 409
    code = "EMAIL_ALREADY_EXISTS"


class InvalidCredentialsError(AppError):
    """이메일 또는 비밀번호 불일치(401).

    **어느 쪽이 틀렸는지 구분하지 않는다**(1.1절). 구분하면 이메일만
    바꿔가며 가입된 계정을 열거할 수 있다. 메시지도 하나로 고정한다 --
    코드가 같아도 문구가 다르면 그것으로 구분이 된다.
    """

    status_code = 401
    code = "INVALID_CREDENTIALS"


class UnauthorizedError(AppError):
    """토큰 없음(401).

    만료·서명 무효는 `core/security.py`의 `TokenExpiredError` /
    `TokenInvalidError`가 같은 코드로 낸다. 셋 다 `UNAUTHORIZED`다.

    ⚠️ **404와 섞지 않는다**(0절). 이것은 *인증 자체가 실패한* 경우이고,
    "인증은 유효하나 그 리소스가 내 것이 아니다"는 `RESOURCE_NOT_FOUND`다.
    권한 문제에 401을 반환하면 프론트가 세션 만료로 오인해 **토큰을 지우고
    로그아웃시킨다** -- 남의 숙소 id를 한 번 잘못 눌렀을 뿐인데 로그인이
    풀린다.
    """

    status_code = 401
    code = "UNAUTHORIZED"


# ----------------------------------------------------------------------
# 토큰 추출 의존성
# ----------------------------------------------------------------------

# `auto_error=False`가 핵심이다. 기본값(True)이면 토큰이 없을 때 FastAPI가
#   자체 `HTTPException`을 던져 `{"detail": "Not authenticated"}`로 응답한다 --
#   0절 봉투가 아니라서 프론트가 에러 처리를 두 벌 만들어야 한다.
#   끄면 토큰이 없을 때 `None`이 들어오고, 우리가 `UnauthorizedError`를 던진다.
#
#   `tokenUrl`은 Swagger UI의 Authorize 버튼 표시용일 뿐 실제 동작에
#   관여하지 않는다(1.6절). 우리는 `OAuth2PasswordRequestForm`을 쓰지
#   않지만 **헤더에서 토큰을 꺼내는 쪽은 응답 형식과 무관**하므로 그대로 쓴다.
_bearer_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login", auto_error=False)


async def get_authenticated_host_id(
    token: Annotated[str | None, Depends(_bearer_scheme)],
) -> int:
    """`Authorization: Bearer <token>` 헤더를 검증해 `host_id`를 돌려준다.

    토큰 없음 / 만료 / 서명 오류가 **전부 401 `UNAUTHORIZED`**로 나간다
    (1.1절). 만료와 서명 오류의 구분은 `security.py` 안에만 있다.

    ⚠️ **이 의존성의 정식 자리는 `core/dependencies.py`다.** 지금 거기에는
    9/11 인증 구현 전까지 쓰는 `get_current_host_id` 스텁이 있고, 그 교체는
    r47 4단계다. 교체할 때 이 함수를 그쪽으로 옮기고 여기서는 import만
    한다 -- 그래야 `channels` 등 기존 라우터도 같은 경로로 인증된다.
    """
    if not token:
        raise UnauthorizedError("인증이 필요합니다. 로그인 후 다시 시도해 주세요.")

    # 만료/서명 오류는 여기서 잡지 않는다 -- security.py가 던지는 예외가
    #   이미 401 UNAUTHORIZED이고, main.py의 AppError 핸들러가 봉투로 감싼다.
    return decode_access_token(token)


CurrentHostId = Annotated[int, Depends(get_authenticated_host_id)]


# ----------------------------------------------------------------------
# 타이밍 공격 방어용 더미 해시
# ----------------------------------------------------------------------

_dummy_hash: str | None = None


def _burn_password_time(password: str) -> None:
    """존재하지 않는 이메일일 때도 bcrypt 검증에 **같은 시간**을 쓴다.

    없는 이메일에서 해시 검증을 건너뛰면 응답이 **눈에 띄게 빨라진다** --
    bcrypt cost 12는 한 번에 수백 ms가 걸리므로 조회만 하고 끝나는 경로와
    차이가 크다. 그러면 `INVALID_CREDENTIALS`를 하나로 통일한 의미가
    사라진다. 코드와 메시지는 같은데 **응답 시간이 계정 존재 여부를
    알려주기** 때문이다.

    더미 해시는 첫 호출 때 한 번만 만들어 재사용한다. 모듈 import 시점에
    만들면 Render 콜드 스타트마다 bcrypt 한 번이 기동 경로에 얹힌다.
    """
    global _dummy_hash
    if _dummy_hash is None:
        _dummy_hash = hash_password("timing-attack-placeholder")
    verify_password(password, _dummy_hash)


# ----------------------------------------------------------------------
# 엔드포인트
# ----------------------------------------------------------------------


@router.post(
    "/signup",
    status_code=status.HTTP_201_CREATED,
    summary="회원가입 (토큰 동시 발급)",
)
async def signup(payload: SignupRequest, db: DbSession) -> dict[str, Any]:
    """가입하고 **토큰을 함께 반환해 곧바로 로그인 상태**가 된다(1.3절).

    가입 직후 다시 로그인하게 하면 같은 정보를 두 번 입력하게 되고, 화면
    흐름도 `/signup -> /onboarding`이라 중간에 `/login`이 낄 자리가 없다.

    ### 중복 이메일을 사전 조회로 막지 않는다

    `SELECT`로 먼저 확인한 뒤 `INSERT`하면 **두 요청이 동시에 오면 둘 다
    조회를 통과**한다(TOCTOU). 사전 조회를 넣어도 `IntegrityError` 처리는
    어차피 필요하므로, 판정을 **DB 제약 한 곳**으로 모은다. 조회 왕복도
    하나 줄어든다.
    """
    host = Host(
        email=payload.email,
        # 평문은 여기서 해시로 바뀌고 이후 어디에도 남지 않는다.
        password_hash=hash_password(payload.password),
        name=payload.name,
    )
    db.add(host)

    try:
        await db.flush()
    except IntegrityError as exc:
        await db.rollback()
        # asyncpg에서는 제약명이 메시지 문자열에만 남는다(troubleshooting 32번).
        #   그래서 속성이 아니라 이 유틸로 판정한다.
        if violates_constraint(exc, "hosts_email_key"):
            raise EmailAlreadyExistsError("이미 가입된 이메일입니다.") from exc
        raise

    body = _token_body(host)
    await db.commit()
    return {"data": body, "error": None}


@router.post("/login", summary="로그인, JWT 발급")
async def login(payload: LoginRequest, db: DbSession) -> dict[str, Any]:
    """이메일·비밀번호를 확인하고 토큰을 발급한다(1.2절).

    **이메일이 없는 경우와 비밀번호가 틀린 경우를 구분하지 않는다** --
    같은 401 `INVALID_CREDENTIALS`에 같은 메시지다. 그리고 **응답 시간도
    구분되지 않게** 한다(`_burn_password_time` 참고).
    """
    host = await db.scalar(select(Host).where(Host.email == payload.email))

    if host is None:
        _burn_password_time(payload.password)
        raise InvalidCredentialsError("이메일 또는 비밀번호가 올바르지 않습니다.")

    if not verify_password(payload.password, host.password_hash):
        raise InvalidCredentialsError("이메일 또는 비밀번호가 올바르지 않습니다.")

    return {"data": _token_body(host), "error": None}


@router.get("/me", summary="현재 로그인한 호스트 정보")
async def me(db: DbSession, host_id: CurrentHostId) -> dict[str, Any]:
    """토큰으로 사용자 정보를 복원한다(1.4절).

    토큰은 `localStorage`에 남지만 메모리의 사용자 정보는 새로고침하면
    사라진다. 앱 진입 시 이것으로 **토큰이 아직 유효한지 확인하고 정보를
    복원**한다.

    **DB를 다시 조회한다.** 토큰에 이름·이메일을 담아두고 꺼내 쓰지 않는
    이유는 두 가지다 -- 만료·서명 검증은 서버만 할 수 있고(1.4절), 토큰에
    복제해 두면 값을 바꿨을 때 만료(24시간) 전까지 옛 값이 따라다닌다.

    토큰은 유효한데 그 호스트가 삭제된 경우도 401이다. 인증 주체 자체가
    없어진 것이라 `RESOURCE_NOT_FOUND`가 아니다.
    """
    host = await db.get(Host, host_id)
    if host is None:
        raise UnauthorizedError("인증이 필요합니다. 로그인 후 다시 시도해 주세요.")

    return {"data": HostResponse.model_validate(host).model_dump(), "error": None}


# ----------------------------------------------------------------------
# 내부 헬퍼
# ----------------------------------------------------------------------


def _token_body(host: Host) -> dict[str, Any]:
    """가입(201)과 로그인(200)이 쓰는 **같은 응답 구조**를 만든다(1.2·1.3절).

    ⚠️ **`Host` 모델을 그대로 반환하지 않는다.** 반드시 `HostResponse`를
    거쳐야 `password_hash`가 빠진다. 응답 생성 경로를 이 함수 하나로 모아
    호출부가 실수로 모델을 내보낼 여지를 없앤다
    (`schemas/channel.py`의 `from_model`과 같은 이유).
    """
    return TokenResponse(
        access_token=create_access_token(host.host_id),
        host=HostResponse.model_validate(host),
    ).model_dump()
