"""예약 무결성 회귀 테스트 (명세서 5절 6번).

DB가 잡아주지 못해 서비스 레이어가 책임지는 두 규칙을 고정한다:
  - troubleshooting.md 2번: bookable_unit_type ↔ room_id/bed_id 교차 검증
  - troubleshooting.md 1번: PROPERTY ↔ ROOM/BED 교차 기간 충돌 검사
"""

from __future__ import annotations

from datetime import date

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    InvalidUnitHierarchyError,
    ReservationOverlapError,
    ResourceNotFoundError,
)
from app.models import Bed, ChannelConnection, Host, Property, Reservation, Room
from app.models.enums import BookableUnitType, ReservationStatus
from app.schemas.reservation import ReservationCreateRequest
from app.services import reservation_service as svc

D10 = date(2026, 9, 10)
D12 = date(2026, 9, 12)
D11 = date(2026, 9, 11)
D13 = date(2026, 9, 13)
D14 = date(2026, 9, 14)


async def _unit_ids(db: AsyncSession, prop: Property) -> tuple[int | None, list[int]]:
    room = await db.scalar(select(Room).where(Room.property_id == prop.property_id))
    if room is None:
        return None, []
    beds = (await db.scalars(select(Bed).where(Bed.room_id == room.room_id).order_by(Bed.bed_label))).all()
    return room.room_id, [b.bed_id for b in beds]


async def _insert_raw_reservation(
    db: AsyncSession,
    *,
    prop: Property,
    conn: ChannelConnection,
    room_id: int | None = None,
    bed_id: int | None = None,
    check_in: date = D10,
    check_out: date = D12,
    status: ReservationStatus = ReservationStatus.CONFIRMED,
) -> Reservation:
    """서비스 검증을 우회해 예약을 직접 만든다.

    실제로도 이런 행은 생긴다 — iCal 동기화로 들어온 과거 예약이 남아 있는데
    호스트가 숙소의 판매단위를 바꾸는 경우. 교차 충돌 검사가 필요한 이유가
    바로 이 상황이므로, 테스트도 같은 방식으로 상황을 만든다.
    """
    r = Reservation(
        property_id=prop.property_id,
        room_id=room_id,
        bed_id=bed_id,
        channel_connection_id=conn.connection_id,
        check_in=check_in,
        check_out=check_out,
        reservation_status=status,
    )
    db.add(r)
    await db.flush()
    return r


# --------------------------------------------------------------------------
# 원칙 2: bookable_unit_type ↔ room_id/bed_id 교차 검증
# --------------------------------------------------------------------------


async def test_property_unit_rejects_room_id(db: AsyncSession, make_property):
    prop, _ = await make_property(BookableUnitType.PROPERTY)
    with pytest.raises(InvalidUnitHierarchyError) as exc:
        svc.validate_unit_hierarchy(prop, room_id=1, bed_id=None)
    assert exc.value.code == "INVALID_UNIT_HIERARCHY"
    assert exc.value.status_code == 400


async def test_room_unit_requires_room_id(db: AsyncSession, make_property):
    prop, _ = await make_property(BookableUnitType.ROOM)
    with pytest.raises(InvalidUnitHierarchyError) as exc:
        svc.validate_unit_hierarchy(prop, room_id=None, bed_id=None)
    assert exc.value.code == "ROOM_ID_REQUIRED"


async def test_room_unit_rejects_bed_id(db: AsyncSession, make_property):
    prop, _ = await make_property(BookableUnitType.ROOM)
    room_id, beds = await _unit_ids(db, prop)
    with pytest.raises(InvalidUnitHierarchyError) as exc:
        svc.validate_unit_hierarchy(prop, room_id=room_id, bed_id=beds[0])
    assert exc.value.code == "ROOM_ID_REQUIRED"


async def test_bed_unit_requires_bed_id(db: AsyncSession, make_property):
    prop, _ = await make_property(BookableUnitType.BED)
    room_id, _ = await _unit_ids(db, prop)
    with pytest.raises(InvalidUnitHierarchyError) as exc:
        svc.validate_unit_hierarchy(prop, room_id=room_id, bed_id=None)
    assert exc.value.code == "BED_ID_REQUIRED"


async def test_valid_combinations_pass(db: AsyncSession, make_property):
    prop_p, _ = await make_property(BookableUnitType.PROPERTY)
    svc.validate_unit_hierarchy(prop_p, None, None)

    prop_r, _ = await make_property(BookableUnitType.ROOM)
    room_id, _ = await _unit_ids(db, prop_r)
    svc.validate_unit_hierarchy(prop_r, room_id, None)

    prop_b, _ = await make_property(BookableUnitType.BED)
    room_id, beds = await _unit_ids(db, prop_b)
    svc.validate_unit_hierarchy(prop_b, room_id, beds[0])


# --------------------------------------------------------------------------
# 원칙 1: PROPERTY ↔ ROOM/BED 교차 기간 충돌 (EXCLUDE가 못 잡는 영역)
# --------------------------------------------------------------------------


async def test_property_booking_blocks_room_booking(db: AsyncSession, make_property):
    """독채 예약이 있으면 그 하위 객실 예약을 막아야 한다."""
    prop, conn = await make_property(BookableUnitType.BED)
    room_id, _ = await _unit_ids(db, prop)
    await _insert_raw_reservation(db, prop=prop, conn=conn)  # PROPERTY 단위

    with pytest.raises(ReservationOverlapError) as exc:
        await svc.assert_no_overlap(
            db,
            property_id=prop.property_id,
            room_id=room_id,
            bed_id=None,
            check_in=D11,
            check_out=D13,
        )
    assert exc.value.status_code == 409


async def test_property_booking_blocks_bed_booking(db: AsyncSession, make_property):
    prop, conn = await make_property(BookableUnitType.BED)
    room_id, beds = await _unit_ids(db, prop)
    await _insert_raw_reservation(db, prop=prop, conn=conn)

    with pytest.raises(ReservationOverlapError):
        await svc.assert_no_overlap(
            db,
            property_id=prop.property_id,
            room_id=room_id,
            bed_id=beds[0],
            check_in=D11,
            check_out=D13,
        )


async def test_room_booking_blocks_property_booking(db: AsyncSession, make_property):
    """반대 방향도 막아야 한다 — 객실 예약이 있는데 독채 통대여를 넣는 경우."""
    prop, conn = await make_property(BookableUnitType.BED)
    room_id, _ = await _unit_ids(db, prop)
    await _insert_raw_reservation(db, prop=prop, conn=conn, room_id=room_id)

    with pytest.raises(ReservationOverlapError):
        await svc.assert_no_overlap(
            db,
            property_id=prop.property_id,
            room_id=None,
            bed_id=None,
            check_in=D11,
            check_out=D13,
        )


async def test_room_booking_blocks_bed_in_same_room(db: AsyncSession, make_property):
    prop, conn = await make_property(BookableUnitType.BED)
    room_id, beds = await _unit_ids(db, prop)
    await _insert_raw_reservation(db, prop=prop, conn=conn, room_id=room_id)

    with pytest.raises(ReservationOverlapError):
        await svc.assert_no_overlap(
            db,
            property_id=prop.property_id,
            room_id=room_id,
            bed_id=beds[0],
            check_in=D11,
            check_out=D13,
        )


async def test_different_beds_do_not_conflict(db: AsyncSession, make_property):
    """같은 객실이라도 다른 침대면 겹쳐도 된다(도미토리 정상 운영)."""
    prop, conn = await make_property(BookableUnitType.BED)
    room_id, beds = await _unit_ids(db, prop)
    await _insert_raw_reservation(db, prop=prop, conn=conn, room_id=room_id, bed_id=beds[0])

    await svc.assert_no_overlap(
        db,
        property_id=prop.property_id,
        room_id=room_id,
        bed_id=beds[1],
        check_in=D11,
        check_out=D13,
    )


async def test_back_to_back_stay_is_not_overlap(db: AsyncSession, make_property):
    """체크아웃일 == 다음 체크인일은 겹침이 아니다(EXCLUDE의 tsrange와 동일 판정)."""
    prop, conn = await make_property(BookableUnitType.PROPERTY)
    await _insert_raw_reservation(db, prop=prop, conn=conn, check_in=D10, check_out=D12)

    await svc.assert_no_overlap(
        db, property_id=prop.property_id, room_id=None, bed_id=None,
        check_in=D12, check_out=D14,
    )


async def test_cancelled_reservation_does_not_block(db: AsyncSession, make_property):
    """취소된 예약은 같은 기간을 다시 팔 수 있어야 한다."""
    prop, conn = await make_property(BookableUnitType.PROPERTY)
    await _insert_raw_reservation(
        db, prop=prop, conn=conn, status=ReservationStatus.CANCELLED
    )

    await svc.assert_no_overlap(
        db, property_id=prop.property_id, room_id=None, bed_id=None,
        check_in=D10, check_out=D12,
    )


async def test_exclude_self_when_modifying(db: AsyncSession, make_property):
    """기간 변경 시 자기 자신과 충돌났다고 판정하면 안 된다."""
    prop, conn = await make_property(BookableUnitType.PROPERTY)
    existing = await _insert_raw_reservation(db, prop=prop, conn=conn)

    await svc.assert_no_overlap(
        db, property_id=prop.property_id, room_id=None, bed_id=None,
        check_in=D11, check_out=D13,
        exclude_reservation_id=existing.reservation_id,
    )


async def test_other_property_is_unaffected(db: AsyncSession, make_property):
    """다른 숙소의 같은 기간 예약은 충돌 대상이 아니다(Property 단위 데이터 격리)."""
    prop_a, conn_a = await make_property(BookableUnitType.PROPERTY)
    prop_b, _ = await make_property(BookableUnitType.PROPERTY)
    await _insert_raw_reservation(db, prop=prop_a, conn=conn_a)

    await svc.assert_no_overlap(
        db, property_id=prop_b.property_id, room_id=None, bed_id=None,
        check_in=D10, check_out=D12,
    )


# --------------------------------------------------------------------------
# create_reservation 통합 경로
# --------------------------------------------------------------------------


async def test_create_reservation_success(db: AsyncSession, host: Host, make_property):
    prop, conn = await make_property(BookableUnitType.BED)
    room_id, beds = await _unit_ids(db, prop)

    created = await svc.create_reservation(
        db,
        host_id=host.host_id,
        payload=ReservationCreateRequest(
            property_id=prop.property_id,
            room_id=room_id,
            bed_id=beds[0],
            channel_connection_id=conn.connection_id,
            check_in=D10,
            check_out=D12,
        ),
    )
    assert created.reservation_id is not None
    assert created.reservation_status is ReservationStatus.CONFIRMED


async def test_create_reservation_rejects_overlap(
    db: AsyncSession, host: Host, make_property
):
    prop, conn = await make_property(BookableUnitType.PROPERTY)
    payload = ReservationCreateRequest(
        property_id=prop.property_id,
        channel_connection_id=conn.connection_id,
        check_in=D10,
        check_out=D12,
    )
    await svc.create_reservation(db, host_id=host.host_id, payload=payload)

    overlapping = payload.model_copy(update={"check_in": D11, "check_out": D13})
    with pytest.raises(ReservationOverlapError):
        await svc.create_reservation(db, host_id=host.host_id, payload=overlapping)


async def test_create_reservation_rejects_wrong_unit(
    db: AsyncSession, host: Host, make_property
):
    prop, conn = await make_property(BookableUnitType.PROPERTY)
    room_prop, _ = await make_property(BookableUnitType.ROOM)
    room_id, _ = await _unit_ids(db, room_prop)

    with pytest.raises(InvalidUnitHierarchyError) as exc:
        await svc.create_reservation(
            db,
            host_id=host.host_id,
            payload=ReservationCreateRequest(
                property_id=prop.property_id,
                room_id=room_id,
                channel_connection_id=conn.connection_id,
                check_in=D10,
                check_out=D12,
            ),
        )
    assert exc.value.code == "INVALID_UNIT_HIERARCHY"


async def test_create_reservation_other_host_gets_404(
    db: AsyncSession, host: Host, make_property
):
    """타인 소유 숙소는 403이 아니라 404로 통일(정보노출 방지)."""
    prop, conn = await make_property(BookableUnitType.PROPERTY)
    other = Host(email="intruder@test.local", password_hash="x", name="타인")
    db.add(other)
    await db.flush()

    with pytest.raises(ResourceNotFoundError) as exc:
        await svc.create_reservation(
            db,
            host_id=other.host_id,
            payload=ReservationCreateRequest(
                property_id=prop.property_id,
                channel_connection_id=conn.connection_id,
                check_in=D10,
                check_out=D12,
            ),
        )
    assert exc.value.status_code == 404
    assert exc.value.code == "RESOURCE_NOT_FOUND"
