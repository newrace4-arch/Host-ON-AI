"""대시보드 요약 통합 테스트 (api_contract.md 4.1절).

## 왜 통합인가

`response_model=Envelope[DashboardSummaryResponse]`를 붙였으므로 반환 형태가
선언과 어긋나면 **500**(`ResponseValidationError`)이다 — 400이 아니다.
서비스 함수만 시험하면 그 자리가 비고 **배포 후에 안다**
(`test_reservations_api.py`와 같은 판단).

## 🔴 `today_turnover_count`가 이 파일의 핵심이다

4.1절이 `IS NOT DISTINCT FROM`을 쓰라고 못박은 이유는 **PROPERTY 단위
예약이 `room_id`·`bed_id`가 NULL**이라 등호 비교로는 영원히 0이 되기
때문이다. 그런데 —

🔴 **등호로 잘못 써도 ROOM/BED 단위 숙소에서는 정상으로 보인다.** 독채에서만
틀리고, 개발자가 실제 운영하는 3룸 숙소가 바로 독채(PROPERTY 단위)다.
**가장 중요한 숙소에서만 틀리는** 모양이라 눈으로는 잡히지 않는다.

`test_turnover_counts_property_unit`이 그 경우를 고정한다 — 조합 비교가
NULL을 같은 것으로 보지 않으면 **그 테스트만 실패한다.**

## 호스트를 남기지 않는다

`conftest.py`의 `host`/`make_property` 픽스처만 쓰고, 타인 호스트는
`stranger` 픽스처로 만들어 `hosts` CASCADE로 정리한다
(`test_reservations_api.py`가 `other-*` 59건 누적을 해소한 것과 같은 형태).
"""

from __future__ import annotations

import uuid
from datetime import date

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token
from app.main import app
from app.models import Bed, ChannelConnection, Host, Property, Reservation, Room
from app.models.action_item import ActionItem
from app.models.cleaning import CleaningTask
from app.models.enums import (
    ActionRiskLevel,
    ActionStatus,
    BookableUnitType,
    ReservationStatus,
    TaskStatus,
)
from app.services import dashboard_service as svc

pytestmark = pytest.mark.asyncio

TODAY = date(2026, 9, 14)
YESTERDAY = date(2026, 9, 13)
TOMORROW = date(2026, 9, 15)
TWO_DAYS_AGO = date(2026, 9, 12)

# 4.1절 JSON 예시의 키 순서 그대로. 🔴 **11이 아니라 12다**(스키마 도크스트링).
EXPECTED_FIELDS = [
    "property_id",
    "property_name",
    "today_checkin_count",
    "today_checkout_count",
    "today_turnover_count",
    "open_action_count",
    "red_now_count",
    "yellow_today_count",
    "green_auto_count",
    "cleaning_pending_count",
    "cleaning_issue_count",
    "conflict_count",
]


@pytest.fixture(scope="module")
def client():
    """⚠️ **`get_db`를 덮어쓰지 않는다.** 라우터는 앱의 공용 엔진을 그대로 쓴다.

    테스트 세션을 주입하면 `TestClient`가 자기 스레드·이벤트 루프에서
    돌기 때문에 teardown에서 asyncpg 커넥션이 닫힌 루프를 건드려
    `Event loop is closed`로 깨진다(9/14 실측). `test_reservations_api.py`가
    같은 이유로 같은 형태를 쓴다.

    **그래서 HTTP로 보는 테스트의 데이터는 반드시 커밋돼 있어야 한다** —
    `make_property` 픽스처가 커밋하므로 그대로 쓰면 된다.
    """
    with TestClient(app) as c:
        yield c


@pytest_asyncio.fixture
async def stranger(db: AsyncSession):
    """타인 호스트. **teardown에서 지운다** — `other-*` 누적을 반복하지 않는다."""
    obj = Host(
        email=f"dash-stranger-{uuid.uuid4().hex[:10]}@test.local",
        password_hash="not-a-real-hash",
        name="남의호스트",
    )
    db.add(obj)
    await db.commit()
    # rollback이 속성을 만료시키므로 id를 값으로 미리 뽑아 둔다(conftest와 동일).
    host_id = obj.host_id
    yield obj

    await db.rollback()
    stored = await db.get(Host, host_id)
    if stored is not None:
        await db.delete(stored)
        await db.commit()


def auth(host_id: int) -> dict[str, str]:
    """`create_access_token`은 **int**를 받는다(`core/security.py:141`)."""
    return {"Authorization": "Bearer " + create_access_token(host_id)}


async def _add_reservation(
    db: AsyncSession,
    *,
    prop: Property,
    conn: ChannelConnection,
    check_in: date,
    check_out: date,
    room_id: int | None = None,
    bed_id: int | None = None,
    status: ReservationStatus = ReservationStatus.CONFIRMED,
) -> Reservation:
    """서비스를 거치지 않고 직접 넣는다 — 겹침·교차 조합을 일부러 만들어야 한다."""
    r = Reservation(
        property_id=prop.property_id,
        room_id=room_id,
        bed_id=bed_id,
        channel_connection_id=conn.connection_id,
        external_uid=f"dash-{uuid.uuid4().hex[:8]}",
        check_in=check_in,
        check_out=check_out,
        reservation_status=status,
    )
    db.add(r)
    await db.flush()
    return r


async def _summary(db: AsyncSession, prop: Property, host: Host):
    return await svc.get_summary(
        db, property_id=prop.property_id, host_id=host.host_id, today=TODAY
    )


# --------------------------------------------------------------------------
# 12필드 계약
# --------------------------------------------------------------------------


async def test_response_has_exactly_twelve_fields(db, host, make_property, client):
    """🔴 4.1절 12필드가 **전부** 있고 **그것만** 있는지.

    개수만 세지 않는다 — 키 집합을 대조해야 오타난 키 하나가 잡힌다.
    """
    prop, _ = await make_property(BookableUnitType.PROPERTY)
    res = client.get(
        f"/properties/{prop.property_id}/dashboard/summary", headers=auth(host.host_id)
    )

    assert res.status_code == 200, res.text
    body = res.json()
    assert set(body) == {"data", "error"}, "봉투가 0절과 다르다"
    assert body["error"] is None
    assert list(body["data"]) == EXPECTED_FIELDS, "12필드 계약이 깨졌다"


async def test_empty_property_is_all_zero(db, host, make_property, client):
    """예약·액션·청소가 0건이면 전부 0이다. **null이 아니다.**

    `conflict_count`도 여기서는 `0`이어야 한다 — 0(충돌 없음)과
    null(계산 실패)은 다른 뜻이고, 프론트가 그 둘을 구분해 표시한다.
    """
    prop, _ = await make_property(BookableUnitType.PROPERTY)
    res = client.get(
        f"/properties/{prop.property_id}/dashboard/summary", headers=auth(host.host_id)
    )
    data = res.json()["data"]

    assert data["property_id"] == prop.property_id
    # ⚠️ 응답 키는 `property_name`인데 컬럼은 `name`이다(4.1절).
    assert data["property_name"] == prop.name
    for f in EXPECTED_FIELDS[2:]:
        assert data[f] == 0, f"{f}가 0이 아니다: {data[f]}"


# --------------------------------------------------------------------------
# 🔴 turnover — IS NOT DISTINCT FROM 이 없으면 실패하는 자리
# --------------------------------------------------------------------------


async def test_turnover_counts_property_unit(db, host, make_property):
    """🔴 **독채(PROPERTY 단위)에서 turnover가 세어지는가.**

    `room_id`·`bed_id`가 **둘 다 NULL**인 예약 두 건이다. 조합 비교가
    `NULL = NULL`(거짓)로 동작하면 **이 테스트만 실패**하고 ROOM/BED
    숙소 테스트는 전부 통과한다 — 4.1절이 `IS NOT DISTINCT FROM`을
    못박은 이유가 그것이다.
    """
    prop, conn = await make_property(BookableUnitType.PROPERTY)
    # 오늘 나가는 예약
    await _add_reservation(db, prop=prop, conn=conn, check_in=YESTERDAY, check_out=TODAY)
    # 같은 단위(독채)로 오늘 들어오는 예약
    await _add_reservation(db, prop=prop, conn=conn, check_in=TODAY, check_out=TOMORROW)

    s = await _summary(db, prop, host)

    assert s.today_checkout_count == 1
    assert s.today_checkin_count == 1
    assert s.today_turnover_count == 1, (
        "독채 turnover가 0이다 — room_id/bed_id가 NULL인 조합을 "
        "등호로 비교하고 있다(IS NOT DISTINCT FROM 필요)"
    )


async def test_turnover_counts_bed_unit(db, host, make_property):
    """같은 침대에서 당일 퇴실 + 당일 입실이면 turnover 1."""
    prop, conn = await make_property(BookableUnitType.BED)
    room = await db.scalar(select(Room).where(Room.property_id == prop.property_id))
    bed_a = (
        await db.scalar(
            select(Bed).where(Bed.room_id == room.room_id).order_by(Bed.bed_label)
        )
    ).bed_id

    await _add_reservation(
        db, prop=prop, conn=conn, room_id=room.room_id, bed_id=bed_a,
        check_in=YESTERDAY, check_out=TODAY,
    )
    await _add_reservation(
        db, prop=prop, conn=conn, room_id=room.room_id, bed_id=bed_a,
        check_in=TODAY, check_out=TOMORROW,
    )

    s = await _summary(db, prop, host)
    assert s.today_turnover_count == 1


async def test_turnover_is_not_counted_across_different_units(db, host, make_property):
    """🔴 **다른 침대면 turnover가 아니다.** 청소 압박이 생기지 않는다.

    체크인 1 · 체크아웃 1이지만 **단위가 달라** turnover는 0이다.
    이 반례가 없으면 *"오늘 체크아웃이 있으면 무조건 turnover"*로
    잘못 구현해도 위 두 테스트가 통과한다.
    """
    prop, conn = await make_property(BookableUnitType.BED)
    room = await db.scalar(select(Room).where(Room.property_id == prop.property_id))
    beds = list(
        (await db.scalars(select(Bed).where(Bed.room_id == room.room_id).order_by(Bed.bed_label))).all()
    )

    await _add_reservation(
        db, prop=prop, conn=conn, room_id=room.room_id, bed_id=beds[0].bed_id,
        check_in=YESTERDAY, check_out=TODAY,
    )
    await _add_reservation(
        db, prop=prop, conn=conn, room_id=room.room_id, bed_id=beds[1].bed_id,
        check_in=TODAY, check_out=TOMORROW,
    )

    s = await _summary(db, prop, host)
    assert s.today_checkout_count == 1
    assert s.today_checkin_count == 1
    assert s.today_turnover_count == 0, "다른 침대인데 turnover로 셌다"


# 🔴 **"건수가 아니라 단위 수"는 활성 예약으로 시험할 수 없다** (14-37 실측)
#
# 4.1절이 turnover를 *"둘 다 존재하는 **단위의 수**"*로 정의했으므로 같은
# 단위에서 오늘 2건이 나가고 2건이 들어오면 turnover가 1이어야 한다 —
# 이것을 고정하는 테스트를 쓰려다 **EXCLUDE에 막혔다**:
#
#     asyncpg.exceptions.ExclusionViolationError:
#       conflicting key value violates exclusion constraint "excl_property_overlap"
#
# 같은 단위에서 같은 날 2건이 체크아웃하려면 **둘 다 그 전에 시작해 서로
# 겹쳐야** 하는데, 활성 상태(CONFIRMED/MODIFIED)끼리의 겹침은 `excl_*`가
# 막는다. 즉 **DB가 이미 "단위당 하루 체크아웃 1건"을 보장**하고 있어
# 활성 예약만 보는 이 집계에서는 단위 수와 건수가 언제나 같다.
#
# 4.1절의 "단위의 수"라는 표현은 틀린 것이 아니라 **더 방어적인 정의**이며,
# 비활성 상태를 집계에 넣는 날 비로소 둘이 갈린다. 그때 이 테스트를 쓴다.

async def test_modified_status_is_counted(db, host, make_property):
    """🔴 `MODIFIED`도 활성이다 — `ACTIVE_STATUSES`는 **둘**이다.

    `CONFIRMED`만 세면 **기간을 변경한 예약이 대시보드에서 사라진다.**
    호스트 입장에서는 오늘 나가는 손님이 화면에 없는 것이라 가장 나쁜
    종류의 누락이다.

    ⚠️ 14-36 이전에는 저장소 어느 집계 테스트도 `MODIFIED`가 **세어지는지**를
    확인하지 않았다(상태 전이 테스트만 있었다).
    """
    prop, conn = await make_property(BookableUnitType.PROPERTY)
    await _add_reservation(db, prop=prop, conn=conn, check_in=YESTERDAY, check_out=TODAY,
                           status=ReservationStatus.MODIFIED)
    await _add_reservation(db, prop=prop, conn=conn, check_in=TODAY, check_out=TOMORROW,
                           status=ReservationStatus.MODIFIED)

    s = await _summary(db, prop, host)
    assert s.today_checkout_count == 1, "MODIFIED가 집계에서 빠졌다"
    assert s.today_checkin_count == 1, "MODIFIED가 집계에서 빠졌다"
    assert s.today_turnover_count == 1


async def test_turnover_separates_null_and_non_null_units(db, host, make_property):
    """🔴 **NULL 단위와 일반 단위가 섞여도 따로 세어진다.**

    호스텔(`BED` 단위)에 **숙소 전체 예약**(`room_id` NULL)과 **침대 예약**이
    함께 있는 경우다. iCal로 들어온 통대여 예약이 남아 있는 상황이 실제로
    이 모양이다.

        독채 단위 (NULL, NULL)  오늘 나가고 오늘 들어온다  → turnover
        침대 단위 (room, bedA)  오늘 나가기만 한다        → turnover 아님

    NULL 조합이 자기들끼리 묶이고 침대와 섞이지 않아야 **1**이 나온다.
    등호 비교면 NULL 쪽이 흩어져 **0**이 된다.
    """
    prop, conn = await make_property(BookableUnitType.BED)
    room = await db.scalar(select(Room).where(Room.property_id == prop.property_id))
    bed_a = (
        await db.scalar(
            select(Bed).where(Bed.room_id == room.room_id).order_by(Bed.bed_label)
        )
    ).bed_id

    # 숙소 전체 단위 — 오늘 나가고 오늘 들어온다
    await _add_reservation(db, prop=prop, conn=conn, check_in=YESTERDAY, check_out=TODAY)
    await _add_reservation(db, prop=prop, conn=conn, check_in=TODAY, check_out=TOMORROW)
    # 침대 단위 — 오늘 나가기만 한다(대응하는 체크인이 없다)
    await _add_reservation(db, prop=prop, conn=conn, room_id=room.room_id, bed_id=bed_a,
                           check_in=YESTERDAY, check_out=TODAY)

    s = await _summary(db, prop, host)

    assert s.today_checkout_count == 2
    assert s.today_checkin_count == 1
    assert s.today_turnover_count == 1, (
        "NULL 단위와 침대 단위가 섞였다 — NULL 조합이 자기들끼리 묶여야 한다"
    )


async def test_cancelled_reservation_is_not_counted(db, host, make_property):
    """취소·대기 예약은 오늘 집계에 들어가지 않는다(`ACTIVE_STATUSES`)."""
    prop, conn = await make_property(BookableUnitType.PROPERTY)
    await _add_reservation(
        db, prop=prop, conn=conn, check_in=TODAY, check_out=TOMORROW,
        status=ReservationStatus.CANCELLED,
    )
    await _add_reservation(
        db, prop=prop, conn=conn, check_in=TODAY, check_out=TOMORROW,
        status=ReservationStatus.PENDING,
    )

    s = await _summary(db, prop, host)
    assert s.today_checkin_count == 0


# --------------------------------------------------------------------------
# 액션 · 청소 · 충돌
# --------------------------------------------------------------------------


async def test_action_counts_group_by_risk_level(db, host, make_property):
    """`status='OPEN'`만 우선순위별로 세고, `open_action_count`는 그 합이다."""
    prop, _ = await make_property(BookableUnitType.PROPERTY)
    for level, n in (
        (ActionRiskLevel.RED_NOW, 2),
        (ActionRiskLevel.YELLOW_TODAY, 3),
        (ActionRiskLevel.GREEN_AUTO, 1),
    ):
        for _ in range(n):
            db.add(ActionItem(
                property_id=prop.property_id, risk_level=level,
                category="TEST", title="t", status=ActionStatus.OPEN,
            ))
    # 처리된 카드는 세지 않는다
    db.add(ActionItem(
        property_id=prop.property_id, risk_level=ActionRiskLevel.RED_NOW,
        category="TEST", title="resolved", status=ActionStatus.RESOLVED,
    ))
    await db.flush()

    s = await _summary(db, prop, host)
    assert (s.red_now_count, s.yellow_today_count, s.green_auto_count) == (2, 3, 1)
    assert s.open_action_count == 6, "OPEN 합이 아니다(RESOLVED가 섞였을 수 있다)"


async def test_cleaning_counts_split_pending_and_issue(db, host, make_property):
    """대기 3상태는 `pending`, `ISSUE`는 따로. 완료·검증은 어디에도 안 든다.

    ⚠️ 운영 경로에서는 `CLEANING_TASKS`에 행을 만드는 기능이 아직 없어
    항상 0이다(단계 5 소관). 여기서는 **집계 식이 맞는지**만 본다.
    """
    prop, conn = await make_property(BookableUnitType.PROPERTY)
    for st in (
        TaskStatus.PENDING, TaskStatus.ASSIGNED, TaskStatus.IN_PROGRESS,
        TaskStatus.ISSUE, TaskStatus.COMPLETED, TaskStatus.VERIFIED,
    ):
        r = await _add_reservation(
            db, prop=prop, conn=conn,
            check_in=date(2026, 10, 1), check_out=date(2026, 10, 2),
            status=ReservationStatus.CANCELLED,  # 오늘 집계를 흐리지 않게
        )
        db.add(CleaningTask(
            reservation_id=r.reservation_id, property_id=prop.property_id, task_status=st,
        ))
    await db.flush()

    s = await _summary(db, prop, host)
    assert s.cleaning_pending_count == 3
    assert s.cleaning_issue_count == 1


async def test_conflict_count_counts_cross_unit_overlap(db, host, make_property):
    """교차 충돌(객실 통째 ↔ 그 안의 침대) 2건을 센다. **null이 아니다.**"""
    prop, conn = await make_property(BookableUnitType.BED)
    room = await db.scalar(select(Room).where(Room.property_id == prop.property_id))
    bed = await db.scalar(
        select(Bed).where(Bed.room_id == room.room_id).order_by(Bed.bed_label)
    )

    await _add_reservation(
        db, prop=prop, conn=conn, room_id=room.room_id, bed_id=None,
        check_in=date(2026, 11, 1), check_out=date(2026, 11, 5),
    )
    await _add_reservation(
        db, prop=prop, conn=conn, room_id=room.room_id, bed_id=bed.bed_id,
        check_in=date(2026, 11, 3), check_out=date(2026, 11, 7),
    )

    s = await _summary(db, prop, host)
    assert s.conflict_count == 2, "충돌 쌍의 **양쪽**을 세야 한다"


async def test_conflict_failure_yields_null_and_keeps_others(
    db, host, make_property, monkeypatch
):
    """🔴 4.1절 Graceful Degradation — 계산 실패 시 `conflict_count`만 null.

    *"키는 항상 포함한다. 계산 실패 시 값을 `null`로 반환한다. 나머지 10개
    필드는 정상 값으로 반환한다."* 나머지가 0으로 뭉개지거나 500이 나면
    **대시보드 전체가 못 쓰게 된다** — 그것을 막는 테스트다.
    """
    prop, conn = await make_property(BookableUnitType.PROPERTY)
    await _add_reservation(db, prop=prop, conn=conn, check_in=TODAY, check_out=TOMORROW)

    async def boom(*a, **kw):
        raise RuntimeError("파생 필드 계산 실패")

    monkeypatch.setattr(svc, "_conflict_count", boom)

    s = await _summary(db, prop, host)
    assert s.conflict_count is None, "실패했는데 null이 아니다"
    assert s.today_checkin_count == 1, "나머지 필드까지 함께 무너졌다"
    assert s.property_name == prop.name


# --------------------------------------------------------------------------
# IDOR
# --------------------------------------------------------------------------


async def test_other_host_gets_404(db, host, make_property, stranger, client):
    """타인 소유 숙소는 **403이 아니라 404**다(코딩규칙 1번 — 정보노출 방지)."""
    prop, _ = await make_property(BookableUnitType.PROPERTY)
    res = client.get(
        f"/properties/{prop.property_id}/dashboard/summary",
        headers=auth(stranger.host_id),
    )
    assert res.status_code == 404
    assert res.json()["error"]["code"] == "RESOURCE_NOT_FOUND"


async def test_missing_property_gets_404(db, host, client):
    """없는 숙소도 같은 404다 — 부존재와 타인 소유를 구분하지 않는다."""
    res = client.get(
        "/properties/999999999/dashboard/summary", headers=auth(host.host_id)
    )
    assert res.status_code == 404
    assert res.json()["error"]["code"] == "RESOURCE_NOT_FOUND"


async def test_requires_auth(db, host, make_property, client):
    """토큰 없이는 401."""
    prop, _ = await make_property(BookableUnitType.PROPERTY)
    res = client.get(f"/properties/{prop.property_id}/dashboard/summary")
    assert res.status_code == 401
