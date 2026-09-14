"""예약 서비스 — DB가 보장하지 못하는 두 가지를 애플리케이션이 책임진다.

명세서 4절 0번은 "DB가 보장하는 것"과 "애플리케이션이 보장하는 것"을 나눈다.
이 모듈은 후자를 구현한다:

1. **bookable_unit_type ↔ room_id/bed_id 교차 검증** (troubleshooting.md 2번)
   `bookable_unit_type`은 PROPERTIES에, `room_id`/`bed_id`는 RESERVATIONS에
   있어 PostgreSQL 일반 CHECK로는 검증할 수 없다(다른 테이블 참조 불가).
   DB CHECK는 같은 행 내부의 형태(3가지 유효 조합)만 본다.

2. **PROPERTY ↔ ROOM/BED 교차 기간 충돌 검사** (troubleshooting.md 1번)
   RESERVATIONS의 EXCLUDE 제약 3종(`excl_property_overlap` /
   `excl_room_overlap` / `excl_bed_overlap`)은 **같은 판매단위끼리만**
   겹침을 막는다. 독채(PROPERTY) 예약과 그 하위 객실(ROOM)/침대(BED)
   예약 사이의 충돌은 DB가 잡지 못하므로 예약 생성 트랜잭션에서 직접
   조회해 막는다.

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
    InvalidStatusTransitionError,
    InvalidUnitHierarchyError,
    ReservationOverlapError,
    ResourceNotFoundError,
)
from app.models.enums import (
    BookableUnitType,
    RefundStatus,
    ReservationStatus,
)
from app.models.property import Property
from app.models.reservation import Reservation
from app.schemas.reservation import (
    ReservationCreateRequest,
    ReservationStatusUpdateRequest,
)
from app.utils.db_errors import violates_constraint

# 겹침 판정 대상 상태. RESERVATIONS의 EXCLUDE 제약 3종
#   (`excl_property_overlap`/`excl_room_overlap`/`excl_bed_overlap`)의
#   WHERE절과 반드시 같은 집합이어야 한다
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


def units_collide(
    a_room_id: int | None,
    a_bed_id: int | None,
    b_room_id: int | None,
    b_bed_id: int | None,
) -> bool:
    """🔴 **판매단위 충돌 규칙의 원본.** 두 예약이 같은 자리를 점유하는가.

    아래 `_conflict_query`가 **이 함수를 SQL로 옮긴 것**이다. 규칙이
    두 곳에 생기므로 `tests/test_conflict_rule_parity.py`가 **같은
    데이터에 두 경로를 돌려 결과가 일치하는지** 고정한다 — 한쪽만
    고치면 그 테스트가 그 자리에서 터진다.

    | a | b | 충돌 | 왜 |
    |---|---|---|---|
    | 독채 | 무엇이든 | ✅ | 독채는 하위 전부를 점유한다 |
    | 객실 R | 독채 | ✅ | 대칭 |
    | 객실 R | 객실 R · 침대(R,*) | ✅ | 같은 객실 |
    | 객실 R1 | 객실 R2 | ❌ | 다른 객실 |
    | 침대(R,B) | 객실 R | ✅ | 객실 통째가 그 침대를 포함 |
    | 침대(R,B1) | 침대(R,B2) | ❌ | 다른 침대 |

    **대칭이다** — `units_collide(a, b) == units_collide(b, a)`.
    `_conflict_query`는 *"새 예약 vs 기존 예약"*의 비대칭 형태로
    쓰여 있지만 판정 결과는 같다(패리티 테스트가 확인한다).

    ⚠️ **기간과 상태는 보지 않는다.** 그 둘은 `dates_collide`와
    `ACTIVE_STATUSES`가 따로 본다 — 한 함수에 섞으면 어느 조건이
    걸렸는지 구분할 수 없다.
    """
    if a_room_id is None or b_room_id is None:
        return True                       # 한쪽이 독채면 무조건 겹친다
    if a_room_id != b_room_id:
        return False                      # 다른 객실
    return a_bed_id is None or b_bed_id is None or a_bed_id == b_bed_id


def dates_collide(
    a_check_in: date, a_check_out: date,
    b_check_in: date, b_check_out: date,
) -> bool:
    """기간 겹침 — **반개구간 `[in, out)`**.

    체크아웃일과 다음 체크인일이 같은 날인 **연박 이어짐은 겹침이
    아니다.** EXCLUDE 3종의 `tsrange`(하한 포함/상한 제외)와 같은
    판정이며, `_conflict_query`의 `date_overlap`을 옮긴 것이다.
    """
    return a_check_in < b_check_out and a_check_out > b_check_in


def reservations_collide(a, b) -> bool:
    """두 예약(ORM 객체 또는 같은 속성을 가진 것)이 충돌하는가.

    **셋을 모두 만족해야 충돌이다** — 단위 · 기간 · 둘 다 활성 상태.
    `is_conflict` 파생 필드가 이 함수를 쓴다(4.4절).

    ⚠️ `PENDING`은 활성이 아니다. `ACTIVE_STATUSES`가 `CONFIRMED`·
    `MODIFIED`뿐이라 **확정 전 예약이 겹치는 것은 `is_conflict`에
    잡히지 않는다** — 4.4절이 정한 범위다(비정상이 아니며, 확정
    시점에 EXCLUDE나 409가 막는다).
    """
    if a.reservation_status not in ACTIVE_STATUSES:
        return False
    if b.reservation_status not in ACTIVE_STATUSES:
        return False
    if not dates_collide(a.check_in, a.check_out, b.check_in, b.check_out):
        return False
    return units_collide(a.room_id, a.bed_id, b.room_id, b.bed_id)


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

    🔴 **이 함수는 위 `units_collide`·`dates_collide`의 SQL 표현이다.**
    규칙의 원본은 그 두 순수 함수이고 여기는 같은 판정을 DB에서 하는
    것뿐이다 — 새 예약을 넣기 전에는 메모리에 비교할 대상이 없어
    SQL이 필요하고, 목록 조회에서는 이미 읽어 온 행끼리 비교하는 쪽이
    N+1을 피한다. **한쪽만 고치면 `tests/test_conflict_rule_parity.py`가
    터진다.**

    기간 겹침은 반개구간 비교다(`기존.check_in < 신규.check_out` AND
    `기존.check_out > 신규.check_in`). 체크아웃일과 다음 체크인일이 같은 날인
    연박 이어짐은 겹침이 아니다 — 위 EXCLUDE 3종의 `tsrange`(하한 포함/상한 제외)와
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


def _overlap_unit_label(exc: IntegrityError) -> str:
    """[r49] EXCLUDE 3종 중 어느 것에 걸렸는지 사람이 읽을 말로 바꾼다.

    db_spec 2.6.1의 제약 이름과 1:1로 대응한다:
      `excl_property_overlap` / `excl_room_overlap` / `excl_bed_overlap`.
    이름을 못 읽으면 빈 문자열을 돌려 기존 문구를 그대로 쓴다 — 판별
    실패가 에러 번역 자체를 깨뜨리면 안 된다.
    """
    if violates_constraint(exc, "excl_property_overlap"):
        return "숙소 전체"
    if violates_constraint(exc, "excl_room_overlap"):
        return "객실"
    if violates_constraint(exc, "excl_bed_overlap"):
        return "침대"
    return ""


def _translate_integrity_error(exc: IntegrityError) -> Exception:
    """DB 제약 위반을 도메인 예외로 옮긴다(마지막 방어선).

    앱 검사를 통과한 뒤에도 동시성 때문에 RESERVATIONS의 EXCLUDE 3종
    (`excl_property_overlap`/`excl_room_overlap`/`excl_bed_overlap`)에
    걸릴 수 있고, 그때
    500을 그대로 내보내면 호스트에게 원인이 전달되지 않는다.

    ⚠️ 제약명 판정은 반드시 `violates_constraint()`를 쓴다. asyncpg에서는
    `exc.orig`에 `constraint_name` 속성이 아예 없어 직접 `getattr`로
    비교하면 **분기가 항상 거짓**이 된다(9/10 실측, troubleshooting 참고).
    """
    orig = exc.orig
    sqlstate = getattr(orig, "sqlstate", None) or getattr(orig, "pgcode", None)

    if sqlstate == "23P01":  # exclusion_violation
        # [r49] 어느 판매단위에서 걸렸는지를 제약 이름으로 구분한다.
        #   **예외 타입으로는 판별할 수 없다** — asyncpg의
        #   ExclusionViolationError는 SQLAlchemy가 자체 DBAPI 예외로
        #   번역하면서 사라지고 sqlstate만 남는다(9/10 실측,
        #   utils/db_errors.py 도크스트링). 그래서 제약 이름으로 본다.
        #   sqlstate 23P01은 EXCLUDE 위반에만 쓰이므로 이 분기에 들어온
        #   시점에 이미 겹침이 확정이고, 이름은 **어느 단위인지**만 더한다.
        unit = _overlap_unit_label(exc)
        #   판별에 실패하면(빈 문자열) 수식어 없이 **기존 문구 그대로** 나간다.
        #   f-string에 그대로 끼우면 공백이 두 칸 남는다.
        what = f"{unit} 예약" if unit else "예약"
        return ReservationOverlapError(f"같은 기간에 이미 확정된 {what}이 있습니다.")
    if sqlstate == "23503":  # foreign_key_violation
        # 계층 복합FK 위반 = 다른 숙소 소속 객실/침대/채널을 참조한 경우.
        #   RESERVATIONS의 복합FK 3종:
        #     fk_reservations_room_property    (room_id, property_id) -> rooms
        #     fk_reservations_bed_room         (bed_id, room_id)     -> beds
        #     fk_reservations_channel_property (channel_connection_id,
        #                                       property_id) -> channel_connections
        if violates_constraint(exc, "fk_reservations_"):
            return InvalidUnitHierarchyError(
                "지정한 객실/침대/채널이 이 숙소 소속이 아닙니다.",
                code="INVALID_UNIT_HIERARCHY",
            )
        return ResourceNotFoundError("참조 대상 리소스를 찾을 수 없습니다.")
    if sqlstate == "23514" and violates_constraint(exc, "ck_reservations_unit_shape"):
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

    🔴 **그날 이 작업의 등급이 2에서 1로 올라간다**(CLAUDE.md 작업 등급
      체계). 지금은 호스트가 **명시적으로 만든 행 하나**뿐이고 `PATCH`로
      되돌릴 수 있어 등급 2다. 청소 선제생성이 붙으면 **예약 하나가
      호스트가 요청하지 않은 행을 딸려 만들고**, 그것은 함수를 되돌려도
      되돌아가지 않는다 — `create_channel`의 요율 행 자동 생성이 등급 1인
      것과 같은 이유다. 착수 시 승인 3곳으로 간다.
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


# ══════════════════════════════════════════════════════════════════════════
# 조회·수정 (api_contract 4.3~4.6절)
# ══════════════════════════════════════════════════════════════════════════

# 🔴 허용 전이 — `docs/state_events.md` 1절 전이도가 원본이다.
#   PENDING --> CONFIRMED / CONFIRMED --> MODIFIED·CANCELLED·COMPLETED /
#   MODIFIED --> CONFIRMED / CANCELLED·COMPLETED는 종결.
#   COMPLETED는 checkout_time 배치가 전이시키는 것이 정상 경로이나 API로도
#   허용한다(4.6절).
_ALLOWED_TRANSITIONS: dict[ReservationStatus, frozenset[ReservationStatus]] = {
    ReservationStatus.PENDING: frozenset({ReservationStatus.CONFIRMED}),
    ReservationStatus.CONFIRMED: frozenset({
        ReservationStatus.MODIFIED,
        ReservationStatus.CANCELLED,
        ReservationStatus.COMPLETED,
    }),
    ReservationStatus.MODIFIED: frozenset({ReservationStatus.CONFIRMED}),
    ReservationStatus.CANCELLED: frozenset(),
    ReservationStatus.COMPLETED: frozenset(),
}


async def get_owned_reservation(
    db: AsyncSession, reservation_id: int, host_id: int
) -> Reservation:
    """`reservation_id`만으로 접근하는 경로의 IDOR 방어(단일 쿼리).

    api_contract **0절이 이 엔드포인트를 예시로 들어** 규칙을 적었다:

        SELECT r.* FROM reservations r
        JOIN properties p ON r.property_id = p.property_id
        WHERE r.reservation_id = :id AND p.host_id = :current_host_id

    부존재와 타인 소유를 **구분하지 않고** 둘 다 404다. 403을 쓰면 id를
    1씩 올려가며 어떤 id가 실재하는지 알아낼 수 있다.
    """
    stmt = (
        select(Reservation)
        .join(Property, Property.property_id == Reservation.property_id)
        .where(
            Reservation.reservation_id == reservation_id,
            Property.host_id == host_id,
        )
    )
    reservation = await db.scalar(stmt)
    if reservation is None:
        raise ResourceNotFoundError("요청한 예약을 찾을 수 없습니다.")
    return reservation


async def list_reservations(
    db: AsyncSession, *, property_id: int, host_id: int, start: date, end: date
) -> list[tuple[Reservation, bool]]:
    """기간에 걸치는 예약 + 각 건의 `is_conflict` (api_contract 4.3절).

    **기간 판정은 "겹치는 것 전부"다** — `check_in <= :end AND
    check_out > :start`. 그 달 안에서 시작하거나 끝나는 것뿐 아니라
    **달을 가로지르는 예약도 포함**해야 그리드에서 막대가 끊기지 않는다.

    🔴 **`is_conflict`를 메모리에서 계산한다.** 예약마다
    `find_conflicting_reservations`를 부르면 N+1 쿼리가 된다(30건이면
    31쿼리). 같은 숙소의 예약은 이미 전부 읽어 왔으므로 쌍끼리 비교하면
    쿼리가 한 번이다.

    ⚠️ **그 대신 판정 규칙이 SQL과 파이썬 두 곳에 생긴다.** 규칙의 원본은
    `units_collide`·`dates_collide`이고 `_conflict_query`가 그것의 SQL
    표현이며, `tests/test_conflict_rule_parity.py`가 두 경로의 답이 같은지
    고정한다.

    ⚠️ **기간 밖 예약과의 충돌은 보지 않는다.** 조회 구간에 걸치지 않는
    예약은 애초에 읽어 오지 않았기 때문이다. 캘린더가 그 기간을 그리는
    것이 목적이므로 화면에 보이는 범위에서 판정하면 된다 — 구간을 넓히면
    다음 달 예약과의 충돌도 잡힌다.
    """
    await get_owned_property(db, property_id, host_id)

    stmt = (
        select(Reservation)
        .where(
            Reservation.property_id == property_id,
            Reservation.check_in <= end,
            Reservation.check_out > start,
        )
        .order_by(Reservation.check_in, Reservation.reservation_id)
    )
    rows = list((await db.scalars(stmt)).all())

    out: list[tuple[Reservation, bool]] = []
    for i, r in enumerate(rows):
        conflict = any(
            reservations_collide(r, other)
            for j, other in enumerate(rows)
            if i != j
        )
        out.append((r, conflict))
    return out


async def is_conflicting(db: AsyncSession, reservation: Reservation) -> bool:
    """단건의 `is_conflict` (api_contract 4.4절).

    목록과 달리 **SQL 경로를 쓴다** — 비교 대상이 메모리에 없고, 한 건이라
    N+1이 생기지 않는다. `exclude_reservation_id`로 자기 자신을 뺀다.

    `reservation_status`가 활성(`CONFIRMED`·`MODIFIED`)이 아니면 애초에
    충돌 대상이 아니므로 조회하지 않는다 — `reservations_collide`의 첫
    분기와 같은 판정이다.
    """
    if reservation.reservation_status not in ACTIVE_STATUSES:
        return False
    conflicts = await find_conflicting_reservations(
        db,
        property_id=reservation.property_id,
        room_id=reservation.room_id,
        bed_id=reservation.bed_id,
        check_in=reservation.check_in,
        check_out=reservation.check_out,
        exclude_reservation_id=reservation.reservation_id,
    )
    return bool(conflicts)


def _validate_status_change(
    current: Reservation, payload: "ReservationStatusUpdateRequest"
) -> None:
    """허용 전이와 무의미한 조합을 막는다 (api_contract 4.6절).

    **같은 값을 다시 보내는 것은 전이가 아니다** — 통과시킨다. `PATCH`가
    멱등이어야 재시도가 안전하다.

    무의미한 조합은 4.6절이 든 예 하나다 — `CANCELLED`로 바꾸면서
    `refund_status`가 `NONE`이면 거부한다. **취소했는데 환불 상태가
    "없음"이면 돈이 어떻게 됐는지 기록이 남지 않는다.**
    """
    new_status = payload.reservation_status
    if new_status is not None and new_status != current.reservation_status:
        allowed = _ALLOWED_TRANSITIONS.get(current.reservation_status, frozenset())
        if new_status not in allowed:
            raise InvalidStatusTransitionError(
                f"{current.reservation_status.value} → {new_status.value} 전이는 "
                f"허용되지 않습니다. 허용: "
                f"{', '.join(sorted(s.value for s in allowed)) or '없음(종결 상태)'}"
            )

    # 조합 판정은 **요청 적용 후의 상태**로 본다.
    final_status = new_status or current.reservation_status
    final_refund = payload.refund_status or current.refund_status
    if (
        final_status is ReservationStatus.CANCELLED
        and final_refund is RefundStatus.NONE
    ):
        raise InvalidStatusTransitionError(
            "예약을 취소하면서 refund_status를 NONE으로 둘 수 없습니다. "
            "PARTIAL 또는 FULL을 함께 보내십시오."
        )


async def update_reservation_status(
    db: AsyncSession,
    *,
    reservation_id: int,
    host_id: int,
    payload: "ReservationStatusUpdateRequest",
) -> Reservation:
    """예약 상태 변경 (api_contract 4.6절). 응답은 갱신 후 전체 상태다.

    **판정 순서** — 소유권(404) → 전이 규칙(400). `update_property`와 같은
    순서이며, 반대로 하면 남의 예약에 대해서도 400이 나가 *"그 id는
    존재한다"*가 새어 나간다.

    **보낸 필드만 바꾼다.** `model_fields_set`으로 판정한다 — 세 필드가
    모두 Optional이라 `None`인 것과 보내지 않은 것을 값으로는 구분할 수
    없다. 빈 본문이면 아무것도 세팅하지 않고 현재 상태를 돌려준다.
    """
    reservation = await get_owned_reservation(db, reservation_id, host_id)
    _validate_status_change(reservation, payload)

    changed = False
    for field in payload.model_fields_set:
        value = getattr(payload, field)
        if value is not None:
            setattr(reservation, field, value)
            changed = True

    if changed:
        await db.flush()
        # 🔴 **생성 컬럼은 UPDATE 뒤 만료된다.** `net_amount`는
        #   `GENERATED ALWAYS AS (gross_amount - fee_amount) STORED`라
        #   SQLAlchemy가 UPDATE 후 값을 신뢰하지 않고 만료시킨다 —
        #   INSERT는 RETURNING으로 받아오지만 UPDATE는 그렇지 않다.
        #   그 상태로 `r.net_amount`를 읽으면 지연로딩(동기 IO)이 걸려
        #   async 컨텍스트에서 MissingGreenlet이 난다(9/14 실측).
        #   `expire_on_commit=False`로도 막히지 않는다 — 만료 시점이
        #   커밋이 아니라 **flush**이기 때문이다.
        await db.refresh(reservation)

    return reservation
