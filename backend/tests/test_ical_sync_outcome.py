"""iCal 동기화 결과 집계 회귀 테스트.

`skipped` 하나에 성격이 다른 것들이 섞이면 **호스트가 응답을 보고
조치할 수 있는지 없는지를 구분할 수 없다.**

    이미 반영돼 있고 변경 없음   정상 — 아무것도 안 해도 된다
    객실 미지정                  구조적 — iCal이 객실을 주지 않아 못 넣는다
    기간 겹침                    r49(9/12) 미정의
    예상 못 한 오류              조사 필요
    파싱 단계에서 버려진 이벤트    피드 자체가 이상하다(다른 층)

앞의 넷은 **예약 반영 단계**, 마지막 하나는 **피드 파싱 단계**다.
층이 다르므로 이름도 나눈다.
"""

from __future__ import annotations

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import BookableUnitType
from app.services import ical_sync

FEED_URL = "https://example.test/calendar.ics"


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
    """`fetch_ical`이 만드는 AsyncClient에 고정 응답을 물린다."""
    original = httpx.AsyncClient

    def factory(*args, **kwargs):
        kwargs["transport"] = httpx.MockTransport(
            lambda req: httpx.Response(200, text=body)
        )
        return original(*args, **kwargs)

    monkeypatch.setattr(ical_sync.httpx, "AsyncClient", factory)


async def _sync(db: AsyncSession, conn, host_id: int):
    conn.ical_url = FEED_URL
    await db.commit()
    return await ical_sync.sync_connection(
        db, connection_id=conn.connection_id, host_id=host_id
    )


# ------------------------------------------------------------------ 반영 단계


@pytest.mark.asyncio
async def test_unchanged_is_counted_separately(
    db: AsyncSession, host, make_property, monkeypatch
):
    """이미 반영돼 있고 변경도 없으면 **`unchanged`**로 센다.

    이것이 `skipped`에 섞이면 정상 상태가 문제처럼 보인다.
    """
    prop, conn = await make_property(BookableUnitType.PROPERTY)
    _serve(monkeypatch, _ics(_event("evt-1@test", "20261101", "20261103")))

    _, first = await _sync(db, conn, host.host_id)
    assert first.created == 1

    _, second = await _sync(db, conn, host.host_id)

    assert second.created == 0
    assert second.updated == 0
    assert second.unchanged == 1, "변경 없음이 unchanged로 잡혀야 한다"
    assert second.skipped_no_room == 0
    assert second.skipped_overlap == 0
    assert second.failed == 0


@pytest.mark.asyncio
async def test_room_unit_property_is_counted_as_no_room(
    db: AsyncSession, host, make_property, monkeypatch
):
    """iCal은 객실을 알려주지 않는다 → ROOM 단위 숙소는 **`skipped_no_room`**.

    "조치할 수 없는 구조적 한계"라서 "이미 반영됨"과 반드시 구분돼야 한다.
    """
    prop, conn = await make_property(BookableUnitType.ROOM)
    _serve(monkeypatch, _ics(_event("evt-room@test", "20261201", "20261203")))

    _, outcome = await _sync(db, conn, host.host_id)

    assert outcome.created == 0
    assert outcome.unchanged == 0
    assert outcome.skipped_no_room == 1, "객실 미지정이 전용 카운터에 잡혀야 한다"
    assert outcome.skipped_overlap == 0
    assert outcome.failed == 0


# ------------------------------------------------------------------ 파싱 단계


def test_invalid_events_are_reported():
    """필수 필드가 없거나 종료<=시작인 이벤트 수를 **`invalid_events`**로 올린다.

    피드에 10건이 있고 3건이 버려지면 호스트는 7건만 보게 된다 —
    **버려진 3건이 응답 어디에도 나타나지 않으면 피드가 이상한 줄 모른다.**
    """
    feed = _ics(
        "BEGIN:VEVENT\nUID:no-dates@test\nSUMMARY:날짜 없음\nEND:VEVENT",
        "BEGIN:VEVENT\nUID:backwards@test\n"
        "DTSTART;VALUE=DATE:20261120\nDTEND;VALUE=DATE:20261118\nEND:VEVENT",
        _event("good@test", "20261125", "20261127"),
    )

    parsed = ical_sync.parse_ical(feed)

    assert [e.uid for e in parsed.events] == ["good@test"]
    assert parsed.invalid_count == 2, "버려진 이벤트 수가 보고돼야 한다"


@pytest.mark.asyncio
async def test_invalid_events_reach_sync_outcome(
    db: AsyncSession, host, make_property, monkeypatch
):
    """파싱에서 버려진 건수가 **동기화 결과까지** 올라온다."""
    prop, conn = await make_property(BookableUnitType.PROPERTY)
    _serve(
        monkeypatch,
        _ics(
            "BEGIN:VEVENT\nUID:broken@test\nSUMMARY:날짜 없음\nEND:VEVENT",
            _event("ok@test", "20261210", "20261212"),
        ),
    )

    _, outcome = await _sync(db, conn, host.host_id)

    assert outcome.created == 1
    assert outcome.invalid_events == 1, "버려진 이벤트가 응답에 나타나야 한다"
