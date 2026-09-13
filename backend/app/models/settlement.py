"""FINANCIAL_CONFIGS / MONTHLY_SETTLEMENTS / CHANNEL_FEE_RATES
— DB명세서 v1.4 2.7~2.8·2.19절.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    CHAR,
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.enums import Channel, FeeType, channel_enum, fee_type_enum

if TYPE_CHECKING:
    from app.models.property import Property


class FinancialConfig(Base):
    """숙소별 설정. 과거 정산 결과에는 영향을 주지 않는다.

    **[v1.4] 이 테이블에서 4개가 빠졌다**(명세서 2.7절):
      - `fee_type` · `commission_rate` · `fee_source` → **2.19
        `CHANNEL_FEE_RATES`로 이동.** `property_id`가 UNIQUE라 이 테이블은
        **숙소당 정확히 한 행**인데 `channel_enum`은 3값이고
        `CHANNEL_CONNECTIONS`는 숙소당 채널 3개까지 허용한다. 즉 채널마다
        수수료가 다른 현실을 담을 자리가 구조적으로 없었다. 요율은
        "숙소의 속성"이 아니라 **"숙소×채널의 속성"**이다.
      - `base_nightly_rate` → **제거(이동 아님).** `PROPERTIES.base_price`와
        뜻이 같은데 어느 쪽이 진짜인지 정한 문서가 없었고 값을 채우거나
        읽는 코드도 없었다. 단가의 원본은 `PROPERTIES.base_price` 하나다.

    **남은 것은 `vat_included` 하나**다.

    ⚠️ **이 테이블의 행을 만드는 코드가 아직 없다.** v1.4 ⑤ 시점에
    `financial_configs`는 0행이고, 이 테이블을 쓰는 DTO·라우터·서비스가
    하나도 없다(9/13 전수 확인). **누가 언제 이 행을 만드는지**는 정산
    구현 시점에 정해야 한다 — 숙소 생성 시 함께 만들지, 설정 화면에서
    처음 저장할 때 만들지가 미정이다. `CHANNEL_FEE_RATES`는 채널 연결
    생성 시 "없으면 만들고 있으면 유지"로 정해졌으나, 이 테이블은 그에
    대응하는 규칙이 없다.
    """

    __tablename__ = "financial_configs"

    config_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    property_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("properties.property_id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    # v1.4: fee_type · commission_rate · fee_source → CHANNEL_FEE_RATES로 이동,
    #   base_nightly_rate는 제거(위 도크스트링 참고).
    # ⚠️ "properties.base_price가 VAT 포함 금액인가"를 뜻한다.
    #   **표시 전용이며 어떤 계산에도 쓰지 않는다**(명세서 2.7절 v1.4).
    #   정산에 세금계산서·부가세·회계 기능을 넣지 않는다는 원칙(CLAUDE.md)에
    #   따라, 이 값은 화면에서 "VAT 포함가"라고 알려주는 데까지만 쓴다.
    vat_included: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("true")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    property: Mapped["Property"] = relationship(back_populates="financial_config")


class MonthlySettlement(Base):
    """월 정산 **스냅샷**.

    ⚠️ FINANCIAL_CONFIGS와 FK로 연결하지 않는다(명세서 2.8절 / 0절 7번).
    수수료율이 나중에 바뀌어도 과거 정산 결과가 변하면 안 되므로, 계산
    당시의 수수료율을 `applied_commission_rate`에 값으로 복사해 보관한다.
    """

    __tablename__ = "monthly_settlements"
    __table_args__ = (
        UniqueConstraint("property_id", "target_month", name="uq_settlement_property_month"),
    )

    settlement_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    property_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("properties.property_id", ondelete="CASCADE"), nullable=False
    )
    target_month: Mapped[str] = mapped_column(CHAR(7), nullable=False)  # 'YYYY-MM'
    total_reservations: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )
    occupied_nights: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )
    occupancy_rate: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    gross_revenue: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    channel_fee: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    # ⚠️ 월정산 금액은 net_payout. 예약 건별 금액(RESERVATIONS.net_amount)과 혼동 금지.
    net_payout: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    # 계산 당시 수수료율 스냅샷 (설정이 바뀌어도 과거값 불변)
    applied_commission_rate: Mapped[Decimal | None] = mapped_column(Numeric(5, 4))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    property: Mapped["Property"] = relationship(back_populates="monthly_settlements")


class ChannelFeeRate(Base):
    """CHANNEL_FEE_RATES — 채널별 수수료율. 명세서 v1.4 2.19절.

    `FINANCIAL_CONFIGS`의 `fee_type`·`commission_rate`·`fee_source` 3개를
    대체한다. 그 테이블은 `property_id`가 UNIQUE라 **숙소당 요율 1개**였는데
    채널은 3개까지 허용된다.

    ⚠️ **`CHANNEL_CONNECTIONS`를 FK로 참조하지 않는다 —
    `PROPERTIES`만 참조한다.** 연결은 **지웠다 다시 만드는 자원**이기
    때문이다. api_contract 3절에 `PATCH`가 없어 iCal URL을 바꾸려면
    `DELETE` 후 다시 `POST`해야 하는데, 요율을 연결에 매달면 **URL을 한 번
    바꿀 때마다 호스트가 입력한 수수료율이 함께 사라진다.** 요율은
    "이 숙소가 이 채널과 맺은 조건"이지 "지금 연결이 살아 있는가"와
    무관하다. **연결이 없는 채널의 요율 행이 남아 있는 것은 정상**이며,
    다시 연결하면 그 값이 그대로 쓰인다.

    ⚠️ **이름이 `channel_fee`가 아닌 이유**: `MONTHLY_SETTLEMENTS.channel_fee`가
    이미 있고 **그것은 금액(INTEGER)**이다. 같은 이름이 한쪽은 비율, 한쪽은
    금액을 뜻하면 쿼리를 읽을 때마다 확인해야 한다. `_rates`를 붙여 비율임을
    이름에 박는다(`net_amount`와 `net_payout`을 구분한 것과 같은 취지).

    ⚠️ **relationship을 만들지 않는다.** 2.17 `ResponseSource`·2.18
    `CleaningTaskPhoto`와 같은 판단이다 — 행을 쓰는 곳이 좁고 삭제 정리는
    DB의 ON DELETE CASCADE가 담당한다.

    **`fee_source`의 뜻과 미정 사항**: 이 요율을 어디서 얻었는가를 담는다.
    기본값 `'system_default_2026'`은 **"호스트가 확인하지 않은 시스템
    기본값"**을 뜻하며, 화면은 이 값을 추정치로 표시해 확정치처럼 보이지
    않게 한다. ⚠️ **호스트가 요율을 고친 뒤 이 컬럼이 어떤 값으로 바뀌는지는
    아직 정의돼 있지 않다** — db_spec 2.19는 "다른 값으로 바뀐다"까지만
    적고 그 값의 목록이나 형식을 정하지 않았다. 요율 수정 API를 만들 때
    함께 확정해야 한다.
    """

    __tablename__ = "channel_fee_rates"
    __table_args__ = (
        UniqueConstraint(
            "property_id", "channel", name="uq_channel_fee_rate_property_channel"
        ),
        # 요율은 비율이다. 15.5%를 15.5로 잘못 넣으면 수수료가 매출의
        #   15.5배가 된다.
        CheckConstraint(
            "commission_rate >= 0 AND commission_rate <= 1",
            name="ck_channel_fee_rate_range",
        ),
        Index("idx_channel_fee_rates_property", "property_id"),
    )

    channel_fee_rate_id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=True
    )
    property_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey(
            "properties.property_id",
            name="fk_channel_fee_rates_property",
            ondelete="CASCADE",
        ),
        nullable=False,
    )
    channel: Mapped[Channel] = mapped_column(channel_enum, nullable=False)
    fee_type: Mapped[FeeType] = mapped_column(
        fee_type_enum, nullable=False, server_default=text("'SINGLE_FEE'")
    )
    # 2026.5.25 한국 단일수수료 기준
    commission_rate: Mapped[Decimal] = mapped_column(
        Numeric(5, 4), nullable=False, server_default=text("0.1550")
    )
    fee_source: Mapped[str] = mapped_column(
        String(50), nullable=False, server_default=text("'system_default_2026'")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
