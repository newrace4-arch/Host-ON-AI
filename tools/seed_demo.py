"""데모 데이터 생성 — 브라우저로 `/calendar`를 눈으로 볼 때 쓴다 (9/14).

    python tools/seed_demo.py            # 만든다(이미 있으면 지우고 다시)
    python tools/seed_demo.py --drop     # 지우기만 한다

## 무엇을 만드는가

    호스트 1  demo@hoston.local / demo1234
    숙소 2    독채(PROPERTY, 3룸 도시민박) + 호스텔(BED, 객실 2·침대 4)
    예약 9건  **교차 충돌 1쌍** + **오늘에 걸치는 3건**(대시보드 today_* 용)

## 🔴 교차 충돌은 서비스를 거치지 않는다

`create_reservation`은 `assert_no_overlap`이 **409로 막는다** — 그것이 r52의
본체다. 화면에서 `is_conflict` 강조를 보려면 그 방어선을 우회해 행을 직접
넣어야 하고, **DB도 막지 않는다**(EXCLUDE는 같은 층만 본다).

실제로도 이런 행은 생긴다 — iCal 동기화로 들어온 예약이 남아 있는데 호스트가
판매단위를 바꾸는 경우다(`test_reservation_integrity.py`의
`_insert_raw_reservation` 도크스트링과 같은 상황).

## ⚠️ 이 스크립트는 테스트가 아니다

`conftest.py`의 픽스처를 쓰지 않으므로 **teardown이 없다.** 만든 것은
`--drop`으로 직접 지운다(`hosts` 삭제 → CASCADE). 개발용 로컬 DB 전용이며,
배포 DB를 향해 실행하지 않는다.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from datetime import date, timedelta
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(BACKEND))

from sqlalchemy import delete, select  # noqa: E402
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine  # noqa: E402
from sqlalchemy.pool import NullPool  # noqa: E402

from app.core.config import settings  # noqa: E402
from app.core.security import hash_password  # noqa: E402
from app.models import Bed, ChannelConnection, Host, Property, Reservation, Room  # noqa: E402
from app.models.enums import (  # noqa: E402
    AccommodationType,
    BookableUnitType,
    Channel,
    ReservationStatus,
)

EMAIL = "demo@hoston.local"
PASSWORD = "demo1234"

# 이번 달 1일을 기준으로 잡는다 — 캘린더가 이번 달을 먼저 그리므로
#   날짜를 고정하면 다음 달에 실행했을 때 화면이 비어 보인다.
TODAY = date.today()
M1 = TODAY.replace(day=1)


def d(n: int) -> date:
    """이번 달 1일 + n일."""
    return M1 + timedelta(days=n)


def t(n: int) -> date:
    """**오늘** + n일.

    🔴 `today_checkin_count`·`today_checkout_count`·`today_turnover_count`는
    `CURRENT_DATE` 기준이라, 달 초 기준(`d()`)으로만 날짜를 잡으면 **오늘을
    비껴가 셋 다 0**이 된다(9/14 실측 — 대시보드가 전부 0이었다).
    오늘에 걸치는 예약은 이 함수로 잡는다.
    """
    return TODAY + timedelta(days=n)


async def drop(session) -> int:
    """데모 호스트를 지운다. 숙소·객실·침대·예약이 CASCADE로 함께 사라진다."""
    host = await session.scalar(select(Host).where(Host.email == EMAIL))
    if host is None:
        return 0
    await session.execute(delete(Host).where(Host.host_id == host.host_id))
    await session.commit()
    return 1


async def build(session) -> dict:
    host = Host(email=EMAIL, password_hash=hash_password(PASSWORD), name="데모 호스트")
    session.add(host)
    await session.flush()

    # ── 숙소 ① 독채 3룸 도시민박 (PROPERTY 단위 통대여) ────────────────
    solo = Property(
        host_id=host.host_id,
        name="연남 3룸 하우스",
        accommodation_type=AccommodationType.URBAN_HOMESTAY,
        bookable_unit_type=BookableUnitType.PROPERTY,
        address="서울 마포구 연남동",
        base_price=180_000,
    )
    session.add(solo)
    await session.flush()
    solo_conn = ChannelConnection(
        property_id=solo.property_id,
        channel=Channel.AIRBNB,
        ical_url="https://example.com/demo-solo.ics",
    )
    session.add(solo_conn)

    # ── 숙소 ② 호스텔 (BED 단위, 객실 2 · 침대 4) ──────────────────────
    hostel = Property(
        host_id=host.host_id,
        name="을지로 호스텔",
        accommodation_type=AccommodationType.HOSTEL,
        bookable_unit_type=BookableUnitType.BED,
        address="서울 중구 을지로",
        base_price=35_000,
    )
    session.add(hostel)
    await session.flush()
    hostel_conn = ChannelConnection(
        property_id=hostel.property_id,
        channel=Channel.AIRBNB,
        ical_url="https://example.com/demo-hostel.ics",
    )
    session.add(hostel_conn)

    rooms = {}
    beds = {}
    for room_name, labels in (("201호", ["A", "B"]), ("202호", ["A", "B"])):
        room = Room(property_id=hostel.property_id, room_name=room_name, capacity=2)
        session.add(room)
        await session.flush()
        rooms[room_name] = room.room_id
        for label in labels:
            bed = Bed(room_id=room.room_id, bed_label=label)
            session.add(bed)
            await session.flush()
            beds[f"{room_name}-{label}"] = bed.bed_id
    await session.flush()

    # ── 예약 6건 (달 전체에 흩어진 것) ──────────────────────────────────
    def res(**kw) -> Reservation:
        kw.setdefault("reservation_status", ReservationStatus.CONFIRMED)
        return Reservation(**kw)

    made = [
        # ① 독채 — 평범한 확정 예약
        res(
            property_id=solo.property_id,
            channel_connection_id=solo_conn.connection_id,
            external_uid="demo-solo-1",
            guest_name="김서준",
            check_in=d(4),
            check_out=d(7),
            gross_amount=540_000,
            fee_amount=81_000,
        ),
        # ② 독채 — 요금 미설정(net_amount가 NULL이 된다: gross/fee 중 하나라도 NULL)
        res(
            property_id=solo.property_id,
            channel_connection_id=solo_conn.connection_id,
            external_uid="demo-solo-2",
            guest_name="이하윤",
            check_in=d(14),
            check_out=d(16),
        ),
        # ③ 독채 — 취소건. 같은 기간을 다시 팔 수 있다(r54 (b))
        res(
            property_id=solo.property_id,
            channel_connection_id=solo_conn.connection_id,
            external_uid="demo-solo-3",
            guest_name="박도윤",
            check_in=d(20),
            check_out=d(22),
            reservation_status=ReservationStatus.CANCELLED,
            gross_amount=360_000,
            fee_amount=54_000,
        ),
        # ④ 호스텔 201호 A침대
        res(
            property_id=hostel.property_id,
            room_id=rooms["201호"],
            bed_id=beds["201호-A"],
            channel_connection_id=hostel_conn.connection_id,
            external_uid="demo-hostel-1",
            guest_name="최지호",
            check_in=d(8),
            check_out=d(11),
            gross_amount=105_000,
            fee_amount=15_750,
        ),
        # ⑤ 🔴 호스텔 201호 **통째** — 아래 ⑥과 교차 충돌한다
        res(
            property_id=hostel.property_id,
            room_id=rooms["201호"],
            bed_id=None,
            channel_connection_id=hostel_conn.connection_id,
            external_uid="demo-hostel-2",
            guest_name="정수아",
            check_in=d(17),
            check_out=d(21),
            gross_amount=280_000,
            fee_amount=42_000,
        ),
        # ⑥ 🔴 호스텔 201호 **B침대** — ⑤의 기간과 겹친다.
        #    EXCLUDE는 층이 달라 통과시키고, 서비스 인터셉터는 우회했다.
        res(
            property_id=hostel.property_id,
            room_id=rooms["201호"],
            bed_id=beds["201호-B"],
            channel_connection_id=hostel_conn.connection_id,
            external_uid="demo-hostel-3",
            guest_name="윤하은",
            check_in=d(19),
            check_out=d(23),
            gross_amount=140_000,
            fee_amount=21_000,
        ),
    ]

    # ── 🔴 오늘에 걸치는 예약 3건 — 대시보드 today_* 지표용 ─────────────
    #   위 6건은 전부 오늘을 비껴가서 대시보드가 0만 보여줬다(9/14).
    #   여기 셋이 `today_checkin`·`today_checkout`·`today_turnover`를 채운다.
    made += [
        # ⑦ 독채 — 오늘 **체크아웃**
        res(
            property_id=solo.property_id,
            channel_connection_id=solo_conn.connection_id,
            external_uid="demo-solo-out",
            guest_name="한지우",
            check_in=t(-2),
            check_out=t(0),
            gross_amount=360_000,
            fee_amount=54_000,
        ),
        # ⑧ 독채 — 오늘 **체크인**. ⑦과 **같은 판매단위(독채)**라 turnover 1.
        #    🔴 독채는 room_id·bed_id가 둘 다 NULL이라, 집계가 조합을
        #      등호로 비교하면 이 turnover가 영원히 0이 된다(4.1절).
        #      화면에서 그 처리가 실제로 되는지 눈으로 확인하는 자리다.
        res(
            property_id=solo.property_id,
            channel_connection_id=solo_conn.connection_id,
            external_uid="demo-solo-in",
            guest_name="오서연",
            check_in=t(0),
            check_out=t(1),
            gross_amount=180_000,
            fee_amount=27_000,
        ),
        # ⑨ 호스텔 201호 A침대 — 오늘 체크아웃만. **대응하는 체크인이 없어
        #    turnover는 0**이다. 독채와 대조되는 반례다.
        res(
            property_id=hostel.property_id,
            room_id=rooms["201호"],
            bed_id=beds["201호-A"],
            channel_connection_id=hostel_conn.connection_id,
            external_uid="demo-hostel-out",
            guest_name="배시우",
            check_in=t(-2),
            check_out=t(0),
            gross_amount=70_000,
            fee_amount=10_500,
        ),
    ]

    session.add_all(made)
    await session.commit()

    return {
        "host_id": host.host_id,
        "solo": (solo.property_id, solo.name),
        "hostel": (hostel.property_id, hostel.name),
        "conflict": (d(17), d(21), d(19), d(23)),
        "count": len(made),
    }


async def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--drop", action="store_true", help="지우기만 한다")
    args = ap.parse_args()

    engine = create_async_engine(settings.DATABASE_URL, poolclass=NullPool)
    maker = async_sessionmaker(bind=engine, expire_on_commit=False, autoflush=False)
    try:
        async with maker() as session:
            removed = await drop(session)
            if removed:
                print(f"기존 데모 호스트 삭제 (CASCADE)  {EMAIL}")
            if args.drop:
                print("삭제만 하고 끝낸다." if removed else "지울 데모 데이터가 없다.")
                return 0

            info = await build(session)
    finally:
        await engine.dispose()

    ci1, co1, ci2, co2 = info["conflict"]
    print("")
    print("  로그인   %s / %s" % (EMAIL, PASSWORD))
    print("  숙소     [%d] %s (독채)" % info["solo"])
    print("           [%d] %s (호스텔 · 객실 2 · 침대 4)" % info["hostel"])
    print("  예약     %d건 (기준 달 %s)" % (info["count"], M1.strftime("%Y-%m")))
    print("  교차충돌 201호 통째 %s~%s  ↔  201호 B침대 %s~%s"
          % (ci1, co1, ci2, co2))
    print("")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
