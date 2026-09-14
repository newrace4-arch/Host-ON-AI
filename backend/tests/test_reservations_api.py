"""예약 API 4종 통합 테스트 (api_contract.md 4.3~4.6절).

## 왜 서비스 단위가 아니라 통합인가

이 라우터들이 **`response_model`을 붙인 첫 4개**다. 반환 형태가 선언과
어긋나면 `ResponseValidationError`로 **500**이 난다(400이 아니다) — 서비스
함수만 시험하면 그 자리가 비고, **배포 후에 안다.**

그래서 봉투 형태·상태 코드·에러 코드를 **응답 본문에서** 확인한다.

## 테스트가 호스트를 남기지 않는다

9/14에 `other-*` 호스트가 **59건 누적**된 것이 보고됐다 — 지역 헬퍼로 만든
호스트가 `conftest.py`의 teardown 경로를 타지 않았기 때문이다. 여기서는
`stranger` **픽스처**로 만들고 `hosts` CASCADE로 정리한다(conftest의 `host`
픽스처와 같은 형태). 이번에 늘리지 않는다.
"""

from __future__ import annotations

import uuid
from datetime import date

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token
from app.main import app
from app.models.channel import ChannelConnection
from app.models.enums import (
    AccommodationType,
    BookableUnitType,
    Channel,
    ReservationStatus,
)
from app.models.host import Host
from app.models.property import Bed, Property, Room

pytestmark = pytest.mark.asyncio

D = date


# ---------------------------------------------------------------------------
# 픽스처 — 전부 정리된다
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def auth(host_id: int) -> dict[str, str]:
    return {"Authorization": "Bearer " + create_access_token(host_id)}


@pytest_asyncio.fixture
async def stranger(db: AsyncSession):
    """남의 계정. **teardown에서 지운다** — 9/14 누적 사고를 반복하지 않는다."""
    obj = Host(
        email=f"parity-stranger-{uuid.uuid4().hex[:10]}@test.local",
        password_hash="not-a-real-hash",
        name="남의호스트",
    )
    db.add(obj)
    await db.commit()
    await db.refresh(obj)
    host_id = obj.host_id
    yield obj

    await db.rollback()
    stored = await db.get(Host, host_id)
    if stored is not None:
        await db.delete(stored)       # properties→reservations까지 CASCADE
        await db.commit()


async def _make(db: AsyncSession, host_id: int, unit: BookableUnitType):
    """숙소 + (필요 시)객실·침대 + 채널 연결."""
    prop = Property(
        host_id=host_id,
        name="예약API숙소",
        accommodation_type=AccommodationType.HOSTEL,
        bookable_unit_type=unit,
    )
    db.add(prop)
    await db.commit()
    await db.refresh(prop)

    conn = ChannelConnection(property_id=prop.property_id, channel=Channel.AIRBNB)
    db.add(conn)
    room = bed = None
    if unit in (BookableUnitType.ROOM, BookableUnitType.BED):
        room = Room(property_id=prop.property_id, room_name="101")
        db.add(room)
    await db.commit()
    await db.refresh(conn)
    if room is not None:
        await db.refresh(room)
        if unit is BookableUnitType.BED:
            bed = Bed(room_id=room.room_id, bed_label="A")
            db.add(bed)
            await db.commit()
            await db.refresh(bed)

    return {
        "property_id": prop.property_id,
        "conn": conn.connection_id,
        "room": room.room_id if room is not None else None,
        "bed": bed.bed_id if bed is not None else None,
    }


def _body(ctx, **over):
    base = {
        "property_id": ctx["property_id"],
        "channel_connection_id": ctx["conn"],
        "check_in": "2027-05-01",
        "check_out": "2027-05-05",
        "guest_name": "게스트",
    }
    base.update(over)
    return base


# ---------------------------------------------------------------------------
# 4.5 POST /reservations
# ---------------------------------------------------------------------------


async def test_create_returns_201_and_envelope(db, host, client):
    """**201**이고 봉투가 `{data, error}` 형태다(0절)."""
    ctx = await _make(db, host.host_id, BookableUnitType.PROPERTY)
    res = client.post("/reservations", json=_body(ctx), headers=auth(host.host_id))

    assert res.status_code == 201
    body = res.json()
    assert set(body) == {"data", "error"}
    assert body["error"] is None
    assert set(body["data"]) == {
        "reservation_id", "property_id", "room_id", "bed_id",
        "channel_connection_id", "guest_name", "check_in", "check_out",
        "reservation_status", "refund_status", "financial_status",
        "gross_amount", "fee_amount", "net_amount", "is_conflict",
    }
    assert body["data"]["is_conflict"] is False
    assert body["data"]["reservation_status"] == "CONFIRMED"


async def test_create_rejects_net_amount_silently(db, host, client):
    """🔴 `net_amount`를 보내도 **무시된다** — 생성 컬럼이라 받지 않는다(4.5절).

    DTO에 필드가 없으므로 Pydantic이 모르는 필드로 버린다. 실어 보냈다면
    PostgreSQL이 거부해 500이 났을 것이다.
    """
    ctx = await _make(db, host.host_id, BookableUnitType.PROPERTY)
    res = client.post(
        "/reservations",
        json=_body(ctx, net_amount=999999, gross_amount=100000, fee_amount=15000),
        headers=auth(host.host_id),
    )
    assert res.status_code == 201
    assert res.json()["data"]["net_amount"] == 85000      # 100000 - 15000


@pytest.mark.parametrize(
    ("unit", "over", "code"),
    [
        (BookableUnitType.PROPERTY, {"room_id": 1}, "INVALID_UNIT_HIERARCHY"),
        (BookableUnitType.ROOM, {}, "ROOM_ID_REQUIRED"),
        (BookableUnitType.BED, {}, "BED_ID_REQUIRED"),
    ],
)
async def test_create_unit_hierarchy_400(db, host, client, unit, over, code):
    """계층 위반 400 3종(4.5절 표)."""
    ctx = await _make(db, host.host_id, unit)
    res = client.post(
        "/reservations", json=_body(ctx, **over), headers=auth(host.host_id)
    )
    assert res.status_code == 400
    assert res.json()["error"]["code"] == code
    assert res.json()["data"] is None


async def test_create_overlap_409(db, host, client):
    """🔴 겹침은 **409 `RESERVATION_OVERLAP`**(v1.7에 확정된 이름)."""
    ctx = await _make(db, host.host_id, BookableUnitType.PROPERTY)
    first = client.post("/reservations", json=_body(ctx), headers=auth(host.host_id))
    assert first.status_code == 201

    res = client.post(
        "/reservations",
        json=_body(ctx, check_in="2027-05-03", check_out="2027-05-07"),
        headers=auth(host.host_id),
    )
    assert res.status_code == 409
    assert res.json()["error"]["code"] == "RESERVATION_OVERLAP"


async def test_create_on_other_host_property_404(db, host, stranger, client):
    """남의 숙소에 예약 생성 → **404**(403 아님, 0절)."""
    ctx = await _make(db, stranger.host_id, BookableUnitType.PROPERTY)
    res = client.post("/reservations", json=_body(ctx), headers=auth(host.host_id))

    assert res.status_code == 404
    assert res.json()["error"]["code"] == "RESOURCE_NOT_FOUND"


# ---------------------------------------------------------------------------
# 4.4 GET /reservations/{id}
# ---------------------------------------------------------------------------


async def test_get_detail_200(db, host, client):
    ctx = await _make(db, host.host_id, BookableUnitType.PROPERTY)
    rid = client.post(
        "/reservations", json=_body(ctx), headers=auth(host.host_id)
    ).json()["data"]["reservation_id"]

    res = client.get(f"/reservations/{rid}", headers=auth(host.host_id))
    assert res.status_code == 200
    assert res.json()["data"]["reservation_id"] == rid
    assert res.json()["data"]["is_conflict"] is False


async def test_get_detail_other_host_404(db, host, stranger, client):
    """🔴 경로에 `property_id`가 없다 — **조인으로 소유권을 보지 않으면 샌다**."""
    ctx = await _make(db, stranger.host_id, BookableUnitType.PROPERTY)
    rid = client.post(
        "/reservations", json=_body(ctx), headers=auth(stranger.host_id)
    ).json()["data"]["reservation_id"]

    res = client.get(f"/reservations/{rid}", headers=auth(host.host_id))
    assert res.status_code == 404
    assert res.json()["error"]["code"] == "RESOURCE_NOT_FOUND"


async def test_get_detail_missing_404(host, client):
    res = client.get("/reservations/99999999", headers=auth(host.host_id))
    assert res.status_code == 404


# ---------------------------------------------------------------------------
# 4.3 GET /properties/{id}/reservations
# ---------------------------------------------------------------------------


async def test_list_returns_span_crossing(db, host, client):
    """🔴 **구간을 가로지르는 예약도 포함**된다 — 빠뜨리면 그리드가 끊긴다."""
    ctx = await _make(db, host.host_id, BookableUnitType.PROPERTY)
    client.post(
        "/reservations",
        json=_body(ctx, check_in="2027-06-28", check_out="2027-07-03"),
        headers=auth(host.host_id),
    )
    res = client.get(
        f"/properties/{ctx['property_id']}/reservations",
        params={"start": "2027-07-01", "end": "2027-07-31"},
        headers=auth(host.host_id),
    )
    assert res.status_code == 200
    assert len(res.json()["data"]) == 1


async def test_list_has_no_meta(db, host, client):
    """`meta`를 넣지 않는다(4.3절 — 0절 예외)."""
    ctx = await _make(db, host.host_id, BookableUnitType.PROPERTY)
    res = client.get(
        f"/properties/{ctx['property_id']}/reservations",
        params={"start": "2027-08-01", "end": "2027-08-31"},
        headers=auth(host.host_id),
    )
    assert set(res.json()) == {"data", "error"}
    assert res.json()["data"] == []


async def test_list_other_host_404(db, host, stranger, client):
    ctx = await _make(db, stranger.host_id, BookableUnitType.PROPERTY)
    res = client.get(
        f"/properties/{ctx['property_id']}/reservations",
        params={"start": "2027-05-01", "end": "2027-05-31"},
        headers=auth(host.host_id),
    )
    assert res.status_code == 404


async def test_list_requires_start_and_end(db, host, client):
    """`start`·`end`는 필수다 — 없으면 형식 검증에 걸린다(400, 0절 봉투)."""
    ctx = await _make(db, host.host_id, BookableUnitType.PROPERTY)
    res = client.get(
        f"/properties/{ctx['property_id']}/reservations", headers=auth(host.host_id)
    )
    assert res.status_code == 400
    assert res.json()["error"]["code"] == "VALIDATION_ERROR"


# ---------------------------------------------------------------------------
# 4.6 PATCH /reservations/{id}/status
# ---------------------------------------------------------------------------


async def test_patch_allowed_transition_200(db, host, client):
    """`CONFIRMED` → `MODIFIED`는 허용 전이다(state_events 1절)."""
    ctx = await _make(db, host.host_id, BookableUnitType.PROPERTY)
    rid = client.post(
        "/reservations", json=_body(ctx), headers=auth(host.host_id)
    ).json()["data"]["reservation_id"]

    res = client.patch(
        f"/reservations/{rid}/status",
        json={"reservation_status": "MODIFIED"},
        headers=auth(host.host_id),
    )
    assert res.status_code == 200
    assert res.json()["data"]["reservation_status"] == "MODIFIED"


async def test_patch_invalid_transition_400(db, host, client):
    """🔴 `CONFIRMED` → `PENDING`은 전이도에 없다 → **`INVALID_STATUS_TRANSITION`**."""
    ctx = await _make(db, host.host_id, BookableUnitType.PROPERTY)
    rid = client.post(
        "/reservations", json=_body(ctx), headers=auth(host.host_id)
    ).json()["data"]["reservation_id"]

    res = client.patch(
        f"/reservations/{rid}/status",
        json={"reservation_status": "PENDING"},
        headers=auth(host.host_id),
    )
    assert res.status_code == 400
    assert res.json()["error"]["code"] == "INVALID_STATUS_TRANSITION"


async def test_patch_cancel_without_refund_400(db, host, client):
    """🔴 **무의미한 조합** — 취소하면서 `refund_status=NONE`이면 같은 코드로 막는다."""
    ctx = await _make(db, host.host_id, BookableUnitType.PROPERTY)
    rid = client.post(
        "/reservations", json=_body(ctx), headers=auth(host.host_id)
    ).json()["data"]["reservation_id"]

    res = client.patch(
        f"/reservations/{rid}/status",
        json={"reservation_status": "CANCELLED"},
        headers=auth(host.host_id),
    )
    assert res.status_code == 400
    assert res.json()["error"]["code"] == "INVALID_STATUS_TRANSITION"

    ok = client.patch(
        f"/reservations/{rid}/status",
        json={"reservation_status": "CANCELLED", "refund_status": "FULL"},
        headers=auth(host.host_id),
    )
    assert ok.status_code == 200
    assert ok.json()["data"]["refund_status"] == "FULL"


async def test_patch_empty_body_returns_current(db, host, client):
    """빈 본문은 에러가 아니라 현재 상태를 그대로 돌려주는 200이다(4.6절)."""
    ctx = await _make(db, host.host_id, BookableUnitType.PROPERTY)
    created = client.post(
        "/reservations", json=_body(ctx), headers=auth(host.host_id)
    ).json()["data"]

    res = client.patch(
        f"/reservations/{created['reservation_id']}/status",
        json={},
        headers=auth(host.host_id),
    )
    assert res.status_code == 200
    assert res.json()["data"] == created


async def test_patch_independent_status_fields(db, host, client):
    """세 상태는 **독립 전이**다 — `financial_status`만 바꿔도 된다."""
    ctx = await _make(db, host.host_id, BookableUnitType.PROPERTY)
    rid = client.post(
        "/reservations", json=_body(ctx), headers=auth(host.host_id)
    ).json()["data"]["reservation_id"]

    res = client.patch(
        f"/reservations/{rid}/status",
        json={"financial_status": "CONFIRMED"},
        headers=auth(host.host_id),
    )
    assert res.status_code == 200
    assert res.json()["data"]["financial_status"] == "CONFIRMED"
    assert res.json()["data"]["reservation_status"] == "CONFIRMED"


async def test_patch_other_host_404(db, host, stranger, client):
    ctx = await _make(db, stranger.host_id, BookableUnitType.PROPERTY)
    rid = client.post(
        "/reservations", json=_body(ctx), headers=auth(stranger.host_id)
    ).json()["data"]["reservation_id"]

    res = client.patch(
        f"/reservations/{rid}/status",
        json={"reservation_status": "MODIFIED"},
        headers=auth(host.host_id),
    )
    assert res.status_code == 404


async def test_patch_checks_ownership_before_transition(db, host, stranger, client):
    """🔴 **판정 순서** — 소유권(404)이 전이 규칙(400)보다 먼저다.

    반대로 하면 남의 예약에 잘못된 전이를 보냈을 때 400이 나가
    *"그 id는 존재한다"*가 새어 나간다.
    """
    ctx = await _make(db, stranger.host_id, BookableUnitType.PROPERTY)
    rid = client.post(
        "/reservations", json=_body(ctx), headers=auth(stranger.host_id)
    ).json()["data"]["reservation_id"]

    res = client.patch(
        f"/reservations/{rid}/status",
        json={"reservation_status": "PENDING"},   # 전이 규칙 위반이기도 하다
        headers=auth(host.host_id),
    )
    assert res.status_code == 404
    assert res.json()["error"]["code"] == "RESOURCE_NOT_FOUND"
