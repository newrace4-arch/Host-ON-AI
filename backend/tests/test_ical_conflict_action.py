"""r49 — iCal 동기화 충돌 감지 시 CONFLICT ActionItem 발행 (2026-09-13).

### 왜 카드가 필요한가

겹쳐서 반영하지 못한 이벤트는 **어디에도 남지 않았다.** `RESERVATIONS`에는
EXCLUDE 3종 때문에 넣을 수 없고, 동기화 응답의 `skipped_overlap_count`는
응답이 화면을 떠나면 사라진다. 호스트는 **더블부킹이 났다는 사실 자체를
모른 채** 지나간다.

### `conflict_count`와는 다른 숫자다

대시보드의 `conflict_count`는 *"`is_conflict = true`인 **예약** 수"*이며
`RESERVATIONS`만 본다(api_contract 4.1절). **저장되지 못한 iCal 이벤트는
거기 잡히지 않는다.** 이 카드가 올리는 것은 `open_action_count`와
`red_now_count`다 — 아래 마지막 테스트가 그 사실을 회귀로 고정한다.
"""

from __future__ import annotations

import httpx
import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.action_item import ActionItem
from app.models.channel import ChannelConnection
from app.models.enums import (
    ActionRiskLevel,
    ActionStatus,
    BookableUnitType,
    Channel,
)
from app.models.property import Room
from app.models.reservation import Reservation
from app.services import ical_sync

FEED_URL = "https://example.test/calendar.ics"


# ---------------------------------------------------------------------------
# 지역 헬퍼 — test_ical_sync_outcome.py와 같은 형태를 쓴다(conftest는 고치지 않는다)
# ---------------------------------------------------------------------------


def _ics(*events: str) -> str:
    body = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//test//test//EN"]
    for e in events:
        body.extend(e.split("\n"))
    body += ["END:VCALENDAR", ""]
    return "\r\n".join(body)


def _event(uid: str, start: str, end: str, summary: str = "Reserved") -> str:
    return "\n".join(
        [
            "BEGIN:VEVENT",
            f"UID:{uid}",
            f"DTSTART;VALUE=DATE:{start}",
            f"DTEND;VALUE=DATE:{end}",
            f"SUMMARY:{summary}",
            "END:VEVENT",
        ]
    )


def _serve(monkeypatch, body: str):
    original = httpx.AsyncClient

    def factory(*args, **kwargs):
        kwargs["transport"] = httpx.MockTransport(
            lambda req: httpx.Response(200, text=body)
        )
        return original(*args, **kwargs)

    monkeypatch.setattr(ical_sync.httpx, "AsyncClient", factory)


async def _sync(db: AsyncSession, connection_id: int, host_id: int):
    """⚠️ **연결을 ORM 객체가 아니라 id로 받는다.**

    동기화 중 겹침이 나면 `ical_sync`가 `rollback()`을 하는데, 롤백은
    세션의 **모든** 인스턴스를 만료시킨다. 그 뒤 호출부가 들고 있던
    객체는 속성을 읽기만 해도 지연로딩(동기 IO)이 걸려 async 컨텍스트
    에서 `MissingGreenlet`이 난다(conftest.py 27~33행이 같은 이유로
    id를 미리 뽑아둔다). 이 파일은 **겹침을 일부러 만드는** 테스트라
    그 상황을 매번 밟는다. 그래서 매 호출마다 id로 다시 읽는다.

    운영에서는 요청마다 세션이 새로 열리므로 이 문제가 없다 —
    한 세션으로 동기화를 여러 번 부르는 것은 테스트뿐이다.
    """
    conn = await db.get(ChannelConnection, connection_id)
    assert conn is not None
    conn.ical_url = FEED_URL
    await db.commit()
    return await ical_sync.sync_connection(
        db, connection_id=connection_id, host_id=host_id
    )


async def _second_connection(
    db: AsyncSession, property_id: int, *, room_id: int | None = None
) -> ChannelConnection:
    """같은 숙소의 **다른 채널** 연결. 더블부킹은 채널이 둘일 때 생긴다."""
    conn = ChannelConnection(
        property_id=property_id,
        channel=Channel.BOOKING_COM,
        room_id=room_id,
        ical_url=FEED_URL,
    )
    db.add(conn)
    await db.commit()
    await db.refresh(conn)
    return conn


async def _conflict_cards(db: AsyncSession, property_id: int) -> list[ActionItem]:
    return list(
        (
            await db.scalars(
                select(ActionItem).where(
                    ActionItem.property_id == property_id,
                    ActionItem.category == ical_sync.CONFLICT_CATEGORY,
                )
            )
        ).all()
    )


# ---------------------------------------------------------------------------
# 1. 다른 채널이 같은 단위를 겹치게 예약 → CONFLICT 카드
# ---------------------------------------------------------------------------


async def test_overlapping_event_creates_conflict_card(
    db: AsyncSession, host, make_property, monkeypatch
):
    """에어비앤비로 들어온 예약 위에 부킹닷컴 예약이 겹치면 카드가 생긴다.

    **반영은 하지 않는다**(EXCLUDE 때문에 넣을 수도 없다). 달라진 것은
    *이유를 버리지 않는다*는 점이다.
    """
    prop, conn_a = await make_property(BookableUnitType.PROPERTY)
    # 겹침 롤백이 인스턴스를 만료시키므로 id를 값으로 먼저 붙잡는다(_sync 참고)
    pid, host_id = prop.property_id, host.host_id
    _serve(monkeypatch, _ics(_event("a-1@test", "20261101", "20261105")))
    _, first = await _sync(db, conn_a.connection_id, host_id)
    assert first.created == 1

    conn_b = await _second_connection(db, pid)
    _serve(monkeypatch, _ics(_event("b-1@test", "20261103", "20261107")))
    _, second = await _sync(db, conn_b.connection_id, host_id)

    # 반영되지 않았고, 겹침으로 집계됐다
    assert second.created == 0
    assert second.skipped_overlap == 1
    assert second.failed == 0

    cards = await _conflict_cards(db, pid)
    assert len(cards) == 1

    card = cards[0]
    assert card.risk_level is ActionRiskLevel.RED_NOW
    assert card.status is ActionStatus.OPEN
    # 🔴 복합 FK (reservation_id, property_id) — 둘 다 채워져야 한다
    assert card.property_id == pid
    assert card.reservation_id is not None

    # reservation_id는 **충돌 상대(기존 예약)**를 가리킨다. 새 이벤트는
    #   저장되지 못해 id 자체가 없다.
    existing = await db.scalar(
        select(Reservation).where(Reservation.external_uid == "a-1@test")
    )
    assert card.reservation_id == existing.reservation_id


# ---------------------------------------------------------------------------
# 2. 같은 충돌로 두 번 동기화 → 카드는 하나
# ---------------------------------------------------------------------------


async def test_repeated_sync_does_not_duplicate_card(
    db: AsyncSession, host, make_property, monkeypatch
):
    """`ACTION_ITEMS`에는 UNIQUE가 없다 — **애플리케이션 idempotency**로 막는다.

    `(reservation_id, category, status='OPEN')`이 이미 있으면 만들지 않는다
    (db_spec 2.15절). 수동 새로고침을 연타할 수 있고 쿨다운이 없으므로,
    이것이 없으면 누를 때마다 카드가 쌓인다.
    """
    prop, conn_a = await make_property(BookableUnitType.PROPERTY)
    pid, host_id = prop.property_id, host.host_id
    _serve(monkeypatch, _ics(_event("a-2@test", "20261201", "20261205")))
    await _sync(db, conn_a.connection_id, host_id)

    conn_b_id = (await _second_connection(db, pid)).connection_id
    _serve(monkeypatch, _ics(_event("b-2@test", "20261203", "20261207")))

    await _sync(db, conn_b_id, host_id)
    await _sync(db, conn_b_id, host_id)
    await _sync(db, conn_b_id, host_id)

    cards = await _conflict_cards(db, pid)
    assert len(cards) == 1, "세 번 동기화해도 카드는 하나여야 한다"


# ---------------------------------------------------------------------------
# 3. RESOLVED 뒤 다시 동기화 → 새로 생긴다 (의도된 설계)
# ---------------------------------------------------------------------------


async def test_resolved_card_is_recreated_while_source_remains(
    db: AsyncSession, host, make_property, monkeypatch
):
    """🔴 호스트가 카드를 닫아도 **소스가 그대로면 다시 만들어진다.**

    충돌은 우리 DB에서 해소되는 것이 아니라 **호스트가 OTA 한쪽을 취소해야**
    끝난다. 닫았다고 영영 사라지게 두면 **진짜 더블부킹이 화면에서 지워진다.**
    idempotency 키에 `status='OPEN'`이 들어간 것이 이 판단의 구현이다
    (문서에 규정이 없어 r49에서 정했다).
    """
    prop, conn_a = await make_property(BookableUnitType.PROPERTY)
    pid, host_id = prop.property_id, host.host_id
    _serve(monkeypatch, _ics(_event("a-3@test", "20270101", "20270105")))
    await _sync(db, conn_a.connection_id, host_id)

    conn_b_id = (await _second_connection(db, pid)).connection_id
    _serve(monkeypatch, _ics(_event("b-3@test", "20270103", "20270107")))
    await _sync(db, conn_b_id, host_id)

    cards = await _conflict_cards(db, pid)
    assert len(cards) == 1

    # 호스트가 처리 완료로 닫는다
    cards[0].status = ActionStatus.RESOLVED
    await db.commit()

    # 소스(OTA 양쪽 예약)는 그대로인 채 다시 동기화
    await _sync(db, conn_b_id, host_id)

    all_cards = await _conflict_cards(db, pid)
    assert len(all_cards) == 2, "RESOLVED 뒤에는 새 카드가 생겨야 한다"
    open_cards = [c for c in all_cards if c.status is ActionStatus.OPEN]
    assert len(open_cards) == 1


# ---------------------------------------------------------------------------
# 4. ROOM 단위 숙소는 겹침 판정에 도달하지 못한다 → 카드도 없다
# ---------------------------------------------------------------------------


async def test_room_unit_property_produces_no_conflict_card(
    db: AsyncSession, host, make_property, monkeypatch
):
    """🔴 CONFLICT 카드는 **PROPERTY 단위 숙소에서만** 발행된다.

    오늘 `CHANNEL_CONNECTIONS.room_id`가 생겼지만(③번 revision + 숙소 API),
    `ical_sync`는 **아직 그 값을 쓰지 않는다** — `_to_create_request`가
    room_id/bed_id를 항상 None으로 둔다. 그래서 ROOM 단위 숙소의 이벤트는
    계층 검증(`INVALID_UNIT_HIERARCHY`)에서 먼저 걸려 `skipped_no_room`이
    되고, **겹침 판정 자리까지 가지도 못한다.**

    연결에 객실을 지정해도 마찬가지다. 반영 경로가 연결의 room_id를 읽지
    않기 때문이다.

    이 한계를 회귀로 고정해 둔다. room_id를 반영 경로에 잇는 것은 r49와
    별개의 작업이고, 그 작업을 하면 **이 테스트가 먼저 빨개져야 한다** —
    그때 r49의 카드 발행 범위도 함께 다시 봐야 하기 때문이다.
    """
    prop, conn_a = await make_property(BookableUnitType.ROOM)
    pid, host_id = prop.property_id, host.host_id
    room_101 = await db.scalar(select(Room).where(Room.property_id == pid))
    room_102 = Room(property_id=pid, room_name="102호")
    db.add(room_102)
    await db.commit()
    await db.refresh(room_102)
    # 아래 동기화가 롤백을 하므로 id를 값으로 붙잡는다(_sync 도크스트링 참고)
    room_102_id = room_102.room_id
    conn_a_id = conn_a.connection_id

    # 연결에 객실을 지정한다 — 그래도 반영되지 않는다는 것이 요지다
    conn_a.room_id = room_101.room_id
    await db.commit()
    _serve(monkeypatch, _ics(_event("r101@test", "20270201", "20270205")))
    _, first = await _sync(db, conn_a_id, host_id)
    assert first.created == 0
    assert first.skipped_no_room == 1, "연결의 room_id는 반영 경로가 읽지 않는다"

    # 다른 객실 · 같은 기간 — 겹침으로 집계되지 않는다(애초에 예약이 없다)
    conn_b = await _second_connection(db, pid, room_id=room_102_id)
    _serve(monkeypatch, _ics(_event("r102@test", "20270201", "20270205")))
    _, second = await _sync(db, conn_b.connection_id, host_id)

    assert second.skipped_no_room == 1
    assert second.skipped_overlap == 0
    assert second.created == 0

    # 겹침이 아니므로 카드도 없다
    assert await _conflict_cards(db, pid) == []


# ---------------------------------------------------------------------------
# 5. conflict_count는 올라가지 않는다 — 두 숫자가 다르다는 것을 고정한다
# ---------------------------------------------------------------------------


async def test_card_does_not_change_reservation_conflict_count(
    db: AsyncSession, host, make_property, monkeypatch
):
    """🔴 대시보드 `conflict_count`는 **`RESERVATIONS` 기반**이라 그대로다.

    api_contract 4.1절: *"`is_conflict = true`인 **예약** 수"*. 저장되지 못한
    iCal 이벤트는 예약 행이 없으므로 그 숫자에 잡히지 않는다. 카드가 올리는
    것은 `open_action_count`·`red_now_count`다.

    이 구분이 흐려지면 *"카드를 만들었으니 conflict_count가 오르겠지"*라는
    잘못된 전제로 대시보드를 구현하게 된다.
    """
    prop, conn_a = await make_property(BookableUnitType.PROPERTY)
    pid, host_id = prop.property_id, host.host_id
    _serve(monkeypatch, _ics(_event("a-5@test", "20270301", "20270305")))
    await _sync(db, conn_a.connection_id, host_id)

    reservations_before = await db.scalar(
        select(func.count())
        .select_from(Reservation)
        .where(Reservation.property_id == pid)
    )

    conn_b = await _second_connection(db, pid)
    _serve(monkeypatch, _ics(_event("b-5@test", "20270303", "20270307")))
    await _sync(db, conn_b.connection_id, host_id)

    reservations_after = await db.scalar(
        select(func.count())
        .select_from(Reservation)
        .where(Reservation.property_id == pid)
    )

    # 예약은 늘지 않았다 — conflict_count의 분모가 그대로다
    assert reservations_after == reservations_before

    # 대신 OPEN 액션이 생겼다(open_action_count / red_now_count의 소스)
    open_red = await db.scalar(
        select(func.count())
        .select_from(ActionItem)
        .where(
            ActionItem.property_id == pid,
            ActionItem.status == ActionStatus.OPEN,
            ActionItem.risk_level == ActionRiskLevel.RED_NOW,
        )
    )
    assert open_red == 1
