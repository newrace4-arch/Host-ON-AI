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
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ResourceNotFoundError
from app.models.property import Bed, Property, Room
from app.services.reservation_service import get_owned_property


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
