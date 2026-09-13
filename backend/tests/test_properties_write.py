"""숙소 생성·수정 API 회귀 테스트 (api_contract.md 2.3·2.5절).

세 가지를 고정한다.

1. **`IMMUTABLE_FIELD`는 무시가 아니라 400이다**(2.5절). 이 결정은 구현에서
   **두 번 뒤집힐 수 있었다** — 요청 스키마에서 필드를 빼면 Pydantic이
   조용히 무시하고, `extra="forbid"`로 두면 422가 먼저 나가 서비스까지
   오지 않는다. 아래 두 테스트가 그 자리를 막는다.
2. **생략한 필드는 DB 기본값**이 채운다(2.3절). `None`을 실어 보내면
   `NOT NULL` 위반이 나므로 INSERT에서 컬럼을 빼야 한다.
3. **404 통일** — 남의 숙소 PATCH는 403도 400도 아닌 404다(0절).
"""

from __future__ import annotations

import uuid
from datetime import time

import pytest
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ImmutableFieldError, ResourceNotFoundError
from app.models.enums import AccommodationType, BookableUnitType
from app.models.host import Host
from app.schemas.property import (
    PropertyCreateRequest,
    PropertyDetailResponse,
    PropertyUpdateRequest,
)
from app.services import property_service

pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# 지역 헬퍼 — conftest는 고치지 않는다
# ---------------------------------------------------------------------------

_MINIMAL = {
    "name": "강남 3룸 독채",
    "accommodation_type": "URBAN_HOMESTAY",
    "bookable_unit_type": "PROPERTY",
}


async def _other_host(db: AsyncSession) -> Host:
    other = Host(
        email=f"other-{uuid.uuid4().hex[:12]}@test.local",
        password_hash="not-a-real-hash",
        name="다른호스트",
    )
    db.add(other)
    await db.commit()
    await db.refresh(other)
    return other


async def _create(db: AsyncSession, host_id: int, **overrides):
    payload = PropertyCreateRequest.model_validate({**_MINIMAL, **overrides})
    prop = await property_service.create_property(db, host_id=host_id, payload=payload)
    await db.commit()
    return prop


# ---------------------------------------------------------------------------
# 1. POST /properties
# ---------------------------------------------------------------------------


async def test_create_returns_all_eleven_fields(db: AsyncSession, host):
    """응답은 목록 4필드가 아니라 **상세와 같은 11필드**다(2.3절).

    온보딩 위저드가 등록 직후 전체 상태를 그려야 하며, 목록 형태로
    돌려주면 클라이언트가 상세를 곧바로 한 번 더 호출하게 된다.
    """
    prop = await _create(db, host.host_id)
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


async def test_create_omitted_fields_get_db_defaults(db: AsyncSession, host):
    """🔴 생략한 7필드는 **DB 기본값**으로 채워진다(2.3절).

    `base_price` `0`은 **"미설정"이지 "0원"이 아니다** — 등록 직후가 바로 이
    상태이며, 이때 예약이 들어오면 금액을 추정하지 않는다.

    ⚠️ 이 테스트가 지키는 것은 *"`None`을 INSERT에 실어 보내지 않는다"*는
    구현 세부다. 실어 보내면 `NOT NULL` 위반으로 등록 자체가 실패한다.
    """
    prop = await _create(db, host.host_id)
    body = PropertyDetailResponse.model_validate(prop).model_dump()

    assert body["base_price"] == 0
    assert body["checkin_time"] == "15:00"
    assert body["checkout_time"] == "11:00"
    assert body["weekday_adjustment_enabled"] is True
    assert body["holiday_adjustment_enabled"] is True
    assert body["address"] is None
    assert body["lower_bound_price"] is None


async def test_create_accepts_all_optional_fields(db: AsyncSession, host):
    """보낸 값은 기본값을 덮어쓴다. `"HH:MM"` 문자열이 `TIME`으로 들어간다."""
    prop = await _create(
        db,
        host.host_id,
        address="서울시 강남구...",
        base_price=150000,
        lower_bound_price=120000,
        checkin_time="16:00",
        checkout_time="10:00",
        weekday_adjustment_enabled=False,
        holiday_adjustment_enabled=False,
    )
    body = PropertyDetailResponse.model_validate(prop).model_dump()

    assert body["address"] == "서울시 강남구..."
    assert body["base_price"] == 150000
    assert body["lower_bound_price"] == 120000
    assert body["checkin_time"] == "16:00"
    assert body["checkout_time"] == "10:00"
    assert body["weekday_adjustment_enabled"] is False
    assert body["holiday_adjustment_enabled"] is False


async def test_create_owner_comes_from_auth_not_body(db: AsyncSession, host):
    """🔴 소유자는 **JWT에서** 온다. 본문의 `host_id`는 받지도 쓰지도 않는다.

    받으면 남의 id를 적어 보내는 순간 다른 호스트 앞으로 숙소가 생긴다.
    """
    other = await _other_host(db)
    payload = PropertyCreateRequest.model_validate(
        {**_MINIMAL, "host_id": other.host_id}  # 무시되어야 한다
    )
    assert "host_id" not in payload.model_fields_set

    prop = await property_service.create_property(
        db, host_id=host.host_id, payload=payload
    )
    await db.commit()

    assert prop.host_id == host.host_id


async def test_create_then_get_detail_matches(db: AsyncSession, host):
    """등록한 값이 `GET /properties/{id}`에서 **그대로** 나온다."""
    created = await _create(db, host.host_id, base_price=99000, checkin_time="14:30")
    fetched = await property_service.get_property_detail(
        db, property_id=created.property_id, host_id=host.host_id
    )

    assert PropertyDetailResponse.model_validate(
        fetched
    ).model_dump() == PropertyDetailResponse.model_validate(created).model_dump()
    assert fetched.base_price == 99000
    assert fetched.checkin_time == time(14, 30)


async def test_create_rejects_bad_enum_as_validation_error(db: AsyncSession, host):
    """허용값 밖의 `accommodation_type`은 **Pydantic**이 잡는다 → `VALIDATION_ERROR`.

    2.3절 에러 표가 `VALIDATION_ERROR` 하나로 받기로 한 자리이며,
    9/13에 `INVALID_ACCOMMODATION_TYPE`을 철회한 것이 이 결정이다.
    """
    with pytest.raises(ValidationError):
        PropertyCreateRequest.model_validate({**_MINIMAL, "accommodation_type": "MOTEL"})


# ---------------------------------------------------------------------------
# 2. PATCH — IMMUTABLE_FIELD
# ---------------------------------------------------------------------------


async def test_patch_accommodation_type_is_400_not_ignored(db: AsyncSession, host):
    """🔴 `accommodation_type`을 보내면 **400 `IMMUTABLE_FIELD`**다(2.5절).

    조용히 무시하면 호스트는 바뀐 줄 알고 화면을 떠난다. 요청 스키마가 이
    필드를 **갖고 있어야** 서비스까지 와서 거부할 수 있다 — 빼면 Pydantic이
    모르는 필드로 버려 400이 나가지 않는다.
    """
    prop = await _create(db, host.host_id)
    payload = PropertyUpdateRequest.model_validate({"accommodation_type": "HOSTEL"})

    with pytest.raises(ImmutableFieldError) as exc:
        await property_service.update_property(
            db, property_id=prop.property_id, host_id=host.host_id, payload=payload
        )

    assert exc.value.code == "IMMUTABLE_FIELD"
    assert exc.value.status_code == 400
    assert "accommodation_type" in exc.value.message


async def test_patch_bookable_unit_type_is_400(db: AsyncSession, host):
    """`bookable_unit_type`도 같다. 바꾸면 과거 예약의 조합이 어긋난다(2.5절)."""
    prop = await _create(db, host.host_id)
    payload = PropertyUpdateRequest.model_validate({"bookable_unit_type": "ROOM"})

    with pytest.raises(ImmutableFieldError) as exc:
        await property_service.update_property(
            db, property_id=prop.property_id, host_id=host.host_id, payload=payload
        )

    assert "bookable_unit_type" in exc.value.message


async def test_patch_immutable_field_with_garbage_value_is_still_immutable(
    db: AsyncSession, host
):
    """🔴 **값이 무엇이든 같은 `IMMUTABLE_FIELD`**다 — `VALIDATION_ERROR`가 아니다.

    타입을 `AccommodationType`으로 두면 잘못된 값에 Pydantic이 먼저 걸려
    *"값이 틀렸다"*고 답하게 된다. 바꿀 수 없는 필드인데 값 탓을 하는 셈이라
    프론트가 그 입력을 비활성화하지 못한다. 그래서 `Any`로 둔다.
    """
    prop = await _create(db, host.host_id)
    payload = PropertyUpdateRequest.model_validate({"accommodation_type": "GARBAGE"})

    with pytest.raises(ImmutableFieldError):
        await property_service.update_property(
            db, property_id=prop.property_id, host_id=host.host_id, payload=payload
        )


async def test_patch_immutable_field_as_null_is_still_400(db: AsyncSession, host):
    """`null`을 보내도 **"바꾸려 했다"**로 본다 — 판정은 값이 아니라 존재 여부다."""
    prop = await _create(db, host.host_id)
    payload = PropertyUpdateRequest.model_validate({"bookable_unit_type": None})

    assert "bookable_unit_type" in payload.model_fields_set
    with pytest.raises(ImmutableFieldError):
        await property_service.update_property(
            db, property_id=prop.property_id, host_id=host.host_id, payload=payload
        )


async def test_patch_immutable_field_blocks_the_whole_request(db: AsyncSession, host):
    """수정 가능 필드와 **함께** 보내도 전체가 거부된다 — 부분 적용은 없다.

    일부만 반영하면 호스트는 요청이 성공했다고 보고 나머지도 바뀐 줄 안다.
    """
    prop = await _create(db, host.host_id, base_price=100000)
    # 아래 rollback()이 세션의 인스턴스를 전부 만료시킨다 → 그 뒤 속성 접근은
    #   지연로딩(동기 IO)이라 async 컨텍스트에서 MissingGreenlet이 된다
    #   (conftest.py 27~33행). 그래서 id를 값으로 먼저 붙잡는다.
    pid, host_id = prop.property_id, host.host_id
    payload = PropertyUpdateRequest.model_validate(
        {"name": "새 이름", "accommodation_type": "HOSTEL"}
    )

    with pytest.raises(ImmutableFieldError):
        await property_service.update_property(
            db, property_id=pid, host_id=host_id, payload=payload
        )

    await db.rollback()
    fetched = await property_service.get_property_detail(
        db, property_id=pid, host_id=host_id
    )
    assert fetched.name == "강남 3룸 독채"


# ---------------------------------------------------------------------------
# 3. PATCH — 수정 가능 8필드
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("field", "sent", "expected"),
    [
        ("name", "새 숙소명", "새 숙소명"),
        ("address", "서울시 마포구...", "서울시 마포구..."),
        ("base_price", 180000, 180000),
        ("lower_bound_price", 90000, 90000),
        ("checkin_time", "16:00", time(16, 0)),
        ("checkout_time", "10:00", time(10, 0)),
        ("weekday_adjustment_enabled", False, False),
        ("holiday_adjustment_enabled", False, False),
    ],
)
async def test_patch_each_mutable_field(db: AsyncSession, host, field, sent, expected):
    """수정 가능 8필드를 하나씩 바꾼다(2.5절 표의 ✅ 8칸)."""
    prop = await _create(db, host.host_id)
    payload = PropertyUpdateRequest.model_validate({field: sent})

    updated = await property_service.update_property(
        db, property_id=prop.property_id, host_id=host.host_id, payload=payload
    )
    await db.commit()

    assert getattr(updated, field) == expected


async def test_patch_only_sent_fields_change(db: AsyncSession, host):
    """보내지 않은 필드는 **그대로 둔다**(2.5절). 기본값으로 되돌아가지 않는다."""
    prop = await _create(
        db, host.host_id, address="원래 주소", base_price=150000, checkin_time="16:00"
    )
    payload = PropertyUpdateRequest.model_validate({"checkout_time": "10:00"})

    updated = await property_service.update_property(
        db, property_id=prop.property_id, host_id=host.host_id, payload=payload
    )
    await db.commit()

    assert updated.checkout_time == time(10, 0)
    assert updated.address == "원래 주소"
    assert updated.base_price == 150000
    assert updated.checkin_time == time(16, 0)


async def test_patch_null_clears_nullable_columns(db: AsyncSession, host):
    """nullable 둘은 `null`로 **지울 수 있다**(2.5절).

    미전송과 뜻이 정반대라 `model_fields_set`으로 구분해야 한다.
    """
    prop = await _create(
        db, host.host_id, address="지워질 주소", lower_bound_price=120000
    )
    payload = PropertyUpdateRequest.model_validate(
        {"address": None, "lower_bound_price": None}
    )

    updated = await property_service.update_property(
        db, property_id=prop.property_id, host_id=host.host_id, payload=payload
    )
    await db.commit()

    assert updated.address is None
    assert updated.lower_bound_price is None


async def test_patch_null_on_not_null_column_is_validation_error(db: AsyncSession):
    """`NOT NULL` 컬럼에 `null`을 보내는 것은 **형식 오류**다 → `VALIDATION_ERROR`.

    `null`의 뜻은 2.5절이 **nullable 컬럼에 한해** *"지운다"*로 정했다.
    `name: null`은 지울 수도 바꿀 수도 없어 조용히 무시되는 것이 최악이다.
    """
    with pytest.raises(ValidationError):
        PropertyUpdateRequest.model_validate({"name": None})


async def test_patch_empty_body_returns_current_state(db: AsyncSession, host):
    """🔴 **빈 본문 `{}`은 에러가 아니다** — 현재 상태를 그대로 `200`으로 돌려준다.

    우리가 고른 것이 아니라 **2.5절이 확정한 동작**이다: *"바꿀 것이 없다는
    뜻이므로 현재 상태를 그대로 200으로 돌려준다."*
    """
    prop = await _create(db, host.host_id, base_price=150000)
    before = PropertyDetailResponse.model_validate(prop).model_dump()

    payload = PropertyUpdateRequest.model_validate({})
    assert payload.model_fields_set == set()

    updated = await property_service.update_property(
        db, property_id=prop.property_id, host_id=host.host_id, payload=payload
    )
    await db.commit()

    assert PropertyDetailResponse.model_validate(updated).model_dump() == before


# ---------------------------------------------------------------------------
# 4. PATCH — IDOR
# ---------------------------------------------------------------------------


async def test_patch_other_host_property_is_404(db: AsyncSession, host):
    """🔴 남의 숙소는 **404**다 — 403도, `IMMUTABLE_FIELD` 400도 아니다(0절)."""
    other = await _other_host(db)
    theirs = await _create(db, other.host_id)
    payload = PropertyUpdateRequest.model_validate({"name": "가로챈 이름"})

    with pytest.raises(ResourceNotFoundError):
        await property_service.update_property(
            db, property_id=theirs.property_id, host_id=host.host_id, payload=payload
        )


async def test_patch_checks_ownership_before_immutable_field(db: AsyncSession, host):
    """🔴 **판정 순서** — 소유권(404)이 수정 불가 필드(400)보다 먼저다.

    반대로 하면 남의 숙소에 `accommodation_type`을 보냈을 때 400이 나가
    *"그 id는 존재한다"*가 새어 나간다. 9/13 `room_id` 404/400 분리에서 정한
    순서와 같다.
    """
    other = await _other_host(db)
    theirs = await _create(db, other.host_id)
    payload = PropertyUpdateRequest.model_validate({"accommodation_type": "HOSTEL"})

    with pytest.raises(ResourceNotFoundError):
        await property_service.update_property(
            db, property_id=theirs.property_id, host_id=host.host_id, payload=payload
        )


async def test_patch_missing_property_is_404(db: AsyncSession, host):
    """없는 숙소도 같은 404다 — 위와 응답이 구분되지 않아야 한다."""
    payload = PropertyUpdateRequest.model_validate({"name": "x"})

    with pytest.raises(ResourceNotFoundError):
        await property_service.update_property(
            db, property_id=99_999_999, host_id=host.host_id, payload=payload
        )
