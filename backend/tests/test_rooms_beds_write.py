"""객실·침대 생성 API 회귀 테스트 (api_contract.md 2.6절).

세 가지를 고정한다.

1. **판매단위별 허용 조합**(2.6절 표). `PROPERTY` 숙소에 객실을 만들 수 없고,
   `ROOM` 숙소의 객실에 침대를 만들 수 없다. 조회 쪽이 *"빈 배열이 정상"*
   이라고 정한 것(2.1·2.2절)의 짝이다 — 만들 수 있게 두면 조회는 계속 빈
   배열을 기대하는데 DB에는 행이 쌓인다.
2. **409 2종을 제약 이름으로 번역한다.** 선조회로 막지 않는다(TOCTOU).
3. **침대 경로에는 `property_id`가 없다.** 객실에서 숙소를 역추적하지 않으면
   남의 객실에 침대를 만들 수 있다.
"""

from __future__ import annotations

import uuid

import pytest
import pytest_asyncio
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    BedLabelAlreadyExistsError,
    InvalidUnitHierarchyError,
    ResourceNotFoundError,
    RoomNameAlreadyExistsError,
)
from app.models.enums import AccommodationType, BookableUnitType
from app.models.host import Host
from app.models.property import Property
from app.schemas.property import (
    BedCreateRequest,
    BedResponse,
    RoomCreateRequest,
    RoomResponse,
)
from app.services import property_service

pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# 픽스처·지역 헬퍼 — conftest는 고치지 않는다
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def stranger(db: AsyncSession):
    """남의 계정. IDOR 테스트는 **실재하는 타인**이 있어야 의미가 있다.

    🔴 **teardown에서 지운다.** 9/14에 지역 헬퍼가 만든 `other-*` 호스트가
    `conftest`의 정리 경로를 타지 않아 **전체 회귀 한 번마다 2건씩** 쌓였다
    (9/15 실측 누적 175건). 형태는 `conftest.py`의 `host` 픽스처와 같다.

    **접두사를 파일마다 다르게 두는 것은 의도다** — 누수가 다시 생기면 어느
    파일이 남겼는지 이메일 접두사로 바로 가려낼 수 있다.
    """
    obj = Host(
        email=f"roomsbeds-{uuid.uuid4().hex[:10]}@test.local",
        password_hash="not-a-real-hash",
        name="다른호스트",
    )
    db.add(obj)
    await db.commit()
    # rollback이 인스턴스 속성을 만료시켜 이후 obj.host_id 접근이 지연로딩(동기 IO)을
    #   유발한다 → MissingGreenlet. conftest와 같은 이유로 id를 값으로 미리 뽑는다.
    host_id = obj.host_id
    yield obj

    await db.rollback()
    stored = await db.get(Host, host_id)
    if stored is not None:
        await db.delete(stored)   # properties → rooms → beds 까지 CASCADE
        await db.commit()


async def _prop(db: AsyncSession, host_id: int, unit: BookableUnitType) -> Property:
    prop = Property(
        host_id=host_id,
        name="테스트숙소",
        accommodation_type=AccommodationType.HOSTEL,
        bookable_unit_type=unit,
    )
    db.add(prop)
    await db.commit()
    await db.refresh(prop)
    return prop


async def _add_room(db: AsyncSession, property_id: int, host_id: int, name: str, **kw):
    payload = RoomCreateRequest.model_validate({"room_name": name, **kw})
    room = await property_service.create_room(
        db, property_id=property_id, host_id=host_id, payload=payload
    )
    await db.commit()
    return room


async def _add_bed(db: AsyncSession, room_id: int, host_id: int, label: str):
    payload = BedCreateRequest.model_validate({"bed_label": label})
    bed = await property_service.create_bed(
        db, room_id=room_id, host_id=host_id, payload=payload
    )
    await db.commit()
    return bed


# ---------------------------------------------------------------------------
# 1. POST /properties/{id}/rooms — 판매단위
# ---------------------------------------------------------------------------


async def test_create_room_on_room_unit_property(db: AsyncSession, host):
    """`ROOM` 단위 숙소에 객실 생성 — **201**이고 응답은 2.1절 원소와 동형."""
    prop = await _prop(db, host.host_id, BookableUnitType.ROOM)
    room = await _add_room(db, prop.property_id, host.host_id, "101호", capacity=4)

    body = RoomResponse.model_validate(room).model_dump()
    assert body == {"room_id": room.room_id, "room_name": "101호", "capacity": 4}
    assert set(body) == {"room_id", "room_name", "capacity"}


async def test_create_room_on_bed_unit_property(db: AsyncSession, host):
    """`BED` 단위 숙소에도 객실을 만든다 — 침대가 객실 하위에 달리기 때문이다."""
    prop = await _prop(db, host.host_id, BookableUnitType.BED)
    room = await _add_room(db, prop.property_id, host.host_id, "도미토리A")

    assert room.room_name == "도미토리A"


async def test_create_room_on_property_unit_is_400(db: AsyncSession, host):
    """🔴 `PROPERTY` 단위 숙소에 객실 생성 → **400 `INVALID_UNIT_HIERARCHY`**.

    2.1절이 *"`PROPERTY` 숙소의 객실 목록이 빈 배열인 것이 정상"*이라고 정한
    것의 짝이다. 만들 수 있게 두면 조회는 빈 배열을 기대하는데 DB에는 행이
    쌓여 어긋난다.
    """
    prop = await _prop(db, host.host_id, BookableUnitType.PROPERTY)
    payload = RoomCreateRequest.model_validate({"room_name": "101호"})

    with pytest.raises(InvalidUnitHierarchyError) as exc:
        await property_service.create_room(
            db, property_id=prop.property_id, host_id=host.host_id, payload=payload
        )

    assert exc.value.code == "INVALID_UNIT_HIERARCHY"
    assert exc.value.status_code == 400


async def test_create_room_does_not_reuse_reservation_validator(db: AsyncSession, host):
    """🔴 `validate_unit_hierarchy`를 재사용했다면 **이 테스트가 실패한다.**

    그 함수는 `ROOM` 숙소에서 `room_id=None`을 `ROOM_ID_REQUIRED` 400으로
    거부한다. 객실을 *만드는* 시점에는 `room_id`가 아직 없으므로 정상 요청이
    막힌다 — 2.6절 표는 그 칸이 ✅다.

    세 함수의 이름이 비슷해 합치고 싶어지는 자리라 회귀로 고정한다
    (devlog 9/13 3절).
    """
    prop = await _prop(db, host.host_id, BookableUnitType.ROOM)
    room = await _add_room(db, prop.property_id, host.host_id, "201호")

    assert room.room_id is not None


# ---------------------------------------------------------------------------
# 2. POST rooms — 409 · capacity
# ---------------------------------------------------------------------------


async def test_duplicate_room_name_is_409(db: AsyncSession, host):
    """같은 숙소에 같은 이름 → **409 `ROOM_NAME_ALREADY_EXISTS`**.

    `uq_property_room_name` 위반을 **제약 이름으로** 번역한다. 선조회로 미리
    막지 않는다 — 조회와 INSERT 사이에 다른 요청이 끼어들 수 있다(2.6절).
    """
    prop = await _prop(db, host.host_id, BookableUnitType.ROOM)
    pid = prop.property_id
    await _add_room(db, pid, host.host_id, "101호")

    payload = RoomCreateRequest.model_validate({"room_name": "101호"})
    with pytest.raises(RoomNameAlreadyExistsError) as exc:
        await property_service.create_room(
            db, property_id=pid, host_id=host.host_id, payload=payload
        )

    assert exc.value.code == "ROOM_NAME_ALREADY_EXISTS"
    assert exc.value.status_code == 409


async def test_same_room_name_in_different_property_is_ok(db: AsyncSession, host):
    """제약이 `(property_id, room_name)`이라 **다른 숙소의 같은 이름은 정상**이다.

    "101호"는 숙소마다 있는 흔한 이름이다. 전역 UNIQUE였다면 여기서 막힌다.
    """
    a = await _prop(db, host.host_id, BookableUnitType.ROOM)
    b = await _prop(db, host.host_id, BookableUnitType.ROOM)
    await _add_room(db, a.property_id, host.host_id, "101호")
    room_b = await _add_room(db, b.property_id, host.host_id, "101호")

    assert room_b.room_name == "101호"


async def test_capacity_null_is_allowed(db: AsyncSession, host):
    """`capacity` 생략은 정상이며 `null`(= 미입력)로 저장된다 — `0`이 아니다(2.1절)."""
    prop = await _prop(db, host.host_id, BookableUnitType.ROOM)
    room = await _add_room(db, prop.property_id, host.host_id, "301호")

    assert room.capacity is None


@pytest.mark.parametrize("bad", [0, -1])
async def test_capacity_zero_or_negative_is_validation_error(db: AsyncSession, bad):
    """🔴 `capacity <= 0`은 거부한다 — **`INVALID_CAPACITY` 철회는 코드만**이다.

    2.6절 에러 표가 `VALIDATION_ERROR`로 받기로 했고, Pydantic `gt=0`이
    잡으면 `main.py` 핸들러가 그 코드로 번역한다.
    """
    with pytest.raises(ValidationError):
        RoomCreateRequest.model_validate({"room_name": "101호", "capacity": bad})


async def test_create_room_on_other_host_property_is_404(db: AsyncSession, host, stranger):
    """남의 숙소에 객실 생성 → 404. 판매단위 400보다 **먼저** 판정된다."""
    theirs = await _prop(db, stranger.host_id, BookableUnitType.ROOM)
    payload = RoomCreateRequest.model_validate({"room_name": "101호"})

    with pytest.raises(ResourceNotFoundError):
        await property_service.create_room(
            db, property_id=theirs.property_id, host_id=host.host_id, payload=payload
        )


# ---------------------------------------------------------------------------
# 3. POST /rooms/{id}/beds
# ---------------------------------------------------------------------------


async def test_create_bed_on_bed_unit_property(db: AsyncSession, host):
    """`BED` 단위 숙소의 객실에 침대 생성 — **201**, 응답은 2.2절 원소와 동형."""
    prop = await _prop(db, host.host_id, BookableUnitType.BED)
    room = await _add_room(db, prop.property_id, host.host_id, "도미토리")
    bed = await _add_bed(db, room.room_id, host.host_id, "A")

    body = BedResponse.model_validate(bed).model_dump()
    assert body == {"bed_id": bed.bed_id, "bed_label": "A"}
    assert set(body) == {"bed_id", "bed_label"}


async def test_create_bed_on_room_unit_property_is_400(db: AsyncSession, host):
    """🔴 `ROOM` 단위 숙소의 객실에 침대 생성 → **400**.

    객실을 침대로 나누어 팔지 않으므로 그 객실의 침대 목록이 빈 배열인 것이
    정상이다(2.2절). 객실 생성과 **통과 조건이 다르다** — `ROOM`은 객실은
    되지만 침대는 안 된다(2.6절 표의 두 열).
    """
    prop = await _prop(db, host.host_id, BookableUnitType.ROOM)
    room = await _add_room(db, prop.property_id, host.host_id, "101호")
    payload = BedCreateRequest.model_validate({"bed_label": "A"})

    with pytest.raises(InvalidUnitHierarchyError) as exc:
        await property_service.create_bed(
            db, room_id=room.room_id, host_id=host.host_id, payload=payload
        )

    assert exc.value.code == "INVALID_UNIT_HIERARCHY"


async def test_duplicate_bed_label_is_409(db: AsyncSession, host):
    """같은 객실에 같은 라벨 → **409 `BED_LABEL_ALREADY_EXISTS`**.

    `uq_room_bed_label` 위반이다. ⚠️ 접두사 `uq_room_`으로 판정하면
    `uq_room_property_ref`까지 걸리므로 **제약 이름 전체**로 본다.
    """
    prop = await _prop(db, host.host_id, BookableUnitType.BED)
    room = await _add_room(db, prop.property_id, host.host_id, "도미토리")
    rid = room.room_id
    await _add_bed(db, rid, host.host_id, "A")

    payload = BedCreateRequest.model_validate({"bed_label": "A"})
    with pytest.raises(BedLabelAlreadyExistsError) as exc:
        await property_service.create_bed(
            db, room_id=rid, host_id=host.host_id, payload=payload
        )

    assert exc.value.code == "BED_LABEL_ALREADY_EXISTS"
    assert exc.value.status_code == 409


async def test_same_bed_label_in_different_room_is_ok(db: AsyncSession, host):
    """제약이 `(room_id, bed_label)`이라 **다른 객실의 같은 라벨은 정상**이다."""
    prop = await _prop(db, host.host_id, BookableUnitType.BED)
    r1 = await _add_room(db, prop.property_id, host.host_id, "도미토리1")
    r2 = await _add_room(db, prop.property_id, host.host_id, "도미토리2")
    await _add_bed(db, r1.room_id, host.host_id, "A")
    bed2 = await _add_bed(db, r2.room_id, host.host_id, "A")

    assert bed2.bed_label == "A"


async def test_create_bed_on_other_host_room_is_404(db: AsyncSession, host, stranger):
    """🔴 남의 객실에 침대 생성 → **404**.

    경로에 `property_id`가 없어, 객실에서 숙소를 역추적하지 않으면 이 요청이
    **그대로 성공한다.** 커밋 1의 `GET /rooms/{id}/beds`와 같은 조인이다.
    """
    theirs = await _prop(db, stranger.host_id, BookableUnitType.BED)
    room = await _add_room(db, theirs.property_id, stranger.host_id, "도미토리")
    payload = BedCreateRequest.model_validate({"bed_label": "A"})

    with pytest.raises(ResourceNotFoundError):
        await property_service.create_bed(
            db, room_id=room.room_id, host_id=host.host_id, payload=payload
        )


async def test_create_bed_on_missing_room_is_404(db: AsyncSession, host):
    """없는 객실도 같은 404다 — 위와 응답이 구분되지 않아야 한다."""
    payload = BedCreateRequest.model_validate({"bed_label": "A"})

    with pytest.raises(ResourceNotFoundError):
        await property_service.create_bed(
            db, room_id=99_999_999, host_id=host.host_id, payload=payload
        )


# ---------------------------------------------------------------------------
# 4. 생성 결과가 조회에 그대로 나온다
# ---------------------------------------------------------------------------


async def test_created_room_and_bed_appear_in_listings(db: AsyncSession, host):
    """등록한 것이 2.1·2.2절 목록에 그대로 나온다 — 두 API의 형태가 맞물린다."""
    prop = await _prop(db, host.host_id, BookableUnitType.BED)
    pid = prop.property_id
    room = await _add_room(db, pid, host.host_id, "도미토리", capacity=8)
    rid = room.room_id
    await _add_bed(db, rid, host.host_id, "A")
    await _add_bed(db, rid, host.host_id, "B")

    rooms = await property_service.list_rooms(db, property_id=pid, host_id=host.host_id)
    beds = await property_service.list_beds(db, room_id=rid, host_id=host.host_id)

    assert [RoomResponse.model_validate(r).model_dump() for r in rooms] == [
        {"room_id": rid, "room_name": "도미토리", "capacity": 8}
    ]
    assert [b.bed_label for b in beds] == ["A", "B"]
