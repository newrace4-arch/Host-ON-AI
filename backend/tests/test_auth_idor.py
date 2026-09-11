"""JWT 교체 후 IDOR 재검증 (r47 4단계).

### 왜 다시 하는가

소유권 검증 로직은 한 줄도 바뀌지 않았지만 **`host_id`의 출처가 바뀌었다.**
9/11 이전에는 개발용 환경변수에서 왔고 이제는 토큰에서 온다.
출처가 바뀌었으니 **같은 결과가 나오는지는 다시 확인해야 한다** -- 논리가
같다는 것과 실제로 같게 동작한다는 것은 다른 이야기다.

### 이 파일이 고정하는 두 경계

**1. 401과 404를 섞지 않는다**(api_contract 0절)

    401  인증 자체가 실패 -- 토큰이 없거나 만료됐거나 서명이 무효
    404  인증은 유효하나 리소스가 없거나 내 것이 아님

권한 문제에 401을 반환하면 프론트가 **세션 만료로 오인해 토큰을 지우고
로그아웃시킨다.** 남의 숙소 id를 한 번 잘못 눌렀을 뿐인데 로그인이 풀린다.

**2. 404 응답이 바이트 단위로 같다**

"남의 것"과 "없는 것"의 응답이 조금이라도 다르면 **id를 1씩 올려가며 어떤
property_id가 실재하는지 알아낼 수 있다.** 403을 쓰지 않는 이유와 같다
(CLAUDE.md 코딩규칙 1).

> ⚠️ 체크리스트 '일자별 실행리스트' r46의 확인방법은 *"403으로 차단"*이라고
> 적고 있으나 **그쪽이 잘못이다.** 문구 정정은 9/12 일괄 처리로 넘긴다.
"""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import Iterator
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import settings
from app.core.security import create_access_token
from app.main import app
from app.models.channel import ChannelConnection
from app.models.enums import AccommodationType, BookableUnitType, Channel
from app.models.host import Host
from app.models.property import Property

PASSWORD = "hoston-1234"
ICAL_URL = "https://www.airbnb.com/calendar/ical/999.ics?s=idor-test-token"

# 실재할 가능성이 없는 id. BIGINT 시퀀스가 여기까지 오지 않는다.
MISSING_PROPERTY_ID = 9_000_000_001
MISSING_CONNECTION_ID = 9_000_000_002


def _email() -> str:
    return f"idor-{uuid.uuid4().hex[:12]}@test.local"


def _run_db(work):
    """앱과 분리된 NullPool 엔진에서 DB 작업을 돌린다.

    앱 공용 엔진의 커넥션은 TestClient의 이벤트 루프에 묶여 있어 새 루프에서
    만지면 깨진다(`test_auth_endpoints.py` `_run_db` 주석 참고).
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
    with TestClient(app) as c:
        yield c


@pytest.fixture
def cleanup() -> Iterator[list[str]]:
    """만든 호스트를 지운다. `hosts` 삭제가 CASCADE로 숙소·채널까지 정리한다."""
    emails: list[str] = []
    yield emails

    if not emails:
        return

    async def _cleanup(session):
        await session.execute(delete(Host).where(Host.email.in_(emails)))
        await session.commit()

    _run_db(_cleanup)


def _signup(client: TestClient, cleanup: list[str]) -> tuple[str, int]:
    """가입하고 (토큰, host_id)를 돌려준다."""
    email = _email()
    res = client.post(
        "/auth/signup", json={"email": email, "password": PASSWORD, "name": "호스트"}
    )
    assert res.status_code == 201, res.text
    cleanup.append(email)
    data = res.json()["data"]
    return data["access_token"], data["host"]["host_id"]


def _make_property(host_id: int) -> tuple[int, int]:
    """호스트 소유의 숙소 + 채널연결을 만든다. `POST /properties`는 아직 없다."""

    async def _work(session):
        prop = Property(
            host_id=host_id,
            name="IDOR 테스트 숙소",
            accommodation_type=AccommodationType.URBAN_HOMESTAY,
            bookable_unit_type=BookableUnitType.PROPERTY,
        )
        session.add(prop)
        await session.flush()

        conn = ChannelConnection(
            property_id=prop.property_id, channel=Channel.AIRBNB, ical_url=ICAL_URL
        )
        session.add(conn)
        await session.commit()
        return prop.property_id, conn.connection_id

    return _run_db(_work)


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _fingerprint(res) -> tuple:
    """상태코드 + 에러 본문 전체. 두 응답이 구분 불가능한지 보는 데 쓴다."""
    return (res.status_code, res.text)


# ======================================================================
# 2단계 -- IDOR 재검증
# ======================================================================


def test_property_scoped_route_isolates_by_token(client: TestClient, cleanup):
    """`GET /properties/{id}/channels` -- 내 것 200, 남의 것/없는 것 둘 다 404.

    **뒤 둘이 바이트 단위로 같아야 한다.** 다르면 어떤 property_id가
    실재하는지 알아낼 수 있다.
    """
    token_a, host_a = _signup(client, cleanup)
    _token_b, host_b = _signup(client, cleanup)

    mine, _ = _make_property(host_a)
    theirs, _ = _make_property(host_b)

    ok = client.get(f"/properties/{mine}/channels", headers=_auth(token_a))
    others = client.get(f"/properties/{theirs}/channels", headers=_auth(token_a))
    missing = client.get(
        f"/properties/{MISSING_PROPERTY_ID}/channels", headers=_auth(token_a)
    )

    # 내 숙소는 보인다 -- 토큰에서 꺼낸 host_id로 소유권이 제대로 통한다.
    assert ok.status_code == 200
    assert len(ok.json()["data"]) == 1

    # 남의 것과 없는 것이 구분되지 않는다.
    assert others.status_code == missing.status_code == 404
    assert others.json()["error"]["code"] == "RESOURCE_NOT_FOUND"
    assert _fingerprint(others) == _fingerprint(missing)

    # 403은 쓰지 않는다(CLAUDE.md 코딩규칙 1).
    assert others.status_code != 403


@pytest.mark.parametrize(
    "method,path_template",
    [
        ("GET", "/channels/{cid}/sync-errors"),
        ("POST", "/channels/{cid}/sync"),
        ("DELETE", "/channels/{cid}"),
    ],
)
def test_connection_scoped_routes_isolate_by_token(
    client: TestClient, cleanup, method, path_template
):
    """`property_id`가 URL에 없는 경로도 같은 규칙을 따른다(0절).

    이 경로들은 조회 쿼리 자체에 소유권 조건을 묶어 처리하므로, 출처가
    환경변수에서 토큰으로 바뀌어도 결과가 같아야 한다.
    """
    token_a, _host_a = _signup(client, cleanup)
    _token_b, host_b = _signup(client, cleanup)

    _prop_b, conn_b = _make_property(host_b)

    others = client.request(
        method, path_template.format(cid=conn_b), headers=_auth(token_a)
    )
    missing = client.request(
        method, path_template.format(cid=MISSING_CONNECTION_ID), headers=_auth(token_a)
    )

    assert others.status_code == missing.status_code == 404
    assert others.json()["error"]["code"] == "RESOURCE_NOT_FOUND"
    assert _fingerprint(others) == _fingerprint(missing)


def test_every_route_makes_others_and_missing_indistinguishable(
    client: TestClient, cleanup
):
    """**네 경로 각각에서 "남의 것"과 "없는 것"이 구분되지 않는가.**

    이것이 지켜야 할 불변식이다 -- 같은 경로에 id만 바꿔 넣었을 때 응답이
    달라지면 **어떤 id가 실재하는지 알아낼 수 있다.**

    ### 경로끼리는 메시지가 달라도 된다

    `properties` 계열은 *"요청한 숙소를 찾을 수 없습니다"*, `channels`
    계열은 *"요청한 채널 연결을 찾을 수 없습니다"*로 갈린다. **이것은
    누출이 아니다** -- 메시지가 알려주는 것은 *"그 경로가 다루는 리소스
    종류"*이고, 호출자는 어느 경로를 호출했는지 **이미 알고 있다.**
    존재 여부는 여전히 드러나지 않는다.

    (처음에는 네 경로의 응답이 전부 같아야 한다고 적었다가 고쳤다.
    그쪽은 보안이 요구하는 것보다 강한 조건이고, 맞추려면 서비스
    레이어의 메시지를 뭉개야 해서 **호스트가 보는 오류 문구만 나빠진다.**)
    """
    token_a, _ = _signup(client, cleanup)
    _token_b, host_b = _signup(client, cleanup)
    prop_b, conn_b = _make_property(host_b)

    pairs = {
        "GET /properties/{}/channels": (
            client.get(f"/properties/{prop_b}/channels", headers=_auth(token_a)),
            client.get(
                f"/properties/{MISSING_PROPERTY_ID}/channels", headers=_auth(token_a)
            ),
        ),
        "GET /channels/{}/sync-errors": (
            client.get(f"/channels/{conn_b}/sync-errors", headers=_auth(token_a)),
            client.get(
                f"/channels/{MISSING_CONNECTION_ID}/sync-errors", headers=_auth(token_a)
            ),
        ),
        "POST /channels/{}/sync": (
            client.post(f"/channels/{conn_b}/sync", headers=_auth(token_a)),
            client.post(
                f"/channels/{MISSING_CONNECTION_ID}/sync", headers=_auth(token_a)
            ),
        ),
        "DELETE /channels/{}": (
            client.delete(f"/channels/{conn_b}", headers=_auth(token_a)),
            client.delete(f"/channels/{MISSING_CONNECTION_ID}", headers=_auth(token_a)),
        ),
    }

    for label, (others, missing) in pairs.items():
        assert _fingerprint(others) == _fingerprint(missing), label
        assert others.status_code == 404, label
        assert others.json()["error"]["code"] == "RESOURCE_NOT_FOUND", label
        # 403은 어느 경로에서도 쓰지 않는다(CLAUDE.md 코딩규칙 1).
        assert others.status_code != 403, label


def test_other_hosts_resource_is_not_actually_deleted(client: TestClient, cleanup):
    """404로 막힌 DELETE가 **실제로 지우지 않았는지** 확인한다.

    상태코드만 보면 "거부됐다"고 믿게 되지만, 응답을 만들기 전에 삭제가
    일어났다면 코드는 404인데 데이터는 사라진 상태가 된다.
    """
    token_a, _ = _signup(client, cleanup)
    token_b, host_b = _signup(client, cleanup)
    prop_b, conn_b = _make_property(host_b)

    assert (
        client.delete(f"/channels/{conn_b}", headers=_auth(token_a)).status_code == 404
    )

    # 주인은 여전히 볼 수 있다.
    still_there = client.get(f"/properties/{prop_b}/channels", headers=_auth(token_b))
    assert still_there.status_code == 200
    assert [c["connection_id"] for c in still_there.json()["data"]] == [conn_b]


# ======================================================================
# 3단계 -- 토큰 없이 channels 접근
# ======================================================================


@pytest.mark.parametrize(
    "label,headers",
    [
        ("토큰 없음", {}),
        ("빈 Bearer", {"Authorization": "Bearer "}),
        ("Bearer 아님", {"Authorization": "Basic abc123"}),
        ("서명 틀림", {"Authorization": "Bearer not.a.real.token"}),
    ],
)
def test_channels_require_authentication(client: TestClient, label, headers):
    """인증 없이 `channels`에 접근하면 **401 `UNAUTHORIZED`**다.

    404가 아니다 -- 요청자가 누구인지 확인할 수 없는 단계이므로 소유권을
    따질 대상 자체가 없다.
    """
    res = client.get("/properties/1/channels", headers=headers)

    assert res.status_code == 401, label
    assert res.json()["error"]["code"] == "UNAUTHORIZED", label
    assert res.json()["data"] is None


def test_channels_reject_expired_token(client: TestClient, cleanup):
    """만료된 토큰도 401 `UNAUTHORIZED`다 -- 404로 새지 않는다."""
    _token, host_id = _signup(client, cleanup)
    prop_id, _ = _make_property(host_id)
    expired = create_access_token(host_id, expires_delta=timedelta(minutes=-1))

    res = client.get(f"/properties/{prop_id}/channels", headers=_auth(expired))

    assert res.status_code == 401
    assert res.json()["error"]["code"] == "UNAUTHORIZED"


def test_forged_token_cannot_reach_another_host(client: TestClient, cleanup):
    """**다른 키로 서명한 토큰으로는 남의 숙소에 닿을 수 없다.**

    host_id를 마음대로 적어도 서명 검증에서 막힌다. 401이지 404가 아니다 --
    소유권 이전 단계에서 걸린다.
    """
    from jose import jwt

    _token_b, host_b = _signup(client, cleanup)
    prop_b, _ = _make_property(host_b)

    forged = jwt.encode(
        {"sub": str(host_b)}, "a-different-secret-key", algorithm=settings.JWT_ALGORITHM
    )

    res = client.get(f"/properties/{prop_b}/channels", headers=_auth(forged))

    assert res.status_code == 401
    assert res.json()["error"]["code"] == "UNAUTHORIZED"


def test_valid_token_for_nonexistent_host_gets_404_not_401(
    client: TestClient, cleanup
):
    """서명이 유효하면 인증은 통과하고, 그 뒤 소유권에서 404가 난다.

    이 경계가 중요하다 -- **인증(401)과 권한(404)이 서로 다른 단계**임을
    보인다. 우리 키로 서명했으므로 토큰 자체는 진짜이고, 다만 그 host_id가
    아무 숙소도 갖고 있지 않을 뿐이다.
    """
    _token_b, host_b = _signup(client, cleanup)
    prop_b, _ = _make_property(host_b)

    ghost = create_access_token(9_000_000_003)

    res = client.get(f"/properties/{prop_b}/channels", headers=_auth(ghost))

    assert res.status_code == 404
    assert res.json()["error"]["code"] == "RESOURCE_NOT_FOUND"
