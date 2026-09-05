"""예약 서비스 — DB가 보장하지 못하는 두 가지를 애플리케이션이 책임진다.

명세서 4절 0번은 "DB가 보장하는 것"과 "애플리케이션이 보장하는 것"을 나눈다.
이 모듈은 후자를 구현한다:

1. **bookable_unit_type ↔ room_id/bed_id 교차 검증** (troubleshooting.md 2번)
   `bookable_unit_type`은 PROPERTIES에, `room_id`/`bed_id`는 RESERVATIONS에
   있어 PostgreSQL 일반 CHECK로는 검증할 수 없다(다른 테이블 참조 불가).
   DB CHECK는 같은 행 내부의 형태(3가지 유효 조합)만 본다.

2. **PROPERTY ↔ ROOM/BED 교차 기간 충돌 검사** (troubleshooting.md 1번)
   EXCLUDE 제약 3종은 **같은 판매단위끼리만** 겹침을 막는다. 독채(PROPERTY)
   예약과 그 하위 객실(ROOM)/침대(BED) 예약 사이의 충돌은 DB가 잡지 못하므로
   예약 생성 트랜잭션에서 직접 조회해 막는다.

두 검증 모두 "빠뜨리면 조용히 통과하는" 종류라, 예약을 만드는 경로는 반드시
`create_reservation()`(또는 최소한 `validate_reservation_placement()`)를 거쳐야
한다. Reservation을 직접 add()하는 코드를 새로 만들지 말 것.
"""

from __future__ import annotations

from datetime import date

from sqlalchemy import Select, and_, or_, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    InvalidUnitHierarchyError,
    ReservationOverlapError,
    ResourceNotFoundError,
)
from app.models.enums import BookableUnitType, ReservationStatus
from app.models.property import Property
from app.models.reservation import Reservation
from app.schemas.reservation import ReservationCreateRequest

# 겹침 판정 대상 상태. EXCLUDE 제약 3종의 WHERE절과 반드시 같은 집합이어야 한다
#   — 여기만 넓히거나 좁히면 앱과 DB의 판정이 어긋난다.
ACTIVE_STATUSES = (ReservationStatus.CONFIRMED, ReservationStatus.MODIFIED)

# 숙소 단위 예약 직렬화용 advisory lock 네임스페이스.
#   검사(SELECT)와 삽입(INSERT) 사이에 다른 트랜잭션이 끼어들면 양쪽 다
#   "충돌 없음"으로 통과할 수 있다(TOCTOU). 같은 숙소를 건드리는 예약
#   트랜잭션을 이 락으로 직렬화한다. 다른 숙소끼리는 서로 막지 않는다.
_LOCK_NAMESPACE = 1001


def _advisory_lock_key(property_id: int) -> int:
    """숙소별 고유 bigint 락 키(네임스페이스를 상위 32비트에 둔다)."""
    return (_LOCK_NAMESPACE << 32) | property_id


async def lock_property_for_booking(db: AsyncSession, property_id: int) -> None:
    """예약 생성/변경 트랜잭션 시작 시 숙소 단위 배타 락을 잡는다.

    `pg_advisory_xact_lock`은 **트랜잭션 종료 시 자동 해제**되므로 별도
    해제 코드가 필요 없다(수동 해제를 잊어 락이 남는 사고를 피하려는 선택).
    """
    await db.execute(
        text("SELECT pg_advisory_xact_lock(:key)"), {"key": _advisory_lock_key(property_id)}
    )


async def get_owned_property(db: AsyncSession, property_id: int, host_id: int) -> Property:
    """소유권을 조회 조건에 묶어서 검증한다(파이썬 if문으로 나중에 검사하지 않음).

    부존재와 타인 소유를 구분하지 않고 똑같이 404를 던진다(정보노출 방지,
    api_contract.md 0절).
    """
    stmt = select(Property).where(
        Property.property_id == property_id, Property.host_id == host_id
    )
    prop = await db.scalar(stmt)
    if prop is None:
        raise ResourceNotFoundError("요청한 숙소를 찾을 수 없습니다.")
    return prop


def validate_unit_hierarchy(
    prop: Property, room_id: int | None, bed_id: int | None
) -> None:
    """[원칙 2] bookable_unit_type과 room_id/bed_id 조합의 의미론적 일치 검증.

    위반 시 api_contract.md 4절 표에 정의된 코드로 400을 던진다:

    | bookable_unit_type | 위반 조건                          | code                    |
    |--------------------|------------------------------------|-------------------------|
    | PROPERTY           | room_id 또는 bed_id가 NOT NULL     | INVALID_UNIT_HIERARCHY  |
    | ROOM               | room_id가 NULL 이거나 bed_id NOT NULL | ROOM_ID_REQUIRED     |
    | BED                | room_id 또는 bed_id가 NULL         | BED_ID_REQUIRED         |
    """
    unit_type = prop.bookable_unit_type

    if unit_type == BookableUnitType.PROPERTY:
        if room_id is not None or bed_id is not None:
            raise InvalidUnitHierarchyError(
                "이 숙소는 전체(PROPERTY) 단위로만 판매합니다. "
                "room_id/bed_id를 지정할 수 없습니다.",
                code="INVALID_UNIT_HIERARCHY",
            )
        return

    if unit_type == BookableUnitType.ROOM:
        if room_id is None or bed_id is not None:
            raise InvalidUnitHierarchyError(
                "이 숙소는 객실(ROOM) 단위로 판매합니다. "
                "room_id는 필수이고 bed_id는 지정할 수 없습니다.",
                code="ROOM_ID_REQUIRED",
            )
        return

    if unit_type == BookableUnitType.BED:
        if room_id is None or bed_id is None:
            raise InvalidUnitHierarchyError(
                "이 숙소는 침대(BED) 단위로 판매합니다. room_id와 bed_id가 모두 필요합니다.",
                code="BED_ID_REQUIRED",
            )
        return

    # ENUM에 값이 추가됐는데 이 함수를 갱신하지 않은 경우를 조용히 통과시키지 않는다.
    raise InvalidUnitHierarchyError(
        f"처리할 수 없는 판매 단위입니다: {unit_type}", code="INVALID_UNIT_HIERARCHY"
    )


def _conflict_query(
    *,
    property_id: int,
    room_id: int | None,
    bed_id: int | None,
    check_in: date,
    check_out: date,
    exclude_reservation_id: int | None,
) -> Select[tuple[Reservation]]:
    """같은 숙소 안에서 **판매단위를 넘나드는** 겹침까지 찾아내는 조회.

    기간 겹침은 반개구간 비교다(`기존.check_in < 신규.check_out` AND
    `기존.check_out > 신규.check_in`). 체크아웃일과 다음 체크인일이 같은 날인
    연박 이어짐은 겹침이 아니다 — EXCLUDE의 `tsrange`(하한 포함/상한 제외)와
    동일한 판정이다.

    단위별 충돌 규칙:
      - 신규가 PROPERTY(독채) → 그 숙소의 모든 활성 예약과 충돌
      - 신규가 ROOM          → 상위 PROPERTY 예약 + 같은 객실의 모든 예약(침대 포함)
      - 신규가 BED           → 상위 PROPERTY 예약 + 같은 객실의 객실통째 예약
                               + 같은 침대 예약
    """
    date_overlap = and_(Reservation.check_in < check_out, Reservation.check_out > check_in)

    if room_id is None:
        # 독채 예약은 하위 객실/침대 예약과 전부 부딪힌다.
        unit_conflict = None
    elif bed_id is None:
        unit_conflict = or_(
            Reservation.room_id.is_(None),  # 상위 독채 예약
            Reservation.room_id == room_id,  # 같은 객실(객실통째/침대 무관)
        )
    else:
        unit_conflict = or_(
            Reservation.room_id.is_(None),  # 상위 독채 예약
            and_(
                Reservation.room_id == room_id,
                or_(
                    Reservation.bed_id.is_(None),  # 그 객실 통째 예약
                    Reservation.bed_id == bed_id,  # 같은 침대 예약
                ),
            ),
        )

    conditions = [
        Reservation.property_id == property_id,
        Reservation.reservation_status.in_(ACTIVE_STATUSES),
        date_overlap,
    ]
    if unit_conflict is not None:
        conditions.append(unit_conflict)
    if exclude_reservation_id is not None:
        # 기존 예약을 수정하는 경우 자기 자신은 충돌 대상에서 제외한다.
        conditions.append(Reservation.reservation_id != exclude_reservation_id)

    return select(Reservation).where(*conditions).order_by(Reservation.check_in)


async def find_conflicting_reservations(
    db: AsyncSession,
    *,
    property_id: int,
    room_id: int | None,
    bed_id: int | None,
    check_in: date,
    check_out: date,
    exclude_reservation_id: int | None = None,
) -> list[Reservation]:
    """겹치는 예약 목록을 돌려준다(비어 있으면 충돌 없음).

    조회 전용이므로 캘린더의 `is_conflict` 파생 필드 계산에도 재사용한다.
    """
    stmt = _conflict_query(
        property_id=property_id,
        room_id=room_id,
        bed_id=bed_id,
        check_in=check_in,
        check_out=check_out,
        exclude_reservation_id=exclude_reservation_id,
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def assert_no_overlap(
    db: AsyncSession,
    *,
    property_id: int,
    room_id: int | None,
    bed_id: int | None,
    check_in: date,
    check_out: date,
    exclude_reservation_id: int | None = None,
) -> None:
    """[원칙 1] 교차 단위 겹침이 있으면 409로 막는다."""
    conflicts = await find_conflicting_reservations(
        db,
        property_id=property_id,
        room_id=room_id,
        bed_id=bed_id,
        check_in=check_in,
        check_out=check_out,
        exclude_reservation_id=exclude_reservation_id,
    )
    if conflicts:
        ids = [r.reservation_id for r in conflicts]
        raise ReservationOverlapError(
            f"같은 숙소에 기간이 겹치는 예약이 있습니다(예약번호: {ids}).",
            conflicting_reservation_ids=ids,
        )


async def validate_reservation_placement(
    db: AsyncSession,
    *,
    prop: Property,
    room_id: int | None,
    bed_id: int | None,
    check_in: date,
    check_out: date,
    exclude_reservation_id: int | None = None,
) -> None:
    """두 원칙을 한 번에 적용한다. 예약을 만들거나 기간/단위를 바꾸는 모든 경로에서 호출.

    ⚠️ 호출 순서 주의: 반드시 `lock_property_for_booking()`으로 락을 잡은 뒤
    호출해야 겹침 검사와 삽입 사이에 다른 트랜잭션이 끼어들지 않는다.
    """
    validate_unit_hierarchy(prop, room_id, bed_id)
    await assert_no_overlap(
        db,
        property_id=prop.property_id,
        room_id=room_id,
        bed_id=bed_id,
        check_in=check_in,
        check_out=check_out,
        exclude_reservation_id=exclude_reservation_id,
    )


def _translate_integrity_error(exc: IntegrityError) -> Exception:
    """DB 제약 위반을 도메인 예외로 옮긴다(마지막 방어선).

    앱 검사를 통과한 뒤에도 동시성 때문에 EXCLUDE에 걸릴 수 있고, 그때
    500을 그대로 내보내면 호스트에게 원인이 전달되지 않는다.
    """
    orig = exc.orig
    sqlstate = getattr(orig, "sqlstate", None) or getattr(orig, "pgcode", None)
    constraint = getattr(orig, "constraint_name", "") or ""

    if sqlstate == "23P01":  # exclusion_violation
        return ReservationOverlapError("같은 기간에 이미 확정된 예약이 있습니다.")
    if sqlstate == "23503":  # foreign_key_violation
        # 계층 복합FK 위반 = 다른 숙소 소속 객실/침대/채널을 참조한 경우
        if constraint.startswith("fk_reservations_"):
            return InvalidUnitHierarchyError(
                "지정한 객실/침대/채널이 이 숙소 소속이 아닙니다.",
                code="INVALID_UNIT_HIERARCHY",
            )
        return ResourceNotFoundError("참조 대상 리소스를 찾을 수 없습니다.")
    if sqlstate == "23514" and constraint == "ck_reservations_unit_shape":
        return InvalidUnitHierarchyError(
            "room_id/bed_id 조합이 올바르지 않습니다.", code="INVALID_UNIT_HIERARCHY"
        )
    return exc


async def create_reservation(
    db: AsyncSession, *, host_id: int, payload: ReservationCreateRequest
) -> Reservation:
    """예약 생성. 소유권 → 계층 → 겹침 순으로 막고 저장한다.

    ※ 예약이 CONFIRMED로 확정되면 CLEANING_TASKS를 PENDING으로 선제생성해야
      한다(state_events.md). 그 로직은 `cleaning_service`가 담당하며 아직
      구현 전이라 여기서 호출하지 않는다 — 구현 시 **이 함수의 트랜잭션
      안에서** 호출해 예약만 남고 청소작업이 빠지는 상태를 만들지 말 것.
    """
    prop = await get_owned_property(db, payload.property_id, host_id)

    # 검사와 삽입 사이를 다른 트랜잭션이 파고들지 못하게 먼저 잠근다.
    await lock_property_for_booking(db, prop.property_id)

    await validate_reservation_placement(
        db,
        prop=prop,
        room_id=payload.room_id,
        bed_id=payload.bed_id,
        check_in=payload.check_in,
        check_out=payload.check_out,
    )

    reservation = Reservation(**payload.model_dump())
    db.add(reservation)
    try:
        await db.flush()
    except IntegrityError as exc:
        await db.rollback()
        raise _translate_integrity_error(exc) from exc

    return reservation
