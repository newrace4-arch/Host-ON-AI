"""RESERVATIONS.net_amount 생성 컬럼 회귀 테스트 (v1.4 revision ④).

### 왜 이 파일이 따로 필요한가

**제약 대조가 ④를 보지 못한다.** 생성 컬럼은 제약이 아니라 컬럼 속성이라
`pg_constraint`에 아무것도 남기지 않는다. `alembic check`도 못 본다 —
alembic 1.13.3은 `Computed`를 렌더링만 하고 **감지하지 않으며**
(`autogenerate/compare.py:988 _compare_computed_default()`가 연산 대신 경고만
낸다), `check`는 그 autogenerate 결과의 diff가 비었는지만 보기 때문이다
(`command.py:250`). 즉 ④가 **적용되지 않은 상태와 적용된 상태가 도구상
구분되지 않는다.** 이 파일이 그 구분을 담당한다.

### 픽스처를 왜 지역에 두는가

`conftest.py`의 `make_property`는 예약을 만들지 않는다. 그렇다고 `conftest.py`를
고치지 않는다(회귀 156건이 그 픽스처에 걸려 있다).
`test_reservation_integrity.py:41`의 `_insert_raw_reservation` 전례대로 이 파일
안에 지역 헬퍼를 둔다.
"""

from __future__ import annotations

from datetime import date

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ChannelConnection, Property, Reservation
from app.models.enums import BookableUnitType, ReservationStatus
from app.schemas.reservation import ReservationCreateRequest, ReservationResponse
from app.services import reservation_service as svc

D10 = date(2026, 11, 10)
D12 = date(2026, 11, 12)

GROSS = 100_000
FEE = 15_500
NET = 84_500  # gross - fee


async def _make_reservation(
    db: AsyncSession,
    *,
    prop: Property,
    conn: ChannelConnection,
    gross: int | None = GROSS,
    fee: int | None = FEE,
    check_in: date = D10,
    check_out: date = D12,
) -> Reservation:
    """서비스를 우회해 예약을 직접 만든다. net_amount는 **넘기지 않는다.**"""
    r = Reservation(
        property_id=prop.property_id,
        channel_connection_id=conn.connection_id,
        check_in=check_in,
        check_out=check_out,
        reservation_status=ReservationStatus.CONFIRMED,
        gross_amount=gross,
        fee_amount=fee,
    )
    db.add(r)
    await db.flush()
    # 생성 컬럼은 **서버가 계산하므로** INSERT 직후 파이썬 객체에는 없다.
    #   refresh해야 값이 올라온다.
    await db.refresh(r)
    return r


# ---------------------------------------------------------------------------
# 1. 값을 대입하면 어떻게 되는가 — 원시 SQL과 ORM은 결과가 다르다
# ---------------------------------------------------------------------------


async def test_raw_sql_insert_with_net_amount_is_rejected(
    db: AsyncSession, make_property
):
    """1-a. 원시 SQL로 net_amount를 지정하면 **PostgreSQL이 거부한다.**

    생성 컬럼의 정의 그 자체다. 이 테스트가 실패하면 ④가 DB에 적용되지
    않았다는 뜻이다(제약 대조로는 알 수 없는 자리).
    """
    prop, conn = await make_property(BookableUnitType.PROPERTY)
    await db.commit()

    with pytest.raises(DBAPIError) as exc:
        await db.execute(
            text(
                "INSERT INTO reservations "
                "(property_id, channel_connection_id, check_in, check_out, "
                " gross_amount, fee_amount, net_amount) "
                "VALUES (:p, :c, :i, :o, :g, :f, :n)"
            ).bindparams(
                p=prop.property_id,
                c=conn.connection_id,
                i=D10,
                o=D12,
                g=GROSS,
                f=FEE,
                n=999,
            )
        )
    await db.rollback()

    msg = str(exc.value.orig)
    assert "net_amount" in msg
    assert "non-DEFAULT" in msg or "generated" in msg.lower()


async def test_orm_none_is_ignored_but_a_value_is_rejected(
    db: AsyncSession, make_property
):
    """1-b. ORM은 **None이면 무시하고, 실제 값이면 DB까지 보내 거부당한다.**

    두 갈래인 이유가 소스에 있다.
      - `orm/persistence.py:352` — `value is None`이면 `continue`로 INSERT에서
        빠진다.
      - `orm/mapper.py:2742 _insert_cols_as_none` — `not col.server_default`
        조건이라, `Computed`(= server_default)인 이 컬럼은 "명시적 None 보강"
        대상에서도 제외된다.
      - 반면 **None이 아닌 값**은 `params[col.key] = value`로 실려 나가고,
        PostgreSQL이 `GeneratedAlwaysError`로 거부한다.

    ⚠️ 이 테스트는 관측된 동작을 그대로 고정한 것이다. 작성 시점의 예상은
    "정수를 넣어도 무시된다"였으나 **실제로는 거부됐다.** 따라서
    `ReservationCreateRequest`에서 필드를 지운 조치는 단순한 위생 조치가
    아니라, 요청 본문에 금액이 실려 올 때 500을 막는 실질적인 방어다.
    """
    prop, conn = await make_property(BookableUnitType.PROPERTY)
    await db.commit()

    # (1) None을 명시해도 INSERT에서 빠지므로 에러가 없다
    ok = Reservation(
        property_id=prop.property_id,
        channel_connection_id=conn.connection_id,
        check_in=D10,
        check_out=D12,
        gross_amount=GROSS,
        fee_amount=FEE,
        net_amount=None,
    )
    db.add(ok)
    await db.flush()
    await db.refresh(ok)
    assert ok.net_amount == NET  # 서버가 계산한 값이 들어온다
    await db.commit()

    # (2) 실제 값을 넣으면 INSERT에 실려 PostgreSQL이 거부한다
    bad = Reservation(
        property_id=prop.property_id,
        channel_connection_id=conn.connection_id,
        check_in=date(2026, 12, 1),
        check_out=date(2026, 12, 3),
        gross_amount=GROSS,
        fee_amount=FEE,
        net_amount=999,
    )
    db.add(bad)
    with pytest.raises(DBAPIError) as exc:
        await db.flush()
    await db.rollback()

    msg = str(exc.value.orig)
    assert "net_amount" in msg
    assert "non-DEFAULT" in msg


# ---------------------------------------------------------------------------
# 2~5. 계산 결과 — NULL 전파 포함
# ---------------------------------------------------------------------------


async def test_net_amount_is_computed_by_db(db: AsyncSession, make_property):
    """2. gross=100000, fee=15500 → net=84500."""
    prop, conn = await make_property(BookableUnitType.PROPERTY)
    r = await _make_reservation(db, prop=prop, conn=conn)
    await db.commit()

    assert (r.gross_amount, r.fee_amount, r.net_amount) == (GROSS, FEE, NET)


@pytest.mark.parametrize(
    "gross, fee",
    [
        (None, FEE),    # 3. gross만 NULL
        (GROSS, None),  # 4. fee만 NULL
        (None, None),   # 5. 둘 다 NULL
    ],
    ids=["gross_null", "fee_null", "both_null"],
)
async def test_null_operand_makes_net_null(
    db: AsyncSession, make_property, gross, fee
):
    """3·4·5. 피연산자가 하나라도 NULL이면 net도 NULL이다(db_spec 2.6절).

    base_price가 0이면 gross를 "미설정"으로 보고 NULL로 두는 정책이 있어
    실제로 발생하는 경로다. 0원으로 계산되면 "수수료만큼 손해 본 예약"처럼
    보이므로 NULL이어야 한다.
    """
    prop, conn = await make_property(BookableUnitType.PROPERTY)
    r = await _make_reservation(db, prop=prop, conn=conn, gross=gross, fee=fee)
    await db.commit()

    assert r.net_amount is None


# ---------------------------------------------------------------------------
# 6~7. UPDATE 추종 — gross와 fee 양쪽을 본다
# ---------------------------------------------------------------------------


async def test_net_follows_gross_update(db: AsyncSession, make_property):
    """6. gross를 바꾸면 net이 따라 바뀐다."""
    prop, conn = await make_property(BookableUnitType.PROPERTY)
    r = await _make_reservation(db, prop=prop, conn=conn)
    await db.commit()

    r.gross_amount = 200_000
    await db.flush()
    await db.refresh(r)

    assert r.net_amount == 200_000 - FEE


async def test_net_follows_fee_update(db: AsyncSession, make_property):
    """7. fee를 바꿔도 net이 따라 바뀐다.

    6번과 한 쌍이다. 수식을 `gross_amount - fee_amount`가 아니라
    `gross_amount - 15500` 같은 형태로 잘못 써도 6번만으로는 통과한다.
    """
    prop, conn = await make_property(BookableUnitType.PROPERTY)
    r = await _make_reservation(db, prop=prop, conn=conn)
    await db.commit()

    r.fee_amount = 30_000
    await db.flush()
    await db.refresh(r)

    assert r.net_amount == GROSS - 30_000


# ---------------------------------------------------------------------------
# 8~9. 애플리케이션 경로 — DTO와 응답
# ---------------------------------------------------------------------------


async def test_create_request_rejects_net_amount_but_still_works(
    db: AsyncSession, host, make_property
):
    """8. 요청 스키마는 net_amount를 받지 않고, 예약 생성은 여전히 동작한다.

    DTO에서 필드를 지운 이유는 **API가 받아선 안 되는 값**이기 때문이다.
    (1-b에서 보듯 ORM 경로는 값을 무시하므로 "지우지 않으면 항상 깨진다"는
    아니지만, 받아서 조용히 버리는 API는 호스트에게 거짓말을 하는 셈이다.)
    """
    assert "net_amount" not in ReservationCreateRequest.model_fields

    prop, conn = await make_property(BookableUnitType.PROPERTY)
    await db.commit()

    payload = ReservationCreateRequest(
        property_id=prop.property_id,
        channel_connection_id=conn.connection_id,
        check_in=D10,
        check_out=D12,
        gross_amount=GROSS,
        fee_amount=FEE,
    )
    # model_dump()에 net_amount 키가 아예 없다 — 서비스가 그대로 펼쳐도 안전하다
    assert "net_amount" not in payload.model_dump()

    reservation = await svc.create_reservation(
        db, host_id=host.host_id, payload=payload
    )
    await db.commit()

    assert reservation.reservation_id is not None


async def test_response_carries_db_computed_net_amount(
    db: AsyncSession, host, make_property
):
    """9. 생성된 예약을 응답 DTO로 직렬화하면 net_amount가 채워져 있다.

    ④ 이전에는 요청에서 들어온 파이썬 값이라 DB를 다녀오지 않아도 객체에
    있었다. **이제는 서버가 계산하므로 DB에서 가져와야만 채워진다** —
    ④에서 실제로 깨질 가능성이 가장 높은 자리다.
    """
    prop, conn = await make_property(BookableUnitType.PROPERTY)
    await db.commit()

    reservation = await svc.create_reservation(
        db,
        host_id=host.host_id,
        payload=ReservationCreateRequest(
            property_id=prop.property_id,
            channel_connection_id=conn.connection_id,
            check_in=D10,
            check_out=D12,
            gross_amount=GROSS,
            fee_amount=FEE,
        ),
    )
    await db.commit()
    await db.refresh(reservation)

    # [9/14] `is_conflict`가 필수가 되면서 `model_validate`로는 만들 수 없다 —
    #   DB 컬럼이 아니라 서버가 계산하는 파생 필드라 ORM 객체에 없기 때문이다.
    #   기본값을 없앤 것이 의도한 결과다(계산을 빠뜨린 경로가 드러난다).
    #   이 테스트가 보는 것은 net_amount이므로 충돌 여부는 False로 고정한다.
    body = ReservationResponse.from_model(reservation, is_conflict=False).model_dump()

    assert body["net_amount"] is not None
    assert body["net_amount"] == body["gross_amount"] - body["fee_amount"] == NET
