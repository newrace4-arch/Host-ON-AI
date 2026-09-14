"""대시보드 요약 집계 (api_contract.md 4.1절).

## 캐싱하지 않는다

4.1절이 **매 요청 실시간 집계**로 정했다. 숙소 하나당 쿼리 3~4회이고 전부
인덱스를 타므로(아래 각 함수 참고) 캐시를 둘 이유가 없다 — 캐시를 두면
*"언제 무효화하는가"*가 새 문제로 생기고, 대시보드는 **지금 상태를 보는
화면**이라 낡은 값이 가장 나쁘다.

## 합산하지 않는다 — 숙소 하나만 본다

4.2절: *"백엔드에 교차 숙소 집계 엔드포인트를 **새로 만들지 않는다.**
프론트가 `GET /properties`로 목록을 받은 뒤 각 숙소의 `dashboard/summary`를
**병렬 호출해 합산**한다."* 그래서 이 모듈은 `property_id` 하나만 받는다.

## 🔴 `today_turnover_count`는 `IS NOT DISTINCT FROM`으로 비교한다

4.1절이 명시한다 —

> **PROPERTY 단위 판매 예약은 `room_id`·`bed_id`가 NULL이다.** SQL에서
> `NULL = NULL`은 참이 아니므로 일반 등호 비교로는 PROPERTY 단위 숙소의
> turnover가 집계되지 않는다. 조합 비교에는 **`IS NOT DISTINCT FROM`**을
> 사용한다. `COALESCE(room_id, 0)` 같은 트릭은 사용하지 않는다.

**등호로 써도 테스트 없이는 드러나지 않는다** — ROOM/BED 단위 숙소에서는
정상으로 보이고 독채에서만 영원히 0이 된다. 개발자가 실제 운영하는
3룸 숙소가 PROPERTY 단위라 **가장 중요한 숙소에서만 틀리는** 모양이다.
`test_dashboard_summary.py`가 이 경우를 고정한다.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.action_item import ActionItem
from app.models.cleaning import CleaningTask
from app.models.enums import ActionRiskLevel, ActionStatus, TaskStatus
from app.models.property import Property
from app.models.reservation import Reservation
from app.services.reservation_service import ACTIVE_STATUSES, get_owned_property

# 4.1절: `cleaning_pending_count`가 세는 세 상태.
#   COMPLETED·VERIFIED는 끝난 것이고, ISSUE는 따로 센다.
PENDING_TASK_STATUSES = (
    TaskStatus.PENDING,
    TaskStatus.ASSIGNED,
    TaskStatus.IN_PROGRESS,
)


@dataclass(frozen=True)
class DashboardSummary:
    """4.1절 12필드. `conflict_count`만 None일 수 있다.

    🔴 **기본값을 두지 않는다.** 하나라도 채우지 않은 경로가 있으면 생성
    시점에 `TypeError`로 드러난다 — `ReservationResponse.is_conflict`에
    기본값을 두지 않은 것과 같은 이유(빠뜨린 계산이 조용히 0이 되면 안 된다).
    """

    property_id: int
    property_name: str

    today_checkin_count: int
    today_checkout_count: int
    today_turnover_count: int

    open_action_count: int
    red_now_count: int
    yellow_today_count: int
    green_auto_count: int

    cleaning_pending_count: int
    cleaning_issue_count: int

    conflict_count: int | None


async def _today_counts(
    db: AsyncSession, property_id: int, today: date
) -> tuple[int, int, int]:
    """체크인·체크아웃·턴오버를 **한 번에** 읽어 온 뒤 파이썬에서 센다.

    셋 다 *"오늘 이 숙소에서 시작하거나 끝나는 확정 예약"*이라는 같은 모집단을
    보므로 쿼리를 셋으로 나눌 이유가 없다. 인덱스는
    `idx_reservations_dates(property_id, check_in, check_out)`이다(4.1절).

    ⚠️ **`OR`라서 인덱스 한쪽만 탄다.** 숙소 하나의 당일 예약이라 건수가
    한 자릿수이므로 문제가 되지 않는다. 나뉜 쿼리 두 개로 바꿀 만한 이유가
    생기면 그때 나눈다.
    """
    stmt = select(Reservation.room_id, Reservation.bed_id, Reservation.check_in).where(
        Reservation.property_id == property_id,
        Reservation.reservation_status.in_(ACTIVE_STATUSES),
        (Reservation.check_in == today) | (Reservation.check_out == today),
    )
    rows = (await db.execute(stmt)).all()

    # 판매단위(room_id, bed_id) 조합별로 오늘 들어오는지 나가는지를 모은다.
    #   🔴 파이썬 튜플 비교는 `None == None`이 **참**이라 SQL과 달리 독채가
    #     자연히 묶인다 — 이것이 `IS NOT DISTINCT FROM`과 같은 판정이다.
    checkin_units: set[tuple[int | None, int | None]] = set()
    checkout_units: set[tuple[int | None, int | None]] = set()
    checkin = checkout = 0

    for room_id, bed_id, check_in in rows:
        unit = (room_id, bed_id)
        if check_in == today:
            checkin += 1
            checkin_units.add(unit)
        else:
            checkout += 1
            checkout_units.add(unit)

    # 4.1절: "같은 (property_id, room_id, bed_id) 조합에서 당일 체크아웃
    #   예약과 당일 체크인 예약이 **둘 다 존재하는 단위의 수**".
    #   건수가 아니라 **단위 수**다 — 그래서 set으로 센다.
    turnover = len(checkin_units & checkout_units)
    return checkin, checkout, turnover


async def _action_counts(db: AsyncSession, property_id: int) -> tuple[int, int, int, int]:
    """`status='OPEN'`을 우선순위별로 센다 — 쿼리 하나(`GROUP BY`).

    인덱스 `idx_action_items_property_status(property_id, status, risk_level)`가
    **정확히 이 쿼리 형태와 일치**한다(4.1절).

    ⚠️ `open_action_count`는 셋의 합이 아니라 **따로 세지 않고 합으로 낸다** —
    `risk_level`이 NOT NULL이라 셋 중 하나에 반드시 들어가므로 합과 총계가
    같고, 쿼리를 하나 더 쏘면 두 값이 어긋날 창이 생긴다.
    """
    stmt = (
        select(ActionItem.risk_level, func.count())
        .where(
            ActionItem.property_id == property_id,
            ActionItem.status == ActionStatus.OPEN,
        )
        .group_by(ActionItem.risk_level)
    )
    by_level = {level: n for level, n in (await db.execute(stmt)).all()}
    red = by_level.get(ActionRiskLevel.RED_NOW, 0)
    yellow = by_level.get(ActionRiskLevel.YELLOW_TODAY, 0)
    green = by_level.get(ActionRiskLevel.GREEN_AUTO, 0)
    return red + yellow + green, red, yellow, green


async def _cleaning_counts(db: AsyncSession, property_id: int) -> tuple[int, int]:
    """대기(3상태)와 이슈를 센다 — 쿼리 하나.

    인덱스 `idx_cleaning_tasks_property_status`(4.1절).

    ⚠️ **지금은 항상 0이다.** `CLEANING_TASKS`에 행을 만드는 경로가 아직
    없다(`cleaning_service`는 단계 5 소관, 9/28~). 기능이 없어서 0인 것이지
    집계가 틀린 것이 아니다 — devlog 9/14 참고.
    """
    stmt = (
        select(CleaningTask.task_status, func.count())
        .where(CleaningTask.property_id == property_id)
        .group_by(CleaningTask.task_status)
    )
    by_status = {s: n for s, n in (await db.execute(stmt)).all()}
    pending = sum(by_status.get(s, 0) for s in PENDING_TASK_STATUSES)
    return pending, by_status.get(TaskStatus.ISSUE, 0)


async def _conflict_count(db: AsyncSession, property_id: int) -> int:
    """`is_conflict = true`인 예약 수.

    **파생 필드다** — DB 컬럼이 아니라 매 조회 시 계산한다(4.1절·4.4절).
    같은 숙소의 활성 예약을 한 번에 읽어 **쌍끼리 메모리에서** 비교한다.
    예약마다 쿼리를 쏘면 N+1이 되며, 목록 엔드포인트가 이미 같은 판단을
    했다(`reservation_service.list_reservations`).

    🔴 규칙의 원본은 `reservations_collide` 하나다. 여기서 조건을 다시 쓰지
    않는다 — `test_conflict_rule_parity.py`가 고정한 *"판정은 한 곳"*을
    이 모듈이 깨뜨리면 안 된다.
    """
    from app.services.reservation_service import reservations_collide

    stmt = select(Reservation).where(
        Reservation.property_id == property_id,
        Reservation.reservation_status.in_(ACTIVE_STATUSES),
    )
    rows = list((await db.scalars(stmt)).all())
    return sum(
        1
        for i, a in enumerate(rows)
        if any(reservations_collide(a, b) for j, b in enumerate(rows) if i != j)
    )


async def get_summary(
    db: AsyncSession, *, property_id: int, host_id: int, today: date | None = None
) -> DashboardSummary:
    """4.1절 12필드를 채운다. 타인 소유·부존재는 404(`get_owned_property`).

    `today`를 인자로 받는 이유는 **테스트가 날짜를 고정할 수 있어야** 하기
    때문이다. 운영 경로는 넘기지 않으므로 서버의 오늘이 쓰인다.

    ## `conflict_count`만 실패를 삼킨다

    4.1절: *"**키는 항상 포함한다. 계산 실패 시 값을 `null`로 반환한다.**
    나머지 10개 필드는 정상 값으로 반환한다(Graceful Degradation)"*.

    ⚠️ **다른 필드에는 이 처리를 하지 않는다.** 파생 필드라 계산 자체가
    실패할 수 있는 것은 이것 하나뿐이고, 나머지가 실패하면 그것은 **DB가
    응답하지 않는 것**이라 500이 맞다. 넓게 잡으면 *"대시보드가 조용히 0을
    보여주는"* 상태가 생긴다.
    """
    prop = await get_owned_property(db, property_id, host_id)
    today = today or date.today()

    checkin, checkout, turnover = await _today_counts(db, property_id, today)
    open_actions, red, yellow, green = await _action_counts(db, property_id)
    cleaning_pending, cleaning_issue = await _cleaning_counts(db, property_id)

    try:
        conflicts: int | None = await _conflict_count(db, property_id)
    except Exception:  # noqa: BLE001 — 4.1절이 정한 Graceful Degradation
        conflicts = None

    return DashboardSummary(
        property_id=prop.property_id,
        # 🔴 응답 키는 `property_name`인데 컬럼은 `name`이다(4.1절).
        property_name=prop.name,
        today_checkin_count=checkin,
        today_checkout_count=checkout,
        today_turnover_count=turnover,
        open_action_count=open_actions,
        red_now_count=red,
        yellow_today_count=yellow,
        green_auto_count=green,
        cleaning_pending_count=cleaning_pending,
        cleaning_issue_count=cleaning_issue,
        conflict_count=conflicts,
    )
