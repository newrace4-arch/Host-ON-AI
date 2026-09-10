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
from datetime import date, datetime

import httpx
from icalendar import Calendar

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
