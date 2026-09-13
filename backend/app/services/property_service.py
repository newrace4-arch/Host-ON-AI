"""숙소·객실·침대 비즈니스 로직 (api_contract.md 2절).

## 소유권은 조회 조건에 묶는다

파이썬 `if`로 나중에 검사하지 않는다(0절). 부존재와 타인 소유를 **구분하지
않고** 둘 다 `404 RESOURCE_NOT_FOUND`다 — 403을 쓰면 id를 1씩 올려가며 어떤
id가 실재하는지 알아낼 수 있다(CLAUDE.md 코딩규칙 1).

숙소 경로는 `reservation_service.get_owned_property`를 그대로 쓴다. 이미
`channel_service`도 그것을 쓰고 있어 소유권 판정이 한 곳에 모인다.

`room_id`만 있는 경로(`GET /rooms/{id}/beds`)에는 그런 함수가 없어 여기서
`get_owned_room`을 만든다 — `channel_service.get_owned_connection`이 같은
모양의 선례다.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    BedLabelAlreadyExistsError,
    ImmutableFieldError,
    InvalidUnitHierarchyError,
    ResourceNotFoundError,
    RoomNameAlreadyExistsError,
)
from app.models.enums import BookableUnitType
from app.models.property import Bed, Property, Room
from app.schemas.property import (
    BedCreateRequest,
    PropertyCreateRequest,
    PropertyUpdateRequest,
    RoomCreateRequest,
)
from app.services.reservation_service import get_owned_property
from app.utils.db_errors import violates_constraint


async def list_properties(db: AsyncSession, *, host_id: int) -> list[Property]:
    """내 숙소 전체(api_contract 2절 `GET /properties`).

    **페이지네이션하지 않는다.** 0절 규약상 `meta`는 `page`·`size`를
    지원하는 컬렉션에만 붙는데, 이 응답은 `PropertySwitcher` 드롭다운과
    대시보드 병렬 호출의 **입력**이라 항상 전체가 필요하다. 일부만 받으면
    존재하는 숙소가 드롭다운에서 누락된다(2절).

    숙소가 0건이면 빈 리스트다 — 신규 가입 직후의 정상 상태이며 404가
    아니다. 온보딩으로 유도하는 것은 화면의 몫이다.
    """
    stmt = (
        select(Property)
        .where(Property.host_id == host_id)
        .order_by(Property.property_id)
    )
    return list((await db.scalars(stmt)).all())


async def get_property_detail(
    db: AsyncSession, *, property_id: int, host_id: int
) -> Property:
    """숙소 상세(api_contract 2.4절). 없거나 타인 소유면 404."""
    return await get_owned_property(db, property_id, host_id)


async def get_owned_room(db: AsyncSession, room_id: int, host_id: int) -> Room:
    """`room_id`만으로 접근하는 경로의 IDOR 방어(단일 쿼리).

    api_contract 2.2절이 적어 둔 조인 그대로다:

        SELECT r.* FROM rooms r
        JOIN properties p ON r.property_id = p.property_id
        WHERE r.room_id = :room_id AND p.host_id = :current_host_id

    ⚠️ **빈 배열과 404를 혼동하지 않는다**(2.2절). 내 소유 객실인데 침대가
    없으면 `200 + []`이고, 남의 객실이거나 없는 객실이면 `404`다. 그
    구분을 만드는 것이 바로 이 함수다 — 객실을 먼저 확인하지 않고 침대만
    조회하면 두 경우가 **똑같이 빈 배열**이 되어 남의 객실 id를 넣어도
    200이 나간다.
    """
    stmt = (
        select(Room)
        .join(Property, Property.property_id == Room.property_id)
        .where(Room.room_id == room_id, Property.host_id == host_id)
    )
    room = await db.scalar(stmt)
    if room is None:
        raise ResourceNotFoundError("요청한 객실을 찾을 수 없습니다.")
    return room


async def list_rooms(
    db: AsyncSession, *, property_id: int, host_id: int
) -> list[Room]:
    """객실 목록(api_contract 2.1절).

    🔴 **`bookable_unit_type`이 `PROPERTY`인 숙소에서 빈 배열은 정상이다.**
    404가 아니고, 화면이 등록을 유도하는 `EmptyState`를 띄워서도 안 된다 —
    데이터가 없는 것이 아니라 **그 숙소에 객실 개념이 없는 것**이다(2.1절).
    그래서 이 함수는 판매단위를 보지 않는다. 조회는 모든 숙소에 대해
    성립하며, *만드는* 쪽만 판매단위로 거른다(2.6절).

    **정렬은 `room_id`다.** `room_name`으로 정렬하면 "101호 · 102호 · 201호"가
    문자열 비교로 뒤섞이는 자리가 생기고(예: "10호" < "9호"), 등록 순서가
    곧 호스트가 기억하는 순서다.
    """
    await get_owned_property(db, property_id, host_id)
    stmt = (
        select(Room)
        .where(Room.property_id == property_id)
        .order_by(Room.room_id)
    )
    return list((await db.scalars(stmt)).all())


async def list_beds(db: AsyncSession, *, room_id: int, host_id: int) -> list[Bed]:
    """침대 목록(api_contract 2.2절).

    `ROOM` 단위 숙소의 객실은 침대를 나누어 팔지 않으므로 빈 배열이
    정상이다(2.2절) — `list_rooms`와 같은 이유로 판매단위를 보지 않는다.
    """
    await get_owned_room(db, room_id, host_id)
    stmt = select(Bed).where(Bed.room_id == room_id).order_by(Bed.bed_id)
    return list((await db.scalars(stmt)).all())


# `PATCH`가 거부하는 필드. **값이 아니라 존재 여부**로 판정한다(2.5절).
#   두 값은 바꾸는 순간 이미 쌓인 데이터가 어긋난다 —
#   `accommodation_type`은 10절 컴플라이언스 체크리스트 항목이 여기서
#   파생되고, `bookable_unit_type`은 4절 400 3종의 판정 기준이라
#   PROPERTY → ROOM으로 바꾸면 과거 예약이 전부 규칙 위반 상태가 된다.
_IMMUTABLE_FIELDS = ("accommodation_type", "bookable_unit_type")


async def create_property(
    db: AsyncSession, *, host_id: int, payload: PropertyCreateRequest
) -> Property:
    """숙소 등록(api_contract 2.3절). 응답은 **상세와 같은 11필드**다.

    **소유자는 JWT에서 온다** — 요청 본문의 `host_id`를 쓰지 않는다.

    ⚠️ **보내지 않은 필드를 `None`으로 넣지 않는다.** `base_price`·
    `checkin_time`·`checkout_time`·두 스위치는 `NOT NULL DEFAULT`가 걸려
    있어, `None`을 명시적으로 실어 보내면 **DB 기본값이 적용되지 않고
    NOT NULL 위반**이 난다. 그래서 `model_fields_set`에 있는 것만 세팅하고
    나머지는 컬럼을 아예 INSERT에서 빼 서버 기본값이 채우게 둔다.

    그 결과가 2.3절이 적은 등록 직후 상태다 — `base_price` `0`(= **미설정**,
    "0원"이 아니다), `checkin_time` `"15:00"`, `checkout_time` `"11:00"`,
    두 스위치 `true`, `address`·`lower_bound_price`는 `null`.
    """
    prop = Property(
        host_id=host_id,
        name=payload.name,
        accommodation_type=payload.accommodation_type,
        bookable_unit_type=payload.bookable_unit_type,
    )
    for field in (
        "address",
        "base_price",
        "lower_bound_price",
        "checkin_time",
        "checkout_time",
        "weekday_adjustment_enabled",
        "holiday_adjustment_enabled",
    ):
        if field in payload.model_fields_set:
            setattr(prop, field, getattr(payload, field))

    db.add(prop)
    await db.flush()
    # 서버 기본값(base_price 0, checkin_time 15:00 ...)은 INSERT 뒤에야
    #   값이 생긴다. 응답이 11필드 전부를 담아야 하므로 여기서 읽어 온다.
    await db.refresh(prop)
    return prop


async def update_property(
    db: AsyncSession,
    *,
    property_id: int,
    host_id: int,
    payload: PropertyUpdateRequest,
) -> Property:
    """숙소 수정(api_contract 2.5절). 응답은 갱신 후 **전체 11필드**다.

    **판정 순서가 뒤바뀌면 안 된다** — 소유권(404)을 먼저 보고, 통과한
    뒤에만 수정 불가 필드(400)를 본다. 9/13 `room_id` 404/400 분리에서
    정한 것과 같은 순서다. 반대로 하면 남의 숙소에 대해서도 `400`이 나가
    *"그 id는 존재한다"*는 사실이 새어 나간다.

    🔴 **`accommodation_type`·`bookable_unit_type`은 무시하지 않고 거부한다**
    (2.5절). 받아서 조용히 버리면 호스트는 바뀐 줄 알고 화면을 떠난다.
    판정은 **값이 아니라 존재 여부**다 — `null`을 보내도 "바꾸려 했다"로
    본다. 요청 스키마가 그 둘을 `Any`로 두고 있어 어떤 값이 와도 여기까지
    온다(schemas/property.py 참고).

    **빈 본문(`{})`은 에러가 아니다.** 2.5절이 *"바꿀 것이 없다는 뜻이므로
    현재 상태를 그대로 `200`으로 돌려준다"*고 정했다 — 우리가 고를 문제가
    아니라 스펙이 확정한 동작이다. `model_fields_set`이 비면 아무것도
    세팅하지 않고 조회 결과를 그대로 반환한다.

    **보낸 필드만 바꾼다.** `None`인 것과 보내지 않은 것을 구분해야 하므로
    `model_fields_set`으로 판정한다 — `address: null`은 *"지운다"*이고
    `address` 미전송은 *"그대로 둔다"*라 뜻이 정반대다(2.5절).
    """
    prop = await get_owned_property(db, property_id, host_id)

    blocked = [f for f in _IMMUTABLE_FIELDS if f in payload.model_fields_set]
    if blocked:
        raise ImmutableFieldError(
            f"다음 필드는 수정할 수 없습니다: {', '.join(blocked)}. "
            "숙박업 유형과 판매단위를 바꾸려면 숙소를 새로 등록해야 합니다."
        )

    for field in payload.model_fields_set - set(_IMMUTABLE_FIELDS):
        setattr(prop, field, getattr(payload, field))

    await db.flush()
    return prop


# ══════════════════════════════════════════════════════════════════════════
# 객실·침대 생성 (api_contract 2.6절)
# ══════════════════════════════════════════════════════════════════════════


def _validate_unit_for_room_creation(prop: Property) -> None:
    """[2.6절] **이 숙소에 객실이라는 것이 존재할 수 있는가**만 본다.

    `bookable_unit_type`이 `ROOM`·`BED`면 통과, `PROPERTY`면
    `400 INVALID_UNIT_HIERARCHY`다. 2.1절이 *"`PROPERTY` 숙소의 객실 목록이
    빈 배열인 것이 정상"*이라고 정한 것의 **짝**이다 — 만들 수 있게 두면
    조회는 계속 빈 배열을 기대하는데 DB에는 행이 쌓인다.

    ## 🔴 이름이 비슷한 함수가 셋이다. 합치지 마라

    | 함수 | 쓰는 곳 | 묻는 것 | `room_id` |
    |---|---|---|---|
    | `reservation_service.validate_unit_hierarchy` | 예약 생성 | 이 **예약의** room/bed 조합이 판매단위와 맞나 | `ROOM` 숙소에서 **필수** |
    | `channel_service._validate_room_for_channel` | 채널 연결 | 이 **피드에 건 객실**이 내 숙소 것이고 걸 수 있나 | **선택**(숙소 전체 피드 허용) |
    | `_validate_unit_for_room_creation`(이 함수) | 객실 생성 | 이 **숙소에** 객실이 존재할 수 있나 | **인자에 없다** — 아직 만들지 않았다 |

    **`validate_unit_hierarchy`를 여기에 쓰면 그 자리에서 틀린다.** `ROOM`
    단위 숙소에 객실을 만들 때 넘길 `room_id`가 없어 `None`이 되는데, 그
    함수는 그것을 **`ROOM_ID_REQUIRED` 400**으로 거부한다 — **정상 요청이
    막힌다.** 2.6절 표는 그 칸이 ✅다.

    `_validate_room_for_channel`도 맞지 않는다. 그쪽은 **이미 존재하는**
    객실을 검사하는 함수이고 DB 조회가 들어 있다.

    셋 다 *"계층 검증"*이라는 같은 말로 불릴 수 있어 **다음에 누가 합치려
    한다.** 뜻이 다르다는 것을 여기 남긴다(2026-09-13에 이 함정을 세 번
    만났다 — devlog 3절).

    :raises InvalidUnitHierarchyError: 400 `INVALID_UNIT_HIERARCHY`.
    """
    if prop.bookable_unit_type is BookableUnitType.PROPERTY:
        raise InvalidUnitHierarchyError(
            "이 숙소는 전체(PROPERTY) 단위로 판매합니다. 객실을 등록할 수 없습니다.",
            code="INVALID_UNIT_HIERARCHY",
        )


def _validate_unit_for_bed_creation(prop: Property) -> None:
    """[2.6절] 침대는 **`BED` 단위 숙소에서만** 만들 수 있다.

    `ROOM` 단위 숙소도 거부한다 — 객실을 침대로 나누어 팔지 않으므로 그
    객실의 침대 목록이 빈 배열인 것이 정상이다(2.2절). 위
    `_validate_unit_for_room_creation`과 **통과 조건이 다르다**(그쪽은
    `ROOM`도 통과) — 2.6절 표의 두 열이 갈리는 지점이라 함수를 나눴다.

    같은 코드(`INVALID_UNIT_HIERARCHY`)를 쓴다. 2.6절이 *"4절이 예약
    생성에서 쓰는 것과 같은 코드를 재사용한다 … 새 코드를 만들면 프론트가
    같은 상황을 두 코드로 처리하게 된다"*고 정했다 — **재사용하는 것은
    코드 문자열이지 함수가 아니다.**
    """
    if prop.bookable_unit_type is not BookableUnitType.BED:
        raise InvalidUnitHierarchyError(
            "이 숙소는 침대(BED) 단위로 판매하지 않습니다. 침대를 등록할 수 없습니다.",
            code="INVALID_UNIT_HIERARCHY",
        )


async def _get_owned_room_and_property(
    db: AsyncSession, room_id: int, host_id: int
) -> tuple[Room, Property]:
    """객실과 **그 상위 숙소**를 한 쿼리로 가져온다(소유권 포함).

    `get_owned_room`과 조건이 같지만 `Property`도 함께 돌려준다. 침대 생성은
    판매단위를 봐야 하는데, `room.property`로 따라가면 **지연로딩(동기 IO)**이
    걸려 async 컨텍스트에서 `MissingGreenlet`이 난다.
    """
    stmt = (
        select(Room, Property)
        .join(Property, Property.property_id == Room.property_id)
        .where(Room.room_id == room_id, Property.host_id == host_id)
    )
    row = (await db.execute(stmt)).first()
    if row is None:
        raise ResourceNotFoundError("요청한 객실을 찾을 수 없습니다.")
    return row[0], row[1]


async def create_room(
    db: AsyncSession, *, property_id: int, host_id: int, payload: RoomCreateRequest
) -> Room:
    """객실 등록(api_contract 2.6절). **201**, 응답은 2.1절 목록의 원소와 동형.

    판정 순서는 **소유권(404) → 판매단위(400) → UNIQUE(409)**다. 앞의 둘은
    `update_property`와 같은 이유로 이 순서여야 한다(400이 먼저 나가면 남의
    숙소에 대해서도 400이 나가 존재가 샌다).

    🔴 **409는 선조회로 막지 않는다.** 이름이 비어 있는지 먼저 확인하고
    INSERT하면 그 사이에 다른 요청이 같은 이름을 넣을 수 있다(TOCTOU).
    2.6절이 *"선조회로 미리 막지 않는 이유는 그 사이 다른 요청이 끼어들 수
    있어서다"*라고 명시했다. DB 제약이 판정하고 우리는 **번역만** 한다.
    """
    prop = await get_owned_property(db, property_id, host_id)
    _validate_unit_for_room_creation(prop)

    room = Room(
        property_id=property_id,
        room_name=payload.room_name,
        capacity=payload.capacity,
    )
    db.add(room)
    try:
        await db.flush()
    except IntegrityError as exc:
        await db.rollback()
        # ⚠️ **제약 이름 전체로 판정한다.** `uq_room_`을 접두사로 쓰면
        #   `uq_room_property_ref`(복합 FK 참조용 후보키)까지 함께 걸린다.
        if violates_constraint(exc, "uq_property_room_name"):
            raise RoomNameAlreadyExistsError(
                f"이미 같은 이름의 객실이 있습니다: {payload.room_name}"
            ) from exc
        raise
    return room


async def create_bed(
    db: AsyncSession, *, room_id: int, host_id: int, payload: BedCreateRequest
) -> Bed:
    """침대 등록(api_contract 2.6절). **201**, 응답은 2.2절 목록의 원소와 동형.

    **경로에 `property_id`가 없다.** 객실에서 숙소를 역추적해 소유권을 본다 —
    `GET /rooms/{id}/beds`와 같은 조인이다(2.6절 말미 SQL). 이것을 빠뜨리면
    남의 객실에 침대를 만들 수 있다.
    """
    room, prop = await _get_owned_room_and_property(db, room_id, host_id)
    _validate_unit_for_bed_creation(prop)

    bed = Bed(room_id=room.room_id, bed_label=payload.bed_label)
    db.add(bed)
    try:
        await db.flush()
    except IntegrityError as exc:
        await db.rollback()
        if violates_constraint(exc, "uq_room_bed_label"):
            raise BedLabelAlreadyExistsError(
                f"이미 같은 라벨의 침대가 있습니다: {payload.bed_label}"
            ) from exc
        raise
    return bed
