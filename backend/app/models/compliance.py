"""CHECKLIST_ITEMS — DB명세서 v1.3 2.16절 (인허가 체크리스트).

정교한 법률 판단 로직을 만들지 않는다. 정적 체크리스트 템플릿 + 만료알림
수준으로 제한하고, UI에는 "참고용, 실제 인허가는 관할 지자체 확인 필요"
문구를 유지한다(CLAUDE.md).
"""

from __future__ import annotations

from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    String,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.enums import (
    AccommodationType,
    RenewalTriggerType,
    accommodation_type_enum,
    renewal_trigger_type_enum,
)

if TYPE_CHECKING:
    from app.models.property import Property


class ChecklistItem(Base):
    """숙소별 인허가/서류 체크리스트 항목."""

    __tablename__ = "checklist_items"
    __table_args__ = (
        CheckConstraint(
            "(renewal_trigger_type = 'NONE' AND expiry_date IS NULL) OR "
            "(renewal_trigger_type = 'EXPIRATION_BASED' AND expiry_date IS NOT NULL) OR "
            "(renewal_trigger_type = 'EVENT_BASED')",
            name="ck_checklist_items_renewal_expiry",
        ),
        Index("idx_checklist_items_property", "property_id"),
    )

    checklist_item_id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=True
    )
    property_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("properties.property_id", ondelete="CASCADE"), nullable=False
    )
    # "이 항목이 파생된 템플릿 유형"을 의미한다. PROPERTIES.accommodation_type이
    #   나중에 바뀌어도 기존 체크리스트 항목은 자동 갱신되지 않는다(의도된 동작,
    #   명세서 4절 2번).
    accommodation_type: Mapped[AccommodationType] = mapped_column(
        accommodation_type_enum, nullable=False
    )
    item_name: Mapped[str] = mapped_column(String(150), nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default=text("'INCOMPLETE'")
    )
    renewal_trigger_type: Mapped[RenewalTriggerType] = mapped_column(
        renewal_trigger_type_enum, nullable=False, server_default=text("'NONE'")
    )
    expiry_date: Mapped[date | None] = mapped_column(Date)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    property: Mapped["Property"] = relationship(back_populates="checklist_items")
