"""FINANCIAL_CONFIGS / MONTHLY_SETTLEMENTS — DB명세서 v1.3 2.7~2.8절."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    CHAR,
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.enums import FeeType, fee_type_enum

if TYPE_CHECKING:
    from app.models.property import Property


class FinancialConfig(Base):
    """숙소별 수수료 설정(현재값). 과거 정산 결과에는 영향을 주지 않는다."""

    __tablename__ = "financial_configs"

    config_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    property_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("properties.property_id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
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
    base_nightly_rate: Mapped[int | None] = mapped_column(Integer)
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
