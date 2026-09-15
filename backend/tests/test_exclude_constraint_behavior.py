"""🔴 EXCLUDE 제약 3종이 **실제로 막는지**를 실행으로 확인한다 (r54).

## 왜 이 파일이 따로 필요한가

제약은 9/5(`a457074`)에 마이그레이션으로 들어갔고 실제 DB에 걸려 있는 것도
제약 기준선(`backend/tests/snapshots/constraints_baseline_20260913_v14.txt`)에 고정돼 있다.
**그런데 그것이 정말 INSERT를 거부하는지는 한 번도 실행으로 확인된 적이
없었다**(9/14 조사) — 저장소 전체에서 EXCLUDE 위반을 일으키는 테스트가
**0건**이었다.

인접한 두 파일은 **다른 것을 본다:**

| 파일 | 보는 것 |
|---|---|
| `test_reservation_integrity.py` | 서비스 인터셉터가 **층간** 겹침을 막는가 (EXCLUDE가 못 보는 영역) |
| `test_conflict_rule_parity.py` | SQL 경로와 메모리 경로의 **판정이 같은가** |
| **이 파일** | **DB가 같은 층 겹침을 거부하는가** |

패리티 테스트가 넣는 조합은 **의도적으로 EXCLUDE가 통과시키는 것들뿐**이다
(*"EXCLUDE는 같은 층끼리만 보므로 교차 조합은 DB가 받아준다"* — 그 파일
`_add()` 도크스트링). 그래서 그 22건이 전부 초록이어도 **제약이 통째로
빠져 있는 것을 알 수 없다.**

## 무엇을 덮는가 — 체크리스트 r54 확인방법 그대로

> *"같은 room에 겹치는 날짜로 2건 INSERT → 2번째가 에러나는지,
> 취소된 예약과는 겹쳐도 통과하는지 둘 다 확인"*

- **(a)** 세 단위(PROPERTY/ROOM/BED) 각각에서 두 번째 INSERT가 거부되는가.
  거부될 때 `sqlstate`가 `23P01`인가. `_overlap_unit_label`이 **어느
  단위인지** 정확히 번역하는가(세 분기 전부).
- **(b)** `CANCELLED`·`PENDING`과는 겹쳐도 **INSERT가 통과**하는가.

**(a)는 `_translate_integrity_error`의 `23P01` 분기와 `_overlap_unit_label`
세 분기를 실행하는 유일한 테스트다.** 그 전까지 이 코드는 정적 판독으로만
*"정상 작동한다"*고 적혀 있었다(troubleshooting 30번 본문).

## 서비스를 거치지 않는다

`create_reservation`은 `assert_no_overlap`이 **DB 앞에서** 409로 막아
IntegrityError가 올라올 일이 없다. 여기서 보려는 것은 **그 방어선이
뚫렸을 때의 마지막 방어선**이므로, 모델을 직접 `db.add()` 한다.

## 호스트를 남기지 않는다

`conftest.py`의 `host`/`make_property` 픽스처만 쓴다. 지역 헬퍼로 호스트를
만들면 teardown 경로를 타지 않아 `hosts`에 누적된다
(`test_reservations_api.py` 도크스트링 — 9/14에 `other-*` 59건).
이 파일은 호스트를 **하나도 새로 만들지 않는다.**
"""

from __future__ import annotations

from datetime import date

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ReservationOverlapError
from app.models.enums import BookableUnitType, ReservationStatus
from app.models.property import Bed, Room
from app.models.reservation import Reservation
from app.services import reservation_service as rs
from app.utils.db_errors import violates_constraint

pytestmark = pytest.mark.asyncio

D = date

# 세 단위 × (제약 이름, `_overlap_unit_label`이 내놓아야 할 말).
#   레이블은 `reservation_service._overlap_unit_label`의 세 분기와 1:1이다 —
#   그 함수가 문구를 바꾸면 여기가 터진다.
UNIT_CASES = [
    pytest.param(
        BookableUnitType.PROPERTY, "excl_property_overlap", "숙소 전체", id="PROPERTY"
    ),
    pytest.param(BookableUnitType.ROOM, "excl_room_overlap", "객실", id="ROOM"),
    pytest.param(BookableUnitType.BED, "excl_bed_overlap", "침대", id="BED"),
]

INACTIVE_STATUSES = [
    pytest.param(ReservationStatus.CANCELLED, id="CANCELLED"),
    pytest.param(ReservationStatus.PENDING, id="PENDING"),
]


async def _unit_ctx(db: AsyncSession, make_property, unit: BookableUnitType) -> dict:
    """그 단위의 예약을 만들 수 있는 id들을 **평범한 int로** 뽑아 둔다.

    🔴 **모델 인스턴스를 들고 다니지 않는다.** 아래 `_expect_exclusion`이
    `rollback()`을 부르면 세션의 모든 인스턴스가 만료되고, 그 뒤에 속성을
    읽으면 지연로딩(동기 IO)이 일어나 `MissingGreenlet`이 난다
    (`conftest.py`의 `host` 픽스처가 `host_id`를 미리 뽑아 두는 것과 같은
    이유).
    """
    prop, conn = await make_property(unit)
    ctx = {
        "property_id": prop.property_id,
        "conn": conn.connection_id,
        "room_id": None,
        "bed_id": None,
    }
    if unit is BookableUnitType.PROPERTY:
        return ctx

    room = await db.scalar(select(Room).where(Room.property_id == ctx["property_id"]))
    ctx["room_id"] = room.room_id
    if unit is BookableUnitType.BED:
        bed = await db.scalar(
            select(Bed).where(Bed.room_id == ctx["room_id"]).order_by(Bed.bed_label)
        )
        ctx["bed_id"] = bed.bed_id
    return ctx


def _res(
    ctx: dict,
    *,
    check_in: date,
    check_out: date,
    uid: str,
    status: ReservationStatus = ReservationStatus.CONFIRMED,
) -> Reservation:
    """ctx가 가리키는 판매단위의 예약 1건.

    `external_uid`를 매번 다르게 준다 — 비워 두면 `uq_reservation_channel_uid`
    쪽에서 걸릴 여지가 생겨 *"무엇 때문에 거부됐는지"*가 흐려진다.
    `net_amount`는 생성 컬럼이라 **대입하지 않는다**(모델 도크스트링).
    """
    return Reservation(
        property_id=ctx["property_id"],
        room_id=ctx["room_id"],
        bed_id=ctx["bed_id"],
        channel_connection_id=ctx["conn"],
        external_uid=uid,
        check_in=check_in,
        check_out=check_out,
        reservation_status=status,
    )


def _sqlstate(exc: IntegrityError) -> str | None:
    """`_translate_integrity_error`가 보는 것과 **같은 방식**으로 읽는다."""
    orig = exc.orig
    return getattr(orig, "sqlstate", None) or getattr(orig, "pgcode", None)


async def _expect_exclusion(db: AsyncSession, obj: Reservation) -> IntegrityError:
    """제약까지 도달시키고 올라온 `IntegrityError`를 돌려준다.

    거부되지 않으면 **그 자리에서 실패시킨다** — 통과해 버린 것을 조용히
    넘기면 이 파일이 존재하는 이유가 사라진다.
    """
    db.add(obj)
    try:
        await db.flush()
    except IntegrityError as exc:
        await db.rollback()
        return exc

    await db.rollback()
    pytest.fail("EXCLUDE가 발동하지 않았다 — 겹치는 2번째 INSERT가 통과했다")


async def _count(db: AsyncSession, property_id: int) -> int:
    return await db.scalar(
        select(func.count())
        .select_from(Reservation)
        .where(Reservation.property_id == property_id)
    )


# --------------------------------------------------------------------------
# (a) 같은 단위에 겹치는 날짜로 2건 INSERT → 2번째가 거부되는가
# --------------------------------------------------------------------------


@pytest.mark.parametrize("unit, constraint, label", UNIT_CASES)
async def test_overlapping_insert_is_rejected(
    db: AsyncSession, make_property, unit, constraint, label
):
    """🔴 r54 확인방법 ①. **DB가 실제로 거부하는지**를 실행으로 본다."""
    ctx = await _unit_ctx(db, make_property, unit)

    db.add(_res(ctx, check_in=D(2027, 5, 1), check_out=D(2027, 5, 5), uid=f"r54-{unit.value}-1"))
    await db.commit()

    exc = await _expect_exclusion(
        db,
        _res(ctx, check_in=D(2027, 5, 3), check_out=D(2027, 5, 8), uid=f"r54-{unit.value}-2"),
    )

    # ① EXCLUDE 위반이어야 한다. 다른 제약에 걸려 "거부됐다"가 되면 안 된다.
    assert _sqlstate(exc) == "23P01", f"sqlstate가 23P01이 아니다: {_sqlstate(exc)}"
    assert violates_constraint(exc, constraint), f"{constraint}이 아니다: {exc.orig}"

    # ② 첫 예약만 남아 있어야 한다.
    assert await _count(db, ctx["property_id"]) == 1

    # ③ 🔴 r49의 단위 판별 — 세 분기 전부를 여기서 실행한다.
    assert rs._overlap_unit_label(exc) == label

    # ④ 번역 결과가 409 도메인 예외여야 한다. 원시 IntegrityError가 그대로
    #    나가면 호스트에게 500이 간다.
    translated = rs._translate_integrity_error(exc)
    assert isinstance(translated, ReservationOverlapError)
    assert translated.status_code == 409
    assert translated.code == "RESERVATION_OVERLAP"
    assert f"{label} 예약" in str(translated)


# --------------------------------------------------------------------------
# (b) 비활성 상태와는 겹쳐도 INSERT가 통과하는가
# --------------------------------------------------------------------------


@pytest.mark.parametrize("unit, constraint, label", UNIT_CASES)
@pytest.mark.parametrize("inactive", INACTIVE_STATUSES)
async def test_inactive_status_does_not_block_insert(
    db: AsyncSession, make_property, unit, constraint, label, inactive
):
    """🔴 r54 확인방법 ②. EXCLUDE의 `WHERE ... IN ('CONFIRMED','MODIFIED')`.

    **양방향으로 본다** — 비활성 건이 먼저 있어도 새 확정 건이 들어가야 하고
    (취소 뒤 재판매), 확정 건이 먼저 있어도 비활성 건이 들어가야 한다.
    한쪽만 보면 **술어가 한 방향으로만 평가되는 착시**가 생긴다.

    ⚠️ 9/14 이전에는 이것이 **우연히 성립한 전제**였다. 패리티 테스트가
    `PENDING` 행을 실제로 `commit()`까지 넣기는 했지만 *"들어갔다"*를
    **단언하지 않았고**, `CANCELLED`는 아예 넣지 않았다.
    """
    ctx = await _unit_ctx(db, make_property, unit)
    tag = f"r54b-{unit.value}-{inactive.value}"

    # 방향 ① — 비활성 먼저, 확정 나중
    db.add(_res(ctx, check_in=D(2027, 6, 1), check_out=D(2027, 6, 5),
                uid=f"{tag}-a1", status=inactive))
    await db.commit()
    db.add(_res(ctx, check_in=D(2027, 6, 3), check_out=D(2027, 6, 8), uid=f"{tag}-a2"))
    await db.commit()

    # 방향 ② — 확정 먼저, 비활성 나중
    db.add(_res(ctx, check_in=D(2027, 7, 1), check_out=D(2027, 7, 5), uid=f"{tag}-b1"))
    await db.commit()
    db.add(_res(ctx, check_in=D(2027, 7, 3), check_out=D(2027, 7, 8),
                uid=f"{tag}-b2", status=inactive))
    await db.commit()

    assert await _count(db, ctx["property_id"]) == 4, (
        f"{inactive.value}이 {label} 단위에서 겹침으로 막혔다 — "
        "EXCLUDE의 상태 술어가 어긋났다"
    )
