"""CHANNEL_FEE_RATES 회귀 테스트 (v1.4 revision ⑤).

### 왜 이 파일이 따로 필요한가

⑤는 오늘 다섯 revision 중 **유일하게 데이터를 쓰고 서비스 코드를 고친다.**
제약 대조(+3)가 보는 것은 FK·UNIQUE·CHECK 셋뿐이라 **PK와 NOT NULL 6개는
집계 밖**이고, `create_channel`이 요율 행을 만드는 동작은 스키마가 아니라
런타임 행위라 어떤 도구도 보지 않는다.

### 백필은 여기서 검증하지 않는다

마이그레이션 시점의 **일회성 사건**이고 테스트는 이미 마이그레이션이 끝난
DB에서 돈다. 그 시점에는 백필이 만든 행과 `create_channel`이 만든 행이
구분되지 않으며, 테스트와 개발이 같은 DB라 "정확히 1건" 같은 단언이 다른
테스트 때문에 깨진다. 백필 결과는 마이그레이션 직후 조회로 판정했다.

### 정리

`conftest.py`를 고치지 않는다. 요율 행이 정리되는 경로는 **`hosts` 삭제
CASCADE 하나뿐**이므로(`hosts` → `properties` → `channel_fee_rates`),
이 파일의 테스트는 전부 `host` 픽스처 안에서 데이터를 만들고 **직접
지우지 않는다.**
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from sqlalchemy import delete, func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ChannelConnection, ChannelFeeRate, Property
from app.models.enums import BookableUnitType, Channel, FeeType
from app.models.host import Host
from app.schemas.channel import ChannelConnectionCreateRequest
from app.services import channel_service
from app.services.channel_service import ChannelAlreadyConnectedError

REAL_URL = "https://www.airbnb.com/calendar/ical/12345678.ics?s=abc1234567890"


# ---------------------------------------------------------------------------
# 지역 헬퍼
# ---------------------------------------------------------------------------


async def _make_rate(
    db: AsyncSession,
    prop: Property,
    *,
    channel: Channel = Channel.BOOKING_COM,
    commission_rate: Decimal | float | None = None,
) -> ChannelFeeRate:
    """요율 행 1건. 값을 생략하면 DB의 server_default에 맡긴다."""
    kwargs = {"property_id": prop.property_id, "channel": channel}
    if commission_rate is not None:
        kwargs["commission_rate"] = commission_rate
    obj = ChannelFeeRate(**kwargs)
    db.add(obj)
    await db.flush()
    await db.refresh(obj)
    return obj


async def _expect_integrity_error(db: AsyncSession, obj) -> IntegrityError:
    db.add(obj)
    try:
        await db.flush()
    except IntegrityError as exc:
        await db.rollback()
        return exc

    await db.rollback()
    pytest.fail("DB 제약이 발동하지 않았다 — 테스트 전제가 깨졌다")


async def _rate_count(db: AsyncSession, property_id: int) -> int:
    return await db.scalar(
        select(func.count())
        .select_from(ChannelFeeRate)
        .where(ChannelFeeRate.property_id == property_id)
    )


# ---------------------------------------------------------------------------
# 1. 숙소 삭제 → 요율 행 CASCADE
#    (맨 앞에 둔다. conftest teardown이 hosts → properties → channel_fee_rates
#     경로를 타므로, 이것이 깨지면 잔여 데이터가 다음 테스트를 오염시킨다)
# ---------------------------------------------------------------------------


async def test_property_delete_cascades_to_fee_rates(db: AsyncSession, make_property):
    prop, _ = await make_property(BookableUnitType.PROPERTY)
    await _make_rate(db, prop, channel=Channel.BOOKING_COM)
    await _make_rate(db, prop, channel=Channel.NAVER)
    await db.commit()

    property_id = prop.property_id
    assert await _rate_count(db, property_id) == 2

    await db.execute(delete(Property).where(Property.property_id == property_id))
    await db.commit()

    assert await _rate_count(db, property_id) == 0


# ---------------------------------------------------------------------------
# 2. CHECK 범위 — 요율은 비율이다
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("rate", ["1.5000", "-0.1000"], ids=["over_one", "negative"])
async def test_commission_rate_out_of_range_is_rejected(
    db: AsyncSession, make_property, rate
):
    """15.5%를 0.1550이 아니라 15.5로 넣으면 수수료가 매출의 15.5배가 된다.

    NUMERIC(5,4)는 9.9999까지 담기므로 타입만으로는 막히지 않는다.
    """
    prop, _ = await make_property(BookableUnitType.PROPERTY)
    await db.commit()

    exc = await _expect_integrity_error(
        db,
        ChannelFeeRate(
            property_id=prop.property_id,
            channel=Channel.BOOKING_COM,
            commission_rate=Decimal(rate),
        ),
    )
    assert "ck_channel_fee_rate_range" in str(exc.orig)


@pytest.mark.parametrize(
    "rate", ["0.0000", "1.0000", "0.1550"], ids=["zero", "one", "default_value"]
)
async def test_commission_rate_boundaries_are_allowed(
    db: AsyncSession, make_property, rate
):
    """경계값 0과 1은 **허용**이다(`>= 0 AND <= 1`)."""
    prop, _ = await make_property(BookableUnitType.PROPERTY)
    obj = await _make_rate(db, prop, commission_rate=Decimal(rate))
    await db.commit()

    assert obj.commission_rate == Decimal(rate)


# ---------------------------------------------------------------------------
# 3. UNIQUE (property_id, channel)
# ---------------------------------------------------------------------------


async def test_duplicate_property_channel_is_rejected(
    db: AsyncSession, make_property
):
    """요율은 (숙소, 채널)당 하나다. 연결이 여럿이어도 요율은 하나다."""
    prop, _ = await make_property(BookableUnitType.PROPERTY)
    await _make_rate(db, prop, channel=Channel.BOOKING_COM)
    await db.commit()

    exc = await _expect_integrity_error(
        db,
        ChannelFeeRate(property_id=prop.property_id, channel=Channel.BOOKING_COM),
    )
    assert "uq_channel_fee_rate_property_channel" in str(exc.orig)


# ---------------------------------------------------------------------------
# 4. 기본값 3종
# ---------------------------------------------------------------------------


async def test_server_defaults(db: AsyncSession, make_property):
    """세 기본값은 **서버가** 채운다(2026.5.25 한국 단일수수료 기준).

    `fee_source`의 `system_default_2026`은 **"호스트가 확인하지 않은 시스템
    기본값"**을 뜻하며, 화면은 이 값을 추정치로 표시한다(db_spec 2.19절).
    """
    prop, _ = await make_property(BookableUnitType.PROPERTY)
    obj = await _make_rate(db, prop, channel=Channel.NAVER)
    await db.commit()

    assert obj.fee_type is FeeType.SINGLE_FEE
    assert obj.commission_rate == Decimal("0.1550")
    assert obj.fee_source == "system_default_2026"


# ---------------------------------------------------------------------------
# 5. 연결을 지워도 요율은 남는다 — FK가 없다는 증거
# ---------------------------------------------------------------------------


async def test_rate_survives_connection_delete(
    db: AsyncSession, host: Host, make_property
):
    """db_spec 2.19가 **"정상"이라고 명시한 동작**이다.

    `CHANNEL_FEE_RATES`는 `CHANNEL_CONNECTIONS`가 아니라 `PROPERTIES`를
    참조한다. 연결은 지웠다 다시 만드는 자원이고(iCal URL 변경에 `PATCH`가
    없다), 요율을 연결에 매달면 URL을 한 번 바꿀 때마다 호스트가 입력한
    수수료율이 함께 사라진다.
    """
    prop, _ = await make_property(BookableUnitType.PROPERTY)
    conn = await channel_service.create_channel(
        db,
        property_id=prop.property_id,
        host_id=host.host_id,
        payload=ChannelConnectionCreateRequest(
            channel=Channel.NAVER, ical_url=REAL_URL
        ),
    )
    await db.commit()
    property_id, connection_id = prop.property_id, conn.connection_id

    await channel_service.delete_channel(
        db, connection_id=connection_id, host_id=host.host_id
    )
    await db.commit()

    # 연결은 사라졌지만 요율은 남는다
    assert (
        await db.scalar(
            select(func.count())
            .select_from(ChannelConnection)
            .where(ChannelConnection.connection_id == connection_id)
        )
        == 0
    )
    surviving = await db.scalar(
        select(ChannelFeeRate).where(
            ChannelFeeRate.property_id == property_id,
            ChannelFeeRate.channel == Channel.NAVER,
        )
    )
    assert surviving is not None


# ---------------------------------------------------------------------------
# 6. create_channel이 요율을 만들고, 호스트가 고친 값은 덮어쓰지 않는다
# ---------------------------------------------------------------------------


async def test_create_channel_creates_rate_and_never_overwrites(
    db: AsyncSession, host: Host, make_property
):
    """"없으면 만들고 있으면 유지" — `ON CONFLICT DO NOTHING`의 계약이다.

    `DO UPDATE`였다면 재연결 한 번에 호스트가 입력한 요율이 기본값으로
    되돌아간다. 연결을 지웠다 다시 만드는 것은 흔한 일이라 실제로 발생한다.
    """
    prop, _ = await make_property(BookableUnitType.PROPERTY)
    await db.commit()
    property_id = prop.property_id

    # (1) 최초 연결 → 요율 행이 기본값으로 생긴다
    conn = await channel_service.create_channel(
        db,
        property_id=property_id,
        host_id=host.host_id,
        payload=ChannelConnectionCreateRequest(
            channel=Channel.BOOKING_COM, ical_url=REAL_URL
        ),
    )
    await db.commit()
    connection_id = conn.connection_id

    rate = await db.scalar(
        select(ChannelFeeRate).where(
            ChannelFeeRate.property_id == property_id,
            ChannelFeeRate.channel == Channel.BOOKING_COM,
        )
    )
    assert rate is not None
    assert rate.commission_rate == Decimal("0.1550")

    # (2) 호스트가 요율을 고친다
    rate.commission_rate = Decimal("0.2000")
    rate.fee_source = "host_confirmed"
    await db.commit()

    # (3) 연결 해제 → 재연결
    await channel_service.delete_channel(
        db, connection_id=connection_id, host_id=host.host_id
    )
    await db.commit()
    await channel_service.create_channel(
        db,
        property_id=property_id,
        host_id=host.host_id,
        payload=ChannelConnectionCreateRequest(
            channel=Channel.BOOKING_COM, ical_url=REAL_URL
        ),
    )
    await db.commit()

    # (4) 호스트가 고친 값이 그대로다
    again = await db.scalar(
        select(ChannelFeeRate).where(
            ChannelFeeRate.property_id == property_id,
            ChannelFeeRate.channel == Channel.BOOKING_COM,
        )
    )
    assert again.commission_rate == Decimal("0.2000")
    assert again.fee_source == "host_confirmed"
    # 행이 늘지도 않았다
    assert await _rate_count(db, property_id) == 1


# ---------------------------------------------------------------------------
# 7. 실패 경로 — 중복 연결은 409이고 트랜잭션 경계가 지켜진다
# ---------------------------------------------------------------------------


async def test_duplicate_connection_is_409_and_rate_count_unchanged(
    db: AsyncSession, host: Host, make_property
):
    """6번은 성공 경로만 본다. 이쪽은 **실패 경로**다.

    요율 INSERT가 `flush()` 뒤에 있으므로, 연결 INSERT가 먼저 실패하면
    요율은 시도조차 되지 않고 `rollback()`으로 트랜잭션이 통째로 되돌아간다.
    이때 **409여야 하고 500이면 안 된다** — 요율 INSERT가 예외를 냈다면
    제약 이름이 `uq_property_channel`이 아니라 409 번역에 걸리지 않는다.
    """
    prop, _ = await make_property(BookableUnitType.PROPERTY)  # AIRBNB 연결이 이미 있다
    await db.commit()
    property_id = prop.property_id

    before = await _rate_count(db, property_id)

    with pytest.raises(ChannelAlreadyConnectedError) as exc:
        await channel_service.create_channel(
            db,
            property_id=property_id,
            host_id=host.host_id,
            payload=ChannelConnectionCreateRequest(
                channel=Channel.AIRBNB, ical_url=REAL_URL
            ),
        )

    assert exc.value.status_code == 409
    assert exc.value.code == "CHANNEL_ALREADY_CONNECTED"
    assert await _rate_count(db, property_id) == before


# ---------------------------------------------------------------------------
# 8. financial_configs에서 컬럼 4개가 사라지고 vat_included는 남았는가
# ---------------------------------------------------------------------------


async def test_financial_configs_columns_moved(db: AsyncSession):
    """모델과 DB 양쪽을 함께 본다(①②의 sources·photo_urls와 같은 방식)."""
    from app.models import FinancialConfig

    gone = {"fee_type", "commission_rate", "fee_source", "base_nightly_rate"}

    # (1) 모델 속성
    for name in gone:
        assert not hasattr(FinancialConfig, name), name
    assert hasattr(FinancialConfig, "vat_included")

    # (2) 실제 DB 컬럼
    names = {
        r[0]
        for r in (
            await db.execute(
                text(
                    "SELECT column_name FROM information_schema.columns "
                    "WHERE table_name = 'financial_configs'"
                )
            )
        ).all()
    }
    assert names & gone == set()
    assert names == {"config_id", "property_id", "vat_included", "created_at"}
