"""iCal 파싱·가져오기 회귀 테스트 (CLAUDE.md 코딩 규칙 11).

iCal은 이 프로젝트의 **유일한 Real 외부연동**이라 장애 전파 방지가
특히 중요하다. 여기서 고정하는 것은 세 가지다.

1. 깨진 `.ics`가 와도 예외가 `IcalSyncError` 하나로 좁혀진다
2. 응답하지 않는 URL이 타임아웃 안에 끊긴다
3. `last_error_message`에 URL·스택트레이스가 섞이지 않는다

네트워크는 `httpx.MockTransport`로 대신한다 — 실제 서버에 의존하면
테스트가 환경에 따라 흔들린다. 실제 서버(`tools/ical-test-server`)를
쓴 검증은 devlog에 실측으로 남긴다.
"""

from __future__ import annotations

import httpx
import pytest

from app.services import ical_sync
from app.services.ical_sync import IcalSyncError, fetch_ical, parse_ical

SECRET_URL = "https://www.airbnb.com/calendar/ical/12345678.ics?s=abc1234567890"

VALID_ICS = "\r\n".join(
    [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//test//test//EN",
        "BEGIN:VEVENT",
        "UID:reservation-001@test",
        "DTSTART;VALUE=DATE:20260903",
        "DTEND;VALUE=DATE:20260906",
        "SUMMARY:Reserved - Hong Gildong",
        "END:VEVENT",
        "END:VCALENDAR",
        "",
    ]
)


# ---------------------------------------------------------------- 파싱


def test_parse_valid_ics():
    events = parse_ical(VALID_ICS)

    assert len(events) == 1
    assert events[0].uid == "reservation-001@test"
    assert str(events[0].check_in) == "2026-09-03"
    assert str(events[0].check_out) == "2026-09-06"


def test_parse_accepts_datetime_form():
    """iCal은 같은 필드를 DATE로도 DATE-TIME으로도 보낸다.

    에어비앤비는 DATE, 테스트 서버는 DATE-TIME을 쓴다. RESERVATIONS의
    check_in/check_out은 DATE라 일시는 날짜 부분만 취해야 한다.
    """
    ics = VALID_ICS.replace(
        "DTSTART;VALUE=DATE:20260903", "DTSTART:20260903T150000"
    ).replace("DTEND;VALUE=DATE:20260906", "DTEND:20260906T110000")

    events = parse_ical(ics)

    assert str(events[0].check_in) == "2026-09-03"
    assert str(events[0].check_out) == "2026-09-06"


@pytest.mark.parametrize(
    "raw",
    [
        "이건 iCal이 아니다",
        '{"json": true}',
        "BEGIN:GARBAGE\r\nEND:GARBAGE\r\n",
        "",
    ],
)
def test_parse_broken_raises_only_ical_sync_error(raw):
    """깨진 입력은 전부 IcalSyncError 하나로 좁혀진다(호출부가 빠뜨릴 여지 없게)."""
    with pytest.raises(IcalSyncError):
        parse_ical(raw)


def test_parse_skips_bad_events_but_keeps_good_ones():
    """이벤트 1건의 문제로 캘린더 전체를 잃지 않는다.

    남의 서버가 보낸 이벤트 하나 때문에 우리 동기화가 통째로 막히면 안 된다.
    """
    ics = "\r\n".join(
        [
            "BEGIN:VCALENDAR",
            "VERSION:2.0",
            "PRODID:-//test//test//EN",
            # 날짜 없음
            "BEGIN:VEVENT",
            "UID:no-dates@test",
            "SUMMARY:날짜 없음",
            "END:VEVENT",
            # 종료가 시작보다 빠름
            "BEGIN:VEVENT",
            "UID:backwards@test",
            "DTSTART;VALUE=DATE:20260920",
            "DTEND;VALUE=DATE:20260918",
            "END:VEVENT",
            # 정상
            "BEGIN:VEVENT",
            "UID:good@test",
            "DTSTART;VALUE=DATE:20260925",
            "DTEND;VALUE=DATE:20260927",
            "SUMMARY:Reserved - 정상",
            "END:VEVENT",
            "END:VCALENDAR",
            "",
        ]
    )

    events = parse_ical(ics)

    assert [e.uid for e in events] == ["good@test"]


def test_parse_truncates_to_column_limits():
    """external_uid VARCHAR(150) / guest_name VARCHAR(100)을 넘기지 않는다."""
    ics = VALID_ICS.replace("reservation-001@test", "u" * 300).replace(
        "Reserved - Hong Gildong", "s" * 300
    )

    event = parse_ical(ics)[0]

    assert len(event.uid) == 150
    assert len(event.summary) == 100


# ---------------------------------------------------------------- 가져오기


@pytest.mark.asyncio
async def test_fetch_timeout_is_reported_safely(monkeypatch):
    """응답하지 않는 URL은 타임아웃으로 끊고, 메시지에 URL을 담지 않는다."""

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("timed out", request=request)

    _patch_transport(monkeypatch, handler)

    with pytest.raises(IcalSyncError) as exc:
        await fetch_ical(SECRET_URL, timeout=5.0)

    assert "timeout 5s" in str(exc.value)
    assert SECRET_URL not in str(exc.value)
    assert "abc1234567890" not in str(exc.value)


@pytest.mark.asyncio
async def test_fetch_http_error_is_reported_safely(monkeypatch):
    _patch_transport(monkeypatch, lambda req: httpx.Response(404, text="Not Found"))

    with pytest.raises(IcalSyncError) as exc:
        await fetch_ical(SECRET_URL)

    assert "HTTP 404" in str(exc.value)
    assert SECRET_URL not in str(exc.value)


@pytest.mark.asyncio
async def test_fetch_connect_error_is_reported_safely(monkeypatch):
    """연결 거부·DNS 실패는 원문에 호스트명이 섞이므로 고정 문구로 바꾼다."""

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("[Errno 111] Connection refused", request=request)

    _patch_transport(monkeypatch, handler)

    with pytest.raises(IcalSyncError) as exc:
        await fetch_ical(SECRET_URL)

    assert "airbnb.com" not in str(exc.value)
    assert "Errno" not in str(exc.value)


@pytest.mark.asyncio
async def test_fetch_rejects_oversized_body(monkeypatch):
    """타임아웃만으로는 '느리게 계속 보내는' 서버를 못 막는다."""
    huge = b"x" * (ical_sync.ICAL_MAX_BYTES + 1)
    _patch_transport(monkeypatch, lambda req: httpx.Response(200, content=huge))

    with pytest.raises(IcalSyncError) as exc:
        await fetch_ical(SECRET_URL)

    assert "너무 큽니다" in str(exc.value)


@pytest.mark.asyncio
async def test_fetch_success(monkeypatch):
    _patch_transport(monkeypatch, lambda req: httpx.Response(200, text=VALID_ICS))

    body = await fetch_ical(SECRET_URL)

    assert "BEGIN:VCALENDAR" in body


def _patch_transport(monkeypatch, handler):
    """`fetch_ical`이 만드는 AsyncClient에 MockTransport를 끼운다."""
    original = httpx.AsyncClient

    def factory(*args, **kwargs):
        kwargs["transport"] = httpx.MockTransport(handler)
        return original(*args, **kwargs)

    monkeypatch.setattr(ical_sync.httpx, "AsyncClient", factory)


def test_empty_calendar_is_valid_not_an_error():
    """이벤트가 없는 VCALENDAR는 "예약이 없는 숙소"라 정상이다.

    `BEGIN:GARBAGE`처럼 캘린더가 아닌 응답과 반드시 구분돼야 한다 —
    구분하지 않으면 깨진 피드가 예약 0건으로 보여 SYNCED로 기록된다.
    """
    empty = "\r\n".join(
        ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//test//test//EN", "END:VCALENDAR", ""]
    )

    assert parse_ical(empty) == []
