"""DB 제약 위반 → 도메인 예외 번역 회귀 테스트.

### 왜 별도 테스트가 필요한가

`test_reservation_integrity.py` 20건은 전부 **서비스 레이어를 거친다.**
그런데 서비스 레이어의 `validate_unit_hierarchy()`·Pydantic 검증이 잘못된
조합을 **DB에 닿기 전에** 막아버리므로, 그 20건은 `_translate_integrity_error()`의
제약명 분기를 **한 번도 실행하지 않는다.** 실제로 9/10에 그 분기가
asyncpg에서 항상 거짓이었는데도 20건이 전부 통과하고 있었다.

그래서 이 파일은 **애플리케이션 레이어를 의도적으로 우회**한다 —
`Reservation` 모델을 직접 `db.add()` + `flush()`해서 DB 제약까지 도달시키고,
올라온 `IntegrityError`를 `_translate_integrity_error()`에 직접 넣어 번역
결과를 확인한다.

### 이 경로가 실제로 일어나는가

일어난다. 서비스 레이어 검사와 INSERT 사이에 다른 트랜잭션이 끼어드는
동시성 상황에서 DB 제약이 마지막 방어선으로 작동한다. 그때 번역이 실패하면
호스트에게 엉뚱한 에러 코드(또는 500)가 나간다.
"""

from __future__ import annotations

from datetime import date

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import InvalidUnitHierarchyError
from app.models.enums import BookableUnitType
from app.models.property import Bed, Room
from app.models.reservation import Reservation
from app.services.reservation_service import _translate_integrity_error


async def _capture_integrity_error(db: AsyncSession, reservation: Reservation):
    """DB 제약까지 도달시키고 올라온 IntegrityError를 돌려준다.

    서비스 함수를 거치지 않는 것이 **이 헬퍼의 존재 이유**다. 거치면
    애플리케이션 검증이 먼저 막아 DB 제약이 발동하지 않는다.
    """
    db.add(reservation)
    try:
        await db.flush()
    except IntegrityError as exc:
        await db.rollback()
        return exc

    await db.rollback()
    pytest.fail("DB 제약이 발동하지 않았다 — 테스트 전제가 깨졌다")


@pytest.mark.asyncio
async def test_hierarchy_fk_violation_translates_to_invalid_unit_hierarchy(
    db: AsyncSession, make_property
):
    """다른 숙소 소속 객실을 참조하면 `fk_reservations_room_property` 위반(23503).

    → `INVALID_UNIT_HIERARCHY`여야 한다. `RESOURCE_NOT_FOUND`가 나오면
    호스트는 "예약이 없다"는 엉뚱한 메시지를 받는다.
    """
    prop_a, conn_a = await make_property(BookableUnitType.ROOM)
    prop_b, _ = await make_property(BookableUnitType.ROOM)

    room_of_b = await db.scalar(
        select(Room).where(Room.property_id == prop_b.property_id)
    )
    assert room_of_b is not None

    exc = await _capture_integrity_error(
        db,
        Reservation(
            property_id=prop_a.property_id,
            room_id=room_of_b.room_id,  # ← 남의 숙소 객실
            channel_connection_id=conn_a.connection_id,
            check_in=date(2026, 10, 1),
            check_out=date(2026, 10, 3),
        ),
    )

    sqlstate = getattr(exc.orig, "sqlstate", None) or getattr(exc.orig, "pgcode", None)
    assert sqlstate == "23503", f"기대한 제약이 아니다: {sqlstate}"

    translated = _translate_integrity_error(exc)

    assert isinstance(translated, InvalidUnitHierarchyError), (
        f"계층 FK 위반이 번역되지 않았다: {type(translated).__name__}"
    )
    assert translated.code == "INVALID_UNIT_HIERARCHY"
    assert translated.status_code == 400


@pytest.mark.asyncio
async def test_unit_shape_check_violation_translates_to_domain_error(
    db: AsyncSession, make_property
):
    """bed_id만 있고 room_id가 NULL이면 `ck_reservations_unit_shape` 위반(23514).

    → 도메인 예외여야 한다. 번역에 실패하면 원시 `IntegrityError`가 그대로
    올라가 **500**이 나간다.

    (room_id가 NULL이라 `fk_reservations_bed_room`은 MATCH SIMPLE 규칙으로
    검사가 스킵되므로 CHECK만 발동한다.)
    """
    prop, conn = await make_property(BookableUnitType.BED)

    bed = await db.scalar(
        select(Bed).join(Room, Bed.room_id == Room.room_id).where(
            Room.property_id == prop.property_id
        )
    )
    assert bed is not None

    exc = await _capture_integrity_error(
        db,
        Reservation(
            property_id=prop.property_id,
            room_id=None,  # ← bed_id만 있고 room_id가 없는 금지 조합
            bed_id=bed.bed_id,
            channel_connection_id=conn.connection_id,
            check_in=date(2026, 10, 5),
            check_out=date(2026, 10, 7),
        ),
    )

    sqlstate = getattr(exc.orig, "sqlstate", None) or getattr(exc.orig, "pgcode", None)
    assert sqlstate == "23514", f"기대한 제약이 아니다: {sqlstate}"

    translated = _translate_integrity_error(exc)

    assert isinstance(translated, InvalidUnitHierarchyError), (
        f"CHECK 위반이 번역되지 않아 500이 된다: {type(translated).__name__}"
    )
    assert translated.code == "INVALID_UNIT_HIERARCHY"
    assert translated.status_code == 400
