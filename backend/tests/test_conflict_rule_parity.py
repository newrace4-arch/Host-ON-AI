"""🔴 겹침 판정 규칙 — SQL 경로와 메모리 경로가 같은 답을 내는지 고정한다.

## 왜 이 파일이 있는가

`is_conflict`를 목록에서 계산할 때 예약마다 `find_conflicting_reservations`를
부르면 **N+1 쿼리**가 된다(30건이면 31쿼리). 같은 숙소의 예약은 이미 전부
읽어 왔으므로 쌍끼리 비교하면 쿼리가 한 번이다.

**그 대신 판정 규칙이 두 곳에 생긴다.**

    units_collide / dates_collide       ← 규칙의 원본(순수 함수)
    _conflict_query                     ← 같은 규칙의 SQL 표현

*"한 곳에 둔다"*를 말로만 하면 지켜지지 않는다. 이 파일은 **같은 데이터에
두 경로를 둘 다 돌려 결과가 일치하는지** 본다 — 한쪽만 고치면 여기가 그
자리에서 터진다.

오늘 계층 검증 함수가 넷으로 늘어난 것(`validate_unit_hierarchy` /
`_validate_room_for_channel` / `_validate_unit_for_room_creation` /
`_validate_unit_for_bed_creation`)이 **이름만 비슷하고 뜻이 달라** 합칠 수
없었던 것과는 경우가 다르다. 여기 둘은 **뜻이 같아야 한다.**

## 무엇을 덮는가

- 독채 ↔ 객실 ↔ 침대 **교차 조합 전수**
- **경계** — 체크아웃일과 다음 체크인일이 같은 날(연박 이어짐)
- `PENDING` 등 비활성 상태가 제외되는지
"""

from __future__ import annotations

import uuid
from datetime import date

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import (
    AccommodationType,
    BookableUnitType,
    Channel,
    FinancialStatus,
    RefundStatus,
    ReservationStatus,
)
from app.models.channel import ChannelConnection
from app.models.property import Bed, Property, Room
from app.models.reservation import Reservation
from app.services import reservation_service as rs

pytestmark = pytest.mark.asyncio

D = date


@pytest_asyncio.fixture
async def bed_property(db: AsyncSession, host):
    """BED 단위 숙소 하나 + 객실 2 + 침대 2(101호) — 교차 조합을 전부 만들 수 있다."""
    prop = Property(
        host_id=host.host_id,
        name="패리티숙소",
        accommodation_type=AccommodationType.HOSTEL,
        bookable_unit_type=BookableUnitType.BED,
    )
    db.add(prop)
    await db.commit()
    await db.refresh(prop)

    r101 = Room(property_id=prop.property_id, room_name="101")
    r102 = Room(property_id=prop.property_id, room_name="102")
    db.add_all([r101, r102])
    await db.commit()
    await db.refresh(r101)
    await db.refresh(r102)

    b_a = Bed(room_id=r101.room_id, bed_label="A")
    b_b = Bed(room_id=r101.room_id, bed_label="B")
    conn = ChannelConnection(property_id=prop.property_id, channel=Channel.AIRBNB)
    db.add_all([b_a, b_b, conn])
    await db.commit()
    await db.refresh(b_a)
    await db.refresh(b_b)
    await db.refresh(conn)

    return {
        "property_id": prop.property_id,
        "room_101": r101.room_id,
        "room_102": r102.room_id,
        "bed_a": b_a.bed_id,
        "bed_b": b_b.bed_id,
        "conn": conn.connection_id,
    }


async def _add(db, ctx, *, room_id, bed_id, check_in, check_out,
               status=ReservationStatus.CONFIRMED):
    """**서비스를 거치지 않고** 직접 넣는다 — 겹치는 행을 일부러 만들어야 한다.

    `create_reservation`을 쓰면 409로 막혀 교차 충돌을 만들 수 없다. EXCLUDE는
    같은 층끼리만 보므로 교차 조합은 DB가 받아준다(9/14 실측).
    """
    r = Reservation(
        property_id=ctx["property_id"],
        room_id=room_id,
        bed_id=bed_id,
        channel_connection_id=ctx["conn"],
        external_uid=f"parity-{uuid.uuid4().hex[:8]}",
        check_in=check_in,
        check_out=check_out,
        reservation_status=status,
        refund_status=RefundStatus.NONE,
        financial_status=FinancialStatus.ESTIMATED,
    )
    db.add(r)
    await db.commit()
    await db.refresh(r)
    return r


async def _sql_says(db, ctx, target: Reservation) -> bool:
    """SQL 경로 — `_conflict_query`를 타는 쪽."""
    return await rs.is_conflicting(db, target)


def _memory_says(target: Reservation, others: list[Reservation]) -> bool:
    """메모리 경로 — `units_collide`/`dates_collide`를 타는 쪽."""
    return any(rs.reservations_collide(target, o) for o in others)


# ---------------------------------------------------------------------------
# 1. 순수 함수 자체 — 교차 조합 전수 (DB 없이)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("a", "b", "expected"),
    [
        # (room_id, bed_id) 쌍
        ((None, None), (None, None), True),    # 독채 ↔ 독채
        ((None, None), (5, None), True),       # 독채 ↔ 객실
        ((None, None), (5, 9), True),          # 독채 ↔ 침대
        ((5, None), (None, None), True),       # 대칭
        ((5, 9), (None, None), True),          # 대칭
        ((5, None), (5, None), True),          # 같은 객실 통째끼리
        ((5, None), (5, 9), True),             # 객실 통째 ↔ 그 객실 침대
        ((5, 9), (5, None), True),             # 대칭
        ((5, None), (6, None), False),         # 다른 객실
        ((5, 9), (6, 9), False),               # 다른 객실의 침대
        ((5, 9), (5, 9), True),                # 같은 침대
        ((5, 9), (5, 10), False),              # 같은 객실 다른 침대
    ],
)
async def test_units_collide_matrix(a, b, expected):
    """`units_collide`의 진리표. **대칭이어야 한다.**"""
    assert rs.units_collide(a[0], a[1], b[0], b[1]) is expected
    assert rs.units_collide(b[0], b[1], a[0], a[1]) is expected


@pytest.mark.parametrize(
    ("a_in", "a_out", "b_in", "b_out", "expected"),
    [
        (D(2026, 11, 1), D(2026, 11, 5), D(2026, 11, 3), D(2026, 11, 7), True),
        (D(2026, 11, 1), D(2026, 11, 5), D(2026, 11, 5), D(2026, 11, 8), False),
        (D(2026, 11, 5), D(2026, 11, 8), D(2026, 11, 1), D(2026, 11, 5), False),
        (D(2026, 11, 1), D(2026, 11, 5), D(2026, 11, 4), D(2026, 11, 5), True),
        (D(2026, 11, 1), D(2026, 11, 9), D(2026, 11, 3), D(2026, 11, 5), True),
        (D(2026, 11, 1), D(2026, 11, 2), D(2026, 11, 9), D(2026, 11, 10), False),
    ],
)
async def test_dates_collide_boundary(a_in, a_out, b_in, b_out, expected):
    """🔴 **경계** — 체크아웃일 == 다음 체크인일은 겹침이 아니다(반개구간)."""
    assert rs.dates_collide(a_in, a_out, b_in, b_out) is expected
    assert rs.dates_collide(b_in, b_out, a_in, a_out) is expected


# ---------------------------------------------------------------------------
# 2. 🔴 두 경로 패리티 — 같은 데이터, 같은 답
# ---------------------------------------------------------------------------


async def test_parity_cross_unit_combinations(db: AsyncSession, bed_property):
    """독채·객실·침대를 한 숙소에 섞어 놓고 **두 경로의 답을 전수 대조**한다.

    EXCLUDE는 같은 층끼리만 보므로 아래 5건이 전부 DB에 들어간다.
    """
    ctx = bed_property
    made = [
        # 독채 11/01~11/05
        await _add(db, ctx, room_id=None, bed_id=None,
                   check_in=D(2026, 11, 1), check_out=D(2026, 11, 5)),
        # 101호 통째 11/03~11/07  → 독채와 겹침
        await _add(db, ctx, room_id=ctx["room_101"], bed_id=None,
                   check_in=D(2026, 11, 3), check_out=D(2026, 11, 7)),
        # 101호 A침대 11/06~11/09 → 위 101호 통째와 겹침
        await _add(db, ctx, room_id=ctx["room_101"], bed_id=ctx["bed_a"],
                   check_in=D(2026, 11, 6), check_out=D(2026, 11, 9)),
        # 101호 B침대 11/20~11/22 → 아무와도 안 겹침
        await _add(db, ctx, room_id=ctx["room_101"], bed_id=ctx["bed_b"],
                   check_in=D(2026, 11, 20), check_out=D(2026, 11, 22)),
        # 102호 통째 11/01~11/05 → 독채와만 겹침(101호와는 다른 객실)
        await _add(db, ctx, room_id=ctx["room_102"], bed_id=None,
                   check_in=D(2026, 11, 1), check_out=D(2026, 11, 5)),
    ]

    for target in made:
        others = [o for o in made if o.reservation_id != target.reservation_id]
        sql = await _sql_says(db, ctx, target)
        mem = _memory_says(target, others)
        assert sql == mem, (
            "두 경로의 답이 다르다 — 규칙이 갈렸다. "
            f"reservation_id={target.reservation_id} "
            f"room={target.room_id} bed={target.bed_id} "
            f"{target.check_in}~{target.check_out} SQL={sql} MEM={mem}"
        )


async def test_parity_on_boundary_dates(db: AsyncSession, bed_property):
    """🔴 **경계에서도 두 경로가 같아야 한다** — 연박 이어짐(체크아웃=체크인).

    한쪽이 `<=`를 쓰고 다른 쪽이 `<`를 쓰면 **여기서만** 답이 갈린다.
    건수 비교로는 잡히지 않는 자리다.
    """
    ctx = bed_property
    a = await _add(db, ctx, room_id=ctx["room_101"], bed_id=None,
                   check_in=D(2026, 12, 1), check_out=D(2026, 12, 5))
    b = await _add(db, ctx, room_id=ctx["room_101"], bed_id=None,
                   check_in=D(2026, 12, 5), check_out=D(2026, 12, 8))

    for target, others in ((a, [b]), (b, [a])):
        sql = await _sql_says(db, ctx, target)
        mem = _memory_says(target, others)
        assert sql == mem
        assert sql is False, "연박 이어짐은 겹침이 아니다"


async def test_parity_excludes_inactive_status(db: AsyncSession, bed_property):
    """`PENDING`·`CANCELLED`는 두 경로 **모두** 겹침으로 보지 않는다.

    `ACTIVE_STATUSES`가 `CONFIRMED`·`MODIFIED`뿐이라 EXCLUDE도 이 둘만
    막는다 — 4.4절이 `is_conflict`에서 `PENDING`을 뺀 근거다.
    """
    ctx = bed_property
    confirmed = await _add(db, ctx, room_id=ctx["room_101"], bed_id=None,
                           check_in=D(2027, 1, 1), check_out=D(2027, 1, 5))
    pending = await _add(db, ctx, room_id=ctx["room_101"], bed_id=None,
                         check_in=D(2027, 1, 2), check_out=D(2027, 1, 4),
                         status=ReservationStatus.PENDING)

    for target, others in ((confirmed, [pending]), (pending, [confirmed])):
        sql = await _sql_says(db, ctx, target)
        mem = _memory_says(target, others)
        assert sql == mem
        assert sql is False


async def test_parity_matches_list_endpoint_path(db: AsyncSession, host, bed_property):
    """목록 서비스(`list_reservations`)가 채우는 값도 SQL 경로와 일치한다.

    앞의 셋은 함수 단위 대조이고, 이것은 **실제 엔드포인트가 쓰는 경로**를
    본다 — 목록 쪽에 필터가 하나 더 있어(조회 구간) 그것이 판정을 바꾸지
    않는지 확인한다.
    """
    ctx = bed_property
    await _add(db, ctx, room_id=None, bed_id=None,
               check_in=D(2027, 3, 1), check_out=D(2027, 3, 5))
    await _add(db, ctx, room_id=ctx["room_101"], bed_id=None,
               check_in=D(2027, 3, 2), check_out=D(2027, 3, 4))

    rows = await reservation_service_list(db, ctx, host)
    assert len(rows) == 2
    for r, mem_flag in rows:
        sql_flag = await rs.is_conflicting(db, r)
        assert sql_flag == mem_flag
        assert sql_flag is True


async def reservation_service_list(db, ctx, host):
    return await rs.list_reservations(
        db,
        property_id=ctx["property_id"],
        host_id=host.host_id,
        start=D(2027, 3, 1),
        end=D(2027, 3, 31),
    )
