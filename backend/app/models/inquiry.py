"""INQUIRIES / INQUIRY_CLASSIFICATIONS / INQUIRY_RESPONSES / INQUIRY_APPROVALS
— DB명세서 v1.3 2.10~2.13절.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.enums import (
    ApprovalStatus,
    InquiryRiskLevel,
    approval_status_enum,
    inquiry_risk_level_enum,
)

if TYPE_CHECKING:
    from app.models.property import Property


class Inquiry(Base):
    """게스트 문의. reservation_id는 nullable(예약 전 사전문의 지원, v1.3).

    ⚠️ FK 2개는 역할이 다르므로 **둘 다 유지**한다(명세서 2.10절):
      - property_id 단독 FK: "이 숙소가 실재하는가"
      - (reservation_id, property_id) 복합 FK: "이 예약이 정말 이 숙소 예약인가"

    PostgreSQL 복합FK의 기본 매칭은 MATCH SIMPLE이라 구성 컬럼 중 하나라도
    NULL이면 검사를 통째로 건너뛴다. 즉 사전문의(reservation_id IS NULL) 행은
    복합FK가 전혀 동작하지 않아, 단독 FK가 없으면 존재하지도 않는 숙소 ID로
    INSERT가 통과해버린다(4절 -1번 데이터 격리 원칙 위반).
    """

    __tablename__ = "inquiries"
    __table_args__ = (
        ForeignKeyConstraint(
            ["reservation_id", "property_id"],
            ["reservations.reservation_id", "reservations.property_id"],
            name="fk_inquiries_reservation_property",
            ondelete="CASCADE",
        ),
        Index("idx_inquiries_property", "property_id"),
        Index("idx_inquiries_reservation", "reservation_id"),
    )

    inquiry_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    reservation_id: Mapped[int | None] = mapped_column(BigInteger)
    property_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("properties.property_id", ondelete="CASCADE"), nullable=False
    )
    channel: Mapped[str | None] = mapped_column(String(30))
    # ⚠️ 원본은 그대로 저장한다(호스트는 원본을 봐야 함). Claude로 나가는
    #   텍스트에만 mask_pii()를 적용한다(CLAUDE.md 코딩규칙 12번).
    message: Mapped[str] = mapped_column(Text, nullable=False)
    language: Mapped[str | None] = mapped_column(String(10))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    property: Mapped["Property"] = relationship(
        back_populates="inquiries", foreign_keys=[property_id]
    )
    classification: Mapped["InquiryClassification | None"] = relationship(
        back_populates="inquiry",
        cascade="all, delete-orphan",
        passive_deletes=True,
        uselist=False,
    )
    responses: Mapped[list["InquiryResponse"]] = relationship(
        back_populates="inquiry",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class InquiryClassification(Base):
    """문의 분류 결과. 1문의 = Claude 1회 통합호출이므로 1:1이다."""

    __tablename__ = "inquiry_classifications"

    classification_id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=True
    )
    inquiry_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("inquiries.inquiry_id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    category: Mapped[str | None] = mapped_column(String(50))
    risk_level: Mapped[InquiryRiskLevel] = mapped_column(
        inquiry_risk_level_enum, nullable=False
    )
    auto_respondable: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )

    inquiry: Mapped["Inquiry"] = relationship(back_populates="classification")


class InquiryResponse(Base):
    """AI 응답 이력. 1:N + is_latest 플래그(재시도/재답변 대응).

    애플리케이션 규칙(명세서 2.12절): 새 응답 생성 시 같은 트랜잭션 안에서
    기존 is_latest=true 행을 **먼저 UPDATE(false)** 한 뒤 새 행을 INSERT한다.
    순서가 바뀌면 아래 부분 UNIQUE 인덱스 위반으로 실패한다(의도된 안전장치).
    """

    __tablename__ = "inquiry_responses"
    __table_args__ = (
        # 문의 하나당 "최신 응답"은 정확히 1개만 존재하도록 강제
        Index(
            "uniq_inquiry_latest_response",
            "inquiry_id",
            unique=True,
            postgresql_where=text("is_latest = true"),
        ),
        Index("idx_inquiry_responses_inquiry", "inquiry_id"),
    )

    response_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    inquiry_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("inquiries.inquiry_id", ondelete="CASCADE"), nullable=False
    )
    response_text: Mapped[str] = mapped_column(Text, nullable=False)
    # RAG 근거(KNOWLEDGE_CHUNKS chunk_id 목록 등)
    sources: Mapped[Any | None] = mapped_column(JSONB)
    language: Mapped[str | None] = mapped_column(String(10))
    is_latest: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("true")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    inquiry: Mapped["Inquiry"] = relationship(back_populates="responses")
    approvals: Mapped[list["InquiryApproval"]] = relationship(
        back_populates="response",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class InquiryApproval(Base):
    """호스트 승인 기록(응답 발송 전 검수)."""

    __tablename__ = "inquiry_approvals"
    __table_args__ = (Index("idx_inquiry_approvals_response", "response_id"),)

    approval_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    response_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("inquiry_responses.response_id", ondelete="CASCADE"),
        nullable=False,
    )
    status: Mapped[ApprovalStatus] = mapped_column(
        approval_status_enum, nullable=False, server_default=text("'PENDING'")
    )
    approved_by: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("hosts.host_id")
    )
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    response: Mapped["InquiryResponse"] = relationship(back_populates="approvals")
