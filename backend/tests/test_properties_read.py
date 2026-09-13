"""숙소·객실·침대 조회 API 회귀 테스트 (api_contract.md 2절·2.1·2.2·2.4).

세 가지를 고정한다.

1. **목록 4필드 / 상세 11필드가 다르다는 것** — 2.3절이 *"클라이언트 타입을
   하나로 쓰지 않는다"*고 못박은 그 차이다. 한쪽을 다른 쪽으로 바꾸면
   온보딩 화면이나 드롭다운 중 하나가 깨진다.
2. **빈 배열과 404의 구분** — `PROPERTY` 단위 숙소의 객실 0건은 **정상**이고
   (2.1절), 남의 객실 id는 404다(2.2절). 이 둘이 뭉개지면 IDOR이 된다.
3. **IDOR 방어** — 타인 소유는 403이 아니라 404다(0절).
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ResourceNotFoundError
from app.models.enums import AccommodationType, BookableUnitType
from app.models.host import Host
from app.models.property import Bed, Property, Room
from app.schemas.property import (
    BedResponse,
    PropertyDetailResponse,
    PropertySummaryResponse,
    RoomResponse,
)
from app.services import property_service

pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# 지역 헬퍼 — conftest는 고치지 않는다
# ---------------------------------------------------------------------------


async def _other_host(db: AsyncSession) -> Host:
    """남의 계정. IDOR 테스트는 **실재하는 타인**이 있어야 의미가 있다."""
    other = Host(
        email=f"other-{uuid.uuid4().hex[:12]}@test.local",
        password_hash="not-a-real-hash",
        name="다른호스트",
    )
    db.add(other)
    await db.commit()
    await db.refresh(other)
    return other


async def _bare_property(
    db: AsyncSession, host_id: int, *, unit: BookableUnitType
) -> Property:
    """`make_property`와 달리 **채널 연결을 만들지 않는** 최소 숙소."""
    prop = Property(
        host_id=host_id,
        name="테스트숙소",
        accommodation_type=AccommodationType.URBAN_HOMESTAY,
        bookable_unit_type=unit,
    )
    db.add(prop)
    await db.commit()
    await db.refresh(prop)
    return prop


# ---------------------------------------------------------------------------
# 1. 목록 4필드 / 상세 11필드
# ---------------------------------------------------------------------------


async def test_summary_has_exactly_four_fields(db: AsyncSession, host):
    """🔴 목록은 **4필드**다(2절).

    7필드를 뺀 것은 실수가 아니라 *"`/settings` 화면 소관이며 드롭다운에는
    쓰이지 않는다"*는 판단이다. 늘어나면 `PropertySwitcher`가 쓰지도 않는
    값을 숙소 수만큼 받게 된다.
    """
    prop = await _bare_property(db, host.host_id, unit=BookableUnitType.PROPERTY)
    body = PropertySummaryResponse.model_validate(prop).model_dump()

    assert set(body) == {
        "property_id",
        "name",
        "accommodation_type",
        "bookable_unit_type",
    }


async def test_detail_has_exactly_eleven_fields(db: AsyncSession, host):
    """상세는 **11필드**이고 `host_id`·`created_at`은 없다(2.3·2.4절).

    `host_id`를 내보내면 다른 호스트의 id 공간을 추론할 단서가 된다.
    """
    prop = await _bare_property(db, host.host_id, unit=BookableUnitType.PROPERTY)
    body = PropertyDetailResponse.model_validate(prop).model_dump()

    assert set(body) == {
        "property_id",
        "name",
        "accommodation_type",
        "bookable_unit_type",
        "address",
        "base_price",
        "lower_bound_price",
        "checkin_time",
        "checkout_time",
        "weekday_adjustment_enabled",
        "holiday_adjustment_enabled",
    }
    assert "host_id" not in body
    assert "created_at" not in body


async def test_detail_serializes_time_as_hhmm(db: AsyncSession, host):
    """`TIME`은 **`"HH:MM"`**이다 — Pydantic 기본값(`"15:00:00"`)이 아니다.

    2절 요청 예시가 `"checkin_time": "15:00"`이므로 응답도 같아야 화면이
    받은 값을 그대로 폼에 되돌려 넣을 수 있다.
    """
    prop = await _bare_property(db, host.host_id, unit=BookableUnitType.PROPERTY)
    body = PropertyDetailResponse.model_validate(prop).model_dump()

    assert body["checkin_time"] == "15:00"
    assert body["checkout_time"] == "11:00"


async def test_new_property_defaults_mean_unset(db: AsyncSession, host):
    """등록 직후 `base_price`는 `0`(= **미설정**)이고 nullable 둘은 `null`이다.

    2.3절: *"`0`은 '미설정'이지 '0원'이 아니다."* 화면은 이 상태를 0원
    예약처럼 보여주면 안 된다.
    """
    prop = await _bare_property(db, host.host_id, unit=BookableUnitType.PROPERTY)
    body = PropertyDetailResponse.model_validate(prop).model_dump()

    assert body["base_price"] == 0
    assert body["lower_bound_price"] is None
    assert body["address"] is None
    assert body["weekday_adjustment_enabled"] is True
    assert body["holiday_adjustment_enabled"] is True


# ---------------------------------------------------------------------------
# 2. 목록 조회
# ---------------------------------------------------------------------------


async def test_list_properties_returns_only_my_properties(db: AsyncSession, host):
    """남의 숙소는 목록에 섞이지 않는다."""
    mine = await _bare_property(db, host.host_id, unit=BookableUnitType.PROPERTY)
    other = await _other_host(db)
    await _bare_property(db, other.host_id, unit=BookableUnitType.PROPERTY)

    props = await property_service.list_properties(db, host_id=host.host_id)

    assert [p.property_id for p in props] == [mine.property_id]


async def test_list_properties_empty_is_not_an_error(db: AsyncSession, host):
    """숙소 0건은 **정상**이다 — 가입 직후의 상태이며 404가 아니다."""
    assert await property_service.list_properties(db, host_id=host.host_id) == []


# ---------------------------------------------------------------------------
# 3. 상세 조회 — IDOR
# ---------------------------------------------------------------------------


async def test_detail_of_other_host_property_is_404(db: AsyncSession, host):
    """🔴 남의 숙소는 **403이 아니라 404**다(0절).

    403을 쓰면 id를 1씩 올려가며 어떤 id가 실재하는지 알아낼 수 있다.
    """
    other = await _other_host(db)
    theirs = await _bare_property(db, other.host_id, unit=BookableUnitType.PROPERTY)

    with pytest.raises(ResourceNotFoundError):
        await property_service.get_property_detail(
            db, property_id=theirs.property_id, host_id=host.host_id
        )


async def test_detail_of_missing_property_is_404(db: AsyncSession, host):
    """없는 숙소도 같은 404다 — 위 테스트와 **응답이 구분되지 않아야** 한다."""
    with pytest.raises(ResourceNotFoundError):
        await property_service.get_property_detail(
            db, property_id=99_999_999, host_id=host.host_id
        )


# ---------------------------------------------------------------------------
# 4. 객실 목록 — 빈 배열이 정상인 자리
# ---------------------------------------------------------------------------


async def test_rooms_of_property_unit_is_empty_not_404(db: AsyncSession, host):
    """🔴 `PROPERTY` 단위 숙소의 객실 0건은 **정상**이다(2.1절).

    데이터가 없는 것이 아니라 **그 숙소에 객실 개념이 없는 것**이라, 404도
    아니고 등록을 유도하는 `EmptyState`를 띄울 자리도 아니다.
    """
    prop = await _bare_property(db, host.host_id, unit=BookableUnitType.PROPERTY)

    assert (
        await property_service.list_rooms(
            db, property_id=prop.property_id, host_id=host.host_id
        )
        == []
    )


async def test_rooms_are_ordered_by_id(db: AsyncSession, host):
    """정렬은 `room_id`(등록 순)다 — `room_name` 문자열 정렬이 아니다.

    이름으로 정렬하면 `"10호" < "9호"`처럼 사람이 기대하지 않는 순서가
    나온다.
    """
    prop = await _bare_property(db, host.host_id, unit=BookableUnitType.ROOM)
    for name in ("9호", "10호", "101호"):
        db.add(Room(property_id=prop.property_id, room_name=name))
    await db.commit()

    rooms = await property_service.list_rooms(
        db, property_id=prop.property_id, host_id=host.host_id
    )

    assert [r.room_name for r in rooms] == ["9호", "10호", "101호"]
    assert [r.room_id for r in rooms] == sorted(r.room_id for r in rooms)


async def test_rooms_of_other_host_property_is_404(db: AsyncSession, host):
    """남의 숙소 객실 목록은 빈 배열이 아니라 404다."""
    other = await _other_host(db)
    theirs = await _bare_property(db, other.host_id, unit=BookableUnitType.ROOM)
    db.add(Room(property_id=theirs.property_id, room_name="101호"))
    await db.commit()

    with pytest.raises(ResourceNotFoundError):
        await property_service.list_rooms(
            db, property_id=theirs.property_id, host_id=host.host_id
        )


async def test_room_response_keeps_capacity_null(db: AsyncSession, host):
    """`capacity`의 `null`은 **미입력**이며 `0`으로 바뀌지 않는다(2.1절)."""
    prop = await _bare_property(db, host.host_id, unit=BookableUnitType.ROOM)
    db.add(Room(property_id=prop.property_id, room_name="201호"))
    await db.commit()

    rooms = await property_service.list_rooms(
        db, property_id=prop.property_id, host_id=host.host_id
    )
    body = RoomResponse.model_validate(rooms[0]).model_dump()

    assert body == {"room_id": rooms[0].room_id, "room_name": "201호", "capacity": None}
    # `0`으로 대체되지 않는다 — 미입력과 "정원 0명"은 다른 뜻이다
    assert body["capacity"] != 0


# ---------------------------------------------------------------------------
# 5. 침대 목록 — 빈 배열 200 vs 404
# ---------------------------------------------------------------------------


async def test_beds_of_my_room_without_beds_is_empty(db: AsyncSession, host):
    """내 객실인데 침대가 없으면 `200 + []`다(2.2절)."""
    prop = await _bare_property(db, host.host_id, unit=BookableUnitType.ROOM)
    room = Room(property_id=prop.property_id, room_name="101호")
    db.add(room)
    await db.commit()
    await db.refresh(room)

    assert (
        await property_service.list_beds(db, room_id=room.room_id, host_id=host.host_id)
        == []
    )


async def test_beds_of_other_host_room_is_404(db: AsyncSession, host):
    """🔴 남의 객실은 **빈 배열이 아니라 404**다(2.2절).

    이것이 이 테스트 파일에서 가장 중요한 한 건이다. 객실 소유권을 먼저
    확인하지 않고 `WHERE bed_id.room_id = :room_id`로 침대만 조회하면 남의
    객실 id를 넣어도 **똑같이 빈 배열**이 나가 두 경우를 구분할 수 없게
    된다 — 그 순간 이 엔드포인트는 남의 객실 id 공간을 탐색하는 도구가
    된다.
    """
    other = await _other_host(db)
    theirs = await _bare_property(db, other.host_id, unit=BookableUnitType.BED)
    room = Room(property_id=theirs.property_id, room_name="도미토리")
    db.add(room)
    await db.commit()
    await db.refresh(room)

    with pytest.raises(ResourceNotFoundError):
        await property_service.list_beds(
            db, room_id=room.room_id, host_id=host.host_id
        )


async def test_beds_of_missing_room_is_404(db: AsyncSession, host):
    """없는 객실도 같은 404다 — 위와 응답이 구분되지 않아야 한다."""
    with pytest.raises(ResourceNotFoundError):
        await property_service.list_beds(
            db, room_id=99_999_999, host_id=host.host_id
        )


async def test_bed_response_shape(db: AsyncSession, host):
    """침대 응답은 **2필드**다 — `room_id`·`created_at`은 넣지 않는다(2.2절)."""
    prop = await _bare_property(db, host.host_id, unit=BookableUnitType.BED)
    room = Room(property_id=prop.property_id, room_name="도미토리")
    db.add(room)
    await db.commit()
    await db.refresh(room)
    db.add_all([Bed(room_id=room.room_id, bed_label="A"), Bed(room_id=room.room_id, bed_label="B")])
    await db.commit()

    beds = await property_service.list_beds(
        db, room_id=room.room_id, host_id=host.host_id
    )
    bodies = [BedResponse.model_validate(b).model_dump() for b in beds]

    assert [b["bed_label"] for b in bodies] == ["A", "B"]
    assert set(bodies[0]) == {"bed_id", "bed_label"}
