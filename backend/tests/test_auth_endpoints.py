"""인증 엔드포인트 회귀 테스트 -- signup / login / me (api_contract 1절).

**실제 라우터와 실제 DB를 쓴다.** 스키마 단위 테스트(`test_auth_schemas.py`)와
목적이 다르다 -- 저쪽은 "검증 규칙이 맞는가"를 보고, 여기는 **"그 규칙이
HTTP 응답으로 제대로 나오는가"**를 본다.

### 이 파일이 존재하는 첫 번째 이유 -- 에러 코드 우회의 실증

`main.py`의 `RequestValidationError` 핸들러는 **모든 검증 실패를
`VALIDATION_ERROR` 하나로** 변환한다. `schemas/auth.py`는 이를 피하려고
`ValueError`가 아니라 `AppError` 하위 예외를 던진다. 그 우회가 실제로
먹히는지는 **라우터를 통과한 응답 본문**으로만 확인할 수 있다.

`test_error_codes_survive_the_router`가 그 확인이다. 하나라도
`VALIDATION_ERROR`가 나오면 우회가 깨진 것이다.

### 두 번째 이유 -- 해시가 실제로 저장되는지

`HostResponse`에 `password_hash` 필드가 없어도 **모델을 그대로 반환하면
새어 나간다.** 그래서 DB를 직접 조회해 저장 형태를 보고, 응답 본문
전체를 문자열로 훑어 평문과 해시가 섞이지 않았는지 본다.
"""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import settings
from app.main import app
from app.models.host import Host

PASSWORD = "hoston-1234"
NAME = "신경주"


def _email() -> str:
    """테스트마다 새 이메일. `hosts.email`이 UNIQUE라 재사용하면 서로 오염된다."""
    return f"auth-{uuid.uuid4().hex[:12]}@test.local"


def _run_db(work):
    """검증·정리용 DB 작업을 **앱과 분리된 엔진**에서 돌린다.

    ⚠️ `app.core.database.AsyncSessionLocal`(앱 공용 엔진)을 여기서 쓰면
    안 된다. 그 풀에 남은 asyncpg 커넥션은 **TestClient가 요청을 처리한
    이벤트 루프에 묶여 있어서**, `asyncio.run`으로 새 루프를 열어 그
    커넥션을 만지는 순간 깨진다(`'NoneType' object has no attribute
    'send'`). `conftest.py`의 `db` 픽스처가 NullPool을 쓰는 것과 **같은
    이유이며, 실제로 이 파일 첫 회차에서 그대로 재현됐다.**

    NullPool은 커넥션을 재사용하지 않으므로 매 호출이 자기 루프에서
    시작하고 끝난다.
    """

    async def _run():
        engine = create_async_engine(settings.DATABASE_URL, poolclass=NullPool)
        maker = async_sessionmaker(bind=engine, expire_on_commit=False, autoflush=False)
        try:
            async with maker() as session:
                return await work(session)
        finally:
            await engine.dispose()

    return asyncio.run(_run())


@pytest.fixture
def client() -> Iterator[TestClient]:
    """실제 앱. 라이프스팬·CORS·예외 핸들러를 그대로 거친 응답을 본다."""
    with TestClient(app) as c:
        yield c


@pytest.fixture
def created_emails() -> Iterator[list[str]]:
    """이 테스트가 만든 호스트를 끝나고 지운다.

    `conftest.py`의 `host` 픽스처는 세션을 직접 쓰는 테스트용이라 HTTP
    경로로 만들어진 행은 잡지 못한다. 남겨두면 회차마다 이메일이 쌓이고,
    무엇이 테스트 잔여물인지 알 수 없게 된다.
    """
    emails: list[str] = []
    yield emails

    if not emails:
        return

    async def _cleanup(session):
        await session.execute(delete(Host).where(Host.email.in_(emails)))
        await session.commit()

    _run_db(_cleanup)


def _signup(client: TestClient, emails: list[str], **overrides):
    email = overrides.pop("email", None) or _email()
    body = {"email": email, "password": PASSWORD, "name": NAME, **overrides}
    res = client.post("/auth/signup", json=body)
    if res.status_code == 201:
        emails.append(body["email"].strip().lower())
    return res, body


def _code(res) -> str | None:
    error = res.json().get("error")
    return error.get("code") if error else None


# ======================================================================
# 2단계 -- 실제 라우터로 에러 코드 확인 (2단계에서 남긴 숙제)
# ======================================================================


def test_error_codes_survive_the_router(client: TestClient, created_emails):
    """**`AppError` 우회가 라우터를 통과해 실제 응답까지 살아남는가.**

    `VALIDATION_ERROR`가 하나라도 나오면 우회가 깨진 것이다 -- 스키마
    단위 테스트는 통과하면서 HTTP 응답만 뭉개지는 상태이므로, 이 테스트가
    없으면 발견되지 않는다.
    """
    taken = _email()
    first, _ = _signup(client, created_emails, email=taken)
    assert first.status_code == 201

    cases = [
        # (설명, 요청, 기대 코드, 기대 status)
        (
            "한글 25자(75바이트) 비밀번호",
            ("/auth/signup", {"email": _email(), "password": "가" * 25, "name": NAME}),
            "PASSWORD_TOO_LONG",
            400,
        ),
        (
            "7자 비밀번호",
            ("/auth/signup", {"email": _email(), "password": "a" * 7, "name": NAME}),
            "INVALID_PASSWORD_FORMAT",
            400,
        ),
        (
            "잘못된 이메일",
            ("/auth/signup", {"email": "not-an-email", "password": PASSWORD, "name": NAME}),
            "INVALID_EMAIL_FORMAT",
            400,
        ),
        (
            "중복 이메일",
            ("/auth/signup", {"email": taken, "password": PASSWORD, "name": NAME}),
            "EMAIL_ALREADY_EXISTS",
            409,
        ),
        (
            "틀린 비밀번호",
            ("/auth/login", {"email": taken, "password": "wrong-password"}),
            "INVALID_CREDENTIALS",
            401,
        ),
        (
            "없는 이메일",
            ("/auth/login", {"email": _email(), "password": PASSWORD}),
            "INVALID_CREDENTIALS",
            401,
        ),
    ]

    actual = {}
    for label, (path, body), _expected, _status in cases:
        res = client.post(path, json=body)
        actual[label] = (res.status_code, _code(res))

    # 토큰 없이 /auth/me
    res = client.get("/auth/me")
    actual["토큰 없이 /auth/me"] = (res.status_code, _code(res))

    expected = {
        "한글 25자(75바이트) 비밀번호": (400, "PASSWORD_TOO_LONG"),
        "7자 비밀번호": (400, "INVALID_PASSWORD_FORMAT"),
        "잘못된 이메일": (400, "INVALID_EMAIL_FORMAT"),
        "중복 이메일": (409, "EMAIL_ALREADY_EXISTS"),
        "틀린 비밀번호": (401, "INVALID_CREDENTIALS"),
        "없는 이메일": (401, "INVALID_CREDENTIALS"),
        "토큰 없이 /auth/me": (401, "UNAUTHORIZED"),
    }

    assert actual == expected
    # 우회가 깨졌을 때 가장 먼저 나타나는 증상을 따로 못박는다.
    assert "VALIDATION_ERROR" not in {code for _, code in actual.values()}


def test_nonexistent_email_and_wrong_password_are_indistinguishable(
    client: TestClient, created_emails
):
    """계정 열거 방어 -- **코드도 메시지도 같아야 한다.**

    코드만 통일하고 메시지를 다르게 쓰면 그 문구로 구분이 된다.
    """
    res, body = _signup(client, created_emails)
    assert res.status_code == 201

    wrong_password = client.post(
        "/auth/login", json={"email": body["email"], "password": "wrong-password"}
    )
    no_such_email = client.post(
        "/auth/login", json={"email": _email(), "password": PASSWORD}
    )

    assert wrong_password.status_code == no_such_email.status_code == 401
    assert wrong_password.json()["error"] == no_such_email.json()["error"]


# ======================================================================
# 3단계 -- bcrypt 저장 실측
# ======================================================================


def test_password_is_stored_as_bcrypt_hash_and_never_leaks(
    client: TestClient, created_emails
):
    """가입 후 **DB를 직접 조회해** 저장 형태를 확인한다.

    셋을 본다 -- 해시 형식(`$2b$`), 평문 부재, 응답 본문 부재. 셋째가
    특히 중요하다: `HostResponse`에 필드가 없어도 **모델을 그대로 반환하면
    새어 나가므로**, 스키마를 보는 것만으로는 보장되지 않는다.
    """
    res, body = _signup(client, created_emails)
    assert res.status_code == 201

    async def _fetch(session):
        return await session.scalar(select(Host).where(Host.email == body["email"]))

    host = _run_db(_fetch)

    assert host is not None

    # 1) bcrypt 해시 형식이다
    assert host.password_hash.startswith("$2b$")
    assert len(host.password_hash) == 60

    # 2) 평문이 DB 어디에도 없다 -- 해시 안에도, 다른 컬럼에도
    assert host.password_hash != PASSWORD
    assert PASSWORD not in host.password_hash
    assert PASSWORD not in f"{host.email}{host.name}"

    # 3) 응답 본문 어디에도 평문과 해시가 없다(중첩 구조까지 문자열로 훑는다)
    raw = res.text
    assert PASSWORD not in raw
    assert host.password_hash not in raw
    assert "password" not in raw
    assert set(res.json()["data"]["host"]) == {"host_id", "email", "name"}


# ======================================================================
# 4단계 -- 전체 흐름
# ======================================================================


def test_signup_login_me_full_flow(client: TestClient, created_emails):
    """가입 -> 로그인 -> /auth/me가 끊김 없이 이어지고 같은 host를 가리킨다."""
    signup_res, body = _signup(client, created_emails)

    # 가입은 201이고 토큰을 함께 준다(1.3절) -- /login을 거치지 않는다.
    assert signup_res.status_code == 201
    signup_data = signup_res.json()["data"]
    assert signup_data["token_type"] == "bearer"
    assert signup_data["access_token"]

    login_res = client.post(
        "/auth/login", json={"email": body["email"], "password": PASSWORD}
    )
    assert login_res.status_code == 200
    login_data = login_res.json()["data"]

    me_res = client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {login_data['access_token']}"},
    )
    assert me_res.status_code == 200

    # 세 응답이 같은 호스트를 가리킨다.
    assert (
        signup_data["host"]
        == login_data["host"]
        == me_res.json()["data"]
    )
    assert me_res.json()["data"]["email"] == body["email"]


def test_signup_token_works_immediately(client: TestClient, created_emails):
    """가입 응답의 토큰이 **그 자리에서** 쓸 수 있다.

    `/signup -> /onboarding` 흐름에 `/login`이 낄 자리가 없다(1.3절).
    """
    res, _ = _signup(client, created_emails)
    token = res.json()["data"]["access_token"]

    me = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})

    assert me.status_code == 200
    assert me.json()["data"]["host_id"] == res.json()["data"]["host"]["host_id"]


@pytest.mark.parametrize("path", ["/auth/signup", "/auth/login"])
def test_success_response_uses_the_common_envelope(
    client: TestClient, created_emails, path
):
    """성공 응답도 0절 봉투를 쓴다 -- `{data, error}`이고 `error`는 null."""
    res, body = _signup(client, created_emails)
    if path == "/auth/login":
        res = client.post(
            "/auth/login", json={"email": body["email"], "password": PASSWORD}
        )

    payload = res.json()
    assert set(payload) == {"data", "error"}
    assert payload["error"] is None
    assert set(payload["data"]) == {"access_token", "token_type", "host"}


def test_error_response_uses_the_common_envelope(client: TestClient):
    """실패 응답도 같은 봉투다 -- `data`는 null, `error`는 code+message."""
    res = client.post(
        "/auth/login", json={"email": _email(), "password": PASSWORD}
    )

    payload = res.json()
    assert set(payload) == {"data", "error"}
    assert payload["data"] is None
    assert set(payload["error"]) == {"code", "message"}
    assert payload["error"]["message"]


# ======================================================================
# /auth/me 토큰 검증
# ======================================================================


def test_login_is_case_insensitive_on_email(client: TestClient, created_emails):
    """대문자로 입력한 이메일로도 로그인된다.

    가입과 로그인이 같은 정규화를 지나지 않으면 "가입했는데 로그인이
    안 된다"가 된다.
    """
    res, body = _signup(client, created_emails)
    assert res.status_code == 201

    upper = client.post(
        "/auth/login", json={"email": body["email"].upper(), "password": PASSWORD}
    )

    assert upper.status_code == 200
    assert upper.json()["data"]["host"]["email"] == body["email"]


@pytest.mark.parametrize(
    "header",
    [
        {"Authorization": "Bearer not.a.real.token"},
        {"Authorization": "Bearer "},
        {"Authorization": "not-a-bearer-scheme"},
        {},
    ],
)
def test_me_rejects_bad_tokens_with_unauthorized(client: TestClient, header):
    """토큰 없음·형식 오류·서명 오류가 **전부 401 `UNAUTHORIZED`**다.

    404가 아니다 -- 인증 자체가 실패한 경우이고, 소유권 문제가 아니다.
    """
    res = client.get("/auth/me", headers=header)

    assert res.status_code == 401
    assert _code(res) == "UNAUTHORIZED"


def test_me_rejects_expired_token(client: TestClient, created_emails):
    """만료된 토큰도 같은 401 `UNAUTHORIZED`다.

    `security.py`가 내부적으로는 `TokenExpiredError`로 구분하지만 응답에서는
    구분되지 않는다 -- "서명은 맞는데 만료됐다"는 답은 공격자에게 비밀키가
    유효하다는 사실을 알려준다.
    """
    from datetime import timedelta

    from app.core.security import create_access_token

    res, _ = _signup(client, created_emails)
    host_id = res.json()["data"]["host"]["host_id"]
    expired = create_access_token(host_id, expires_delta=timedelta(minutes=-1))

    me = client.get("/auth/me", headers={"Authorization": f"Bearer {expired}"})

    assert me.status_code == 401
    assert _code(me) == "UNAUTHORIZED"


def test_me_rejects_token_for_deleted_host(client: TestClient, created_emails):
    """토큰은 유효한데 그 호스트가 사라졌으면 401이다.

    인증 주체 자체가 없어진 것이라 `RESOURCE_NOT_FOUND`가 아니다.
    """
    from app.core.security import create_access_token

    # 실재할 가능성이 없는 큰 id로 토큰을 만든다(BIGINT 시퀀스가 여기까지 오지 않는다).
    token = create_access_token(9_000_000_000)

    res = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})

    assert res.status_code == 401
    assert _code(res) == "UNAUTHORIZED"
