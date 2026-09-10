"""iCal 동기화 — 이 프로젝트의 **유일한 Real 외부연동**.

OTA(에어비앤비 등) 공식 메시징·가격 API는 이번 범위 밖이고 전부 Mock이다.
캘린더 동기화만 실제 외부 호출을 한다. 그래서 **장애 전파 방지가 특히
중요하다** — 남의 서버가 느리거나 깨진 데이터를 보내도 우리 백엔드가
같이 죽으면 안 된다(CLAUDE.md 코딩 규칙 11).

방어는 세 겹이다.

1. **타임아웃 5초** — 연결·읽기 전부 포함. 응답하지 않는 URL이 요청
   스레드를 붙잡지 못하게 한다.
2. **응답 크기 상한** — 무한정 흘려보내는 서버가 메모리를 먹지 못하게
   한다. 타임아웃만으로는 "느리게 계속 보내는" 경우를 못 막는다.
3. **모든 실패를 `IcalSyncError` 하나로 좁힌다** — 호출부가 잡아야 할
   예외가 하나라 빠뜨릴 여지가 없다. 파싱 실패든 네트워크 실패든
   기존 캘린더 상태는 그대로 두고 사유만 기록한다(Graceful Degradation).

### `last_error_message`에 무엇을 넣는가

api_contract.md 3절: **스택트레이스나 내부 URL을 넣지 않는다**(정보노출
방지). iCal URL은 그 자체가 자격증명이라 특히 그렇다. 그래서 예외 메시지는
사람이 읽을 수 있는 한 줄로 고정하고, 원문 예외는 서버 로그로만 남긴다.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, datetime, timezone

import httpx
from icalendar import Calendar
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import InvalidUnitHierarchyError, ReservationOverlapError
from app.models.channel import ChannelConnection
from app.models.enums import SyncStatus
from app.models.reservation import Reservation
from app.schemas.reservation import ReservationCreateRequest
from app.services.channel_service import get_owned_connection
from app.services.reservation_service import create_reservation

logger = logging.getLogger(__name__)

# 코딩 규칙 11: 최대 5초. connect/read/write/pool 전부에 적용된다.
ICAL_TIMEOUT_SECONDS = 5.0

# 응답 크기 상한(바이트). 1년치 예약 캘린더도 수백 KB를 넘지 않는다.
ICAL_MAX_BYTES = 2 * 1024 * 1024


class IcalSyncError(Exception):
    """iCal 가져오기·파싱 실패. **메시지는 그대로 저장돼 호스트에게 보인다.**

    그래서 URL·스택트레이스·내부 경로를 담지 않는다. 원문 예외는
    `__cause__`로만 붙여 서버 로그에 남긴다.
    """


@dataclass(frozen=True)
class IcalEvent:
    """iCal VEVENT 1건에서 예약 반영에 필요한 것만 뽑은 값."""

    uid: str
    check_in: date
    check_out: date
    summary: str | None


def _to_date(value: object) -> date | None:
    """DTSTART/DTEND를 `date`로 정규화한다.

    iCal은 같은 필드를 날짜(`VALUE=DATE`)로도 일시(`DATE-TIME`)로도 보낸다.
    에어비앤비는 날짜로, 테스트 서버는 일시로 보낸다. RESERVATIONS의
    `check_in`/`check_out`은 DATE이므로 일시는 날짜 부분만 취한다.
    """
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return None


def parse_ical(raw: str | bytes) -> list[IcalEvent]:
    """.ics 텍스트 → 이벤트 목록. 형식이 깨져 있으면 `IcalSyncError`.

    개별 이벤트가 이상한 경우(UID 없음, 날짜 없음, 종료<=시작)는 **그 건만
    건너뛴다.** 한 건 때문에 캘린더 전체를 실패로 만들면, 남의 서버가 보낸
    이벤트 하나가 우리 동기화를 통째로 막게 된다.
    """
    try:
        cal = Calendar.from_ical(raw)
    except Exception as exc:
        logger.warning("iCal 파싱 실패", exc_info=exc)
        raise IcalSyncError("iCal 형식이 올바르지 않습니다(파싱 실패)") from exc

    # 루트가 VCALENDAR인지 확인한다. `BEGIN:GARBAGE`처럼 iCal 문법은 맞지만
    #   캘린더가 아닌 응답도 from_ical()을 통과하기 때문이다. 이걸 걸러내지
    #   않으면 **예약 0건과 구분되지 않아** 깨진 피드가 SYNCED로 기록된다.
    #   (이벤트가 없는 VCALENDAR는 "예약이 없는 숙소"라 정상이다.)
    if getattr(cal, "name", None) != "VCALENDAR":
        logger.warning("iCal 루트 컴포넌트가 VCALENDAR가 아니다: %r", getattr(cal, "name", None))
        raise IcalSyncError("iCal 형식이 올바르지 않습니다(캘린더가 아님)")

    events: list[IcalEvent] = []
    skipped = 0

    for component in cal.walk("VEVENT"):
        try:
            uid = component.get("UID")
            start = _to_date(getattr(component.get("DTSTART"), "dt", None))
            end = _to_date(getattr(component.get("DTEND"), "dt", None))
            summary = component.get("SUMMARY")

            if uid is None or start is None or end is None or end <= start:
                skipped += 1
                continue

            events.append(
                IcalEvent(
                    uid=str(uid)[:150],  # RESERVATIONS.external_uid VARCHAR(150)
                    check_in=start,
                    check_out=end,
                    summary=str(summary)[:100] if summary is not None else None,
                )
            )
        except Exception as exc:  # 이벤트 1건의 문제로 전체를 잃지 않는다
            skipped += 1
            logger.warning("iCal 이벤트 1건 건너뜀", exc_info=exc)

    if skipped:
        logger.info("iCal 이벤트 %d건을 건너뛰었다(필수 필드 누락 또는 형식 오류)", skipped)

    return events


async def fetch_ical(url: str, *, timeout: float = ICAL_TIMEOUT_SECONDS) -> str:
    """iCal URL을 가져온다. 모든 실패를 `IcalSyncError`로 좁힌다.

    ⚠️ 예외 메시지에 `url`을 넣지 않는다 — 그대로 `last_error_message`에
    저장돼 화면·로그에 노출된다(3절 정보노출 방지).
    """
    try:
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(timeout), follow_redirects=True
        ) as client:
            response = await client.get(url)
            response.raise_for_status()

            body = response.content
            if len(body) > ICAL_MAX_BYTES:
                raise IcalSyncError(
                    f"iCal 응답이 너무 큽니다(상한 {ICAL_MAX_BYTES // 1024}KB)"
                )
            return body.decode("utf-8", errors="replace")

    except IcalSyncError:
        raise
    except httpx.TimeoutException as exc:
        logger.warning("iCal 요청 타임아웃", exc_info=exc)
        raise IcalSyncError(f"iCal URL 응답 없음(timeout {timeout:g}s)") from exc
    except httpx.HTTPStatusError as exc:
        status = exc.response.status_code
        logger.warning("iCal 응답 오류 status=%s", status, exc_info=exc)
        raise IcalSyncError(f"iCal URL이 오류를 반환했습니다(HTTP {status})") from exc
    except httpx.InvalidURL as exc:
        logger.warning("iCal URL 형식 오류", exc_info=exc)
        raise IcalSyncError("iCal URL 형식이 올바르지 않습니다") from exc
    except httpx.HTTPError as exc:
        # 연결 거부·DNS 실패·SSL 오류 등. 원문에 호스트명이 섞이므로
        #   메시지를 그대로 쓰지 않고 고정 문구로 바꾼다.
        logger.warning("iCal 연결 실패", exc_info=exc)
        raise IcalSyncError("iCal URL에 연결할 수 없습니다") from exc
    except Exception as exc:
        # 예상 못 한 예외도 여기서 멈춘다 — 백엔드가 죽지 않게 하는 것이
        #   이 함수의 존재 이유다(규칙 11).
        logger.exception("iCal 가져오기 중 예상치 못한 오류")
        raise IcalSyncError("iCal 동기화 중 알 수 없는 오류가 발생했습니다") from exc


async def fetch_and_parse(
    url: str, *, timeout: float = ICAL_TIMEOUT_SECONDS
) -> list[IcalEvent]:
    """가져오기 + 파싱. 실패는 전부 `IcalSyncError` 하나로 올라온다."""
    return parse_ical(await fetch_ical(url, timeout=timeout))


# ===========================================================================
# 동기화 적용 — 파싱 결과를 RESERVATIONS에 반영한다
# ===========================================================================


@dataclass
class SyncOutcome:
    """동기화 1회의 결과. 호스트가 "무엇을 했는지" 알 수 있어야 한다."""

    created: int = 0
    updated: int = 0
    skipped: int = 0
    error: str | None = None


def _to_create_request(
    conn: "ChannelConnection", event: IcalEvent
) -> "ReservationCreateRequest":
    """iCal 이벤트 → 예약 생성 요청.

    iCal 피드는 **객실/침대를 알려주지 않는다.** 그래서 room_id/bed_id는
    항상 None이고, 결과적으로 `bookable_unit_type=PROPERTY`인 숙소만
    자동 반영된다. ROOM/BED 단위 숙소는 계층 검증에서 걸러져 skipped로
    집계된다(아래 sync_connection 참고).
    """
    return ReservationCreateRequest(
        property_id=conn.property_id,
        channel_connection_id=conn.connection_id,
        external_uid=event.uid,
        guest_name=event.summary,
        check_in=event.check_in,
        check_out=event.check_out,
    )


async def _apply_event(
    db: "AsyncSession", conn: "ChannelConnection", host_id: int, event: IcalEvent
) -> str:
    """이벤트 1건을 반영한다. 반환값은 'created' / 'updated' / 'skipped'.

    **이벤트마다 독립적으로 커밋한다.** 한 건이 실패해도 앞서 반영한
    예약이 함께 사라지지 않게 하기 위함이다(Graceful Degradation).
    """
    existing = await db.scalar(
        select(Reservation).where(
            Reservation.channel_connection_id == conn.connection_id,
            Reservation.external_uid == event.uid,
        )
    )

    if existing is not None:
        # 이미 반영된 예약 — 기간·게스트명이 바뀌었을 때만 갱신한다.
        #   UNIQUE(channel_connection_id, external_uid)가 멱등성 키다.
        changed = (
            existing.check_in != event.check_in
            or existing.check_out != event.check_out
            or existing.guest_name != event.summary
        )
        if not changed:
            return "skipped"

        existing.check_in = event.check_in
        existing.check_out = event.check_out
        existing.guest_name = event.summary
        await db.commit()
        return "updated"

    await create_reservation(
        db, host_id=host_id, payload=_to_create_request(conn, event)
    )
    await db.commit()
    return "created"


async def sync_connection(
    db: "AsyncSession", *, connection_id: int, host_id: int
) -> tuple["ChannelConnection", SyncOutcome]:
    """수동 동기화 1회. 실패해도 **기존 캘린더 상태를 그대로 둔다.**

    피드에서 사라진 예약을 삭제하지 않는다 — 취소 반영은 별도 판단이
    필요하고(취소인지 일시적 피드 오류인지 구분 불가), 잘못 지우면 복구가
    어렵다. 오늘 범위는 추가·갱신까지다.

    겹침 처리는 **오늘 범위 밖이다**(r49, 9/12). iCal 동기화 중 충돌이
    났을 때 건너뛸지 전체를 실패로 볼지가 어느 문서에도 정의돼 있지
    않다. 지금은 그 건만 skipped로 세고 넘어간다.
    """
    conn = await get_owned_connection(db, connection_id, host_id)
    outcome = SyncOutcome()

    if not conn.ical_url:
        return await _mark_failed(db, conn, "iCal URL이 등록되지 않았습니다", outcome)

    try:
        events = await fetch_and_parse(conn.ical_url)
    except IcalSyncError as exc:
        return await _mark_failed(db, conn, str(exc), outcome)

    for event in events:
        try:
            result = await _apply_event(db, conn, host_id, event)
            setattr(outcome, result, getattr(outcome, result) + 1)
        except (ReservationOverlapError, InvalidUnitHierarchyError) as exc:
            # 겹침: r49(9/12)에서 다룬다. 계층: iCal이 객실/침대를 주지 않아
            #   ROOM/BED 단위 숙소는 자동 반영 대상이 아니다.
            outcome.skipped += 1
            logger.info("iCal 이벤트 반영 건너뜀 uid=%s: %s", event.uid, exc)
            await db.rollback()
        except Exception as exc:
            outcome.skipped += 1
            logger.warning("iCal 이벤트 반영 실패 uid=%s", event.uid, exc_info=exc)
            await db.rollback()

    conn.sync_status = SyncStatus.SYNCED
    conn.last_synced_at = datetime.now(timezone.utc)
    # 성공 시 반드시 NULL로 초기화한다(v1.3 운용 규칙) — 지난 에러가 화면에 남지 않게.
    conn.last_error_message = None
    await db.commit()

    return conn, outcome


async def _mark_failed(
    db: "AsyncSession", conn: "ChannelConnection", message: str, outcome: SyncOutcome
) -> tuple["ChannelConnection", SyncOutcome]:
    """실패를 DB에 기록한다. **기존 예약은 건드리지 않는다.**

    `last_synced_at`은 갱신하지 않는다 — 이 값은 "마지막으로 **성공**한
    동기화 시각"이다. 실패까지 여기에 찍으면 호스트가 "언제부터 캘린더가
    낡았는지"를 알 수 없게 된다.
    """
    conn.sync_status = SyncStatus.FAILED
    conn.last_error_message = message
    await db.commit()

    outcome.error = message
    logger.warning(
        "iCal 동기화 실패 connection_id=%s: %s", conn.connection_id, message
    )

    # TODO(10/3): ACTION_ITEMS에
    #   category='CHANNEL_SYNC_FAILED' 카드 발행
    #   액션센터 구현이 10/3이라 오늘은 DB 기록까지만 한다. 대시보드 배지는
    #   만들지 않는다 — 배지는 눈에 띄지만 처리 흐름이 없다.

    return conn, outcome
