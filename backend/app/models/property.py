"""PROPERTIES / ROOMS / BEDS — DB명세서 v1.3 2.2~2.4절."""

from __future__ import annotations

from datetime import datetime, time
from typing import TYPE_CHECKING

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Time,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.enums import (
    AccommodationType,
    BookableUnitType,
    accommodation_type_enum,
    bookable_unit_type_enum,
)

if TYPE_CHECKING:
    from app.models.action_item import ActionItem
    from app.models.channel import ChannelConnection
    from app.models.compliance import ChecklistItem
    from app.models.host import Host
    from app.models.inquiry import Inquiry
    from app.models.rag import KnowledgeChunk
    from app.models.reservation import Reservation
    from app.models.settlement import FinancialConfig, MonthlySettlement


class Property(Base):
    """숙소. accommodation_type은 단일 ENUM(복수 유형 동시 등록 불가).

    근거: 관광진흥법 시행령 제2조 제1항 제3호 바목 — 동일 공간에 대해
    복수 숙박업 유형을 동시 등록할 수 없음(명세서 1절).
    """

    __tablename__ = "properties"
    __table_args__ = (Index("idx_properties_host", "host_id"),)

    property_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    host_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("hosts.host_id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    accommodation_type: Mapped[AccommodationType] = mapped_column(
        accommodation_type_enum, nullable=False
    )
    bookable_unit_type: Mapped[BookableUnitType] = mapped_column(
        bookable_unit_type_enum, nullable=False
    )
    address: Mapped[str | None] = mapped_column(String(255))
    base_price: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    # 하한가 경고용(명세서 6절 동적 가격조정). NULL 허용.
    lower_bound_price: Mapped[int | None] = mapped_column(Integer)
    # v1.1 추가: Action Center "체크인 N시간 전" 규칙은 check_in(DATE)만으로는
    #   계산할 수 없어 숙소 단위 운영정책 시각이 필요하다.
    checkin_time: Mapped[time] = mapped_column(
        Time, nullable=False, server_default=text("'15:00'")
    )
    checkout_time: Mapped[time] = mapped_column(
        Time, nullable=False, server_default=text("'11:00'")
    )
    # v1.2 추가: 공백일 미세조정 / 성수기 방치감지 on-off 스위치(명세서 6절)
    weekday_adjustment_enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("true")
    )
    holiday_adjustment_enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("true")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    host: Mapped["Host"] = relationship(back_populates="properties")
    rooms: Mapped[list["Room"]] = relationship(
        back_populates="property",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    channel_connections: Mapped[list["ChannelConnection"]] = relationship(
        back_populates="property",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    reservations: Mapped[list["Reservation"]] = relationship(
        back_populates="property",
        cascade="all, delete-orphan",
        passive_deletes=True,
        foreign_keys="Reservation.property_id",
    )
    financial_config: Mapped["FinancialConfig | None"] = relationship(
        back_populates="property",
        cascade="all, delete-orphan",
        passive_deletes=True,
        uselist=False,
    )
    monthly_settlements: Mapped[list["MonthlySettlement"]] = relationship(
        back_populates="property",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    inquiries: Mapped[list["Inquiry"]] = relationship(
        back_populates="property",
        cascade="all, delete-orphan",
        passive_deletes=True,
        foreign_keys="Inquiry.property_id",
    )
    knowledge_chunks: Mapped[list["KnowledgeChunk"]] = relationship(
        back_populates="property",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    action_items: Mapped[list["ActionItem"]] = relationship(
        back_populates="property",
        cascade="all, delete-orphan",
        passive_deletes=True,
        foreign_keys="ActionItem.property_id",
    )
    checklist_items: Mapped[list["ChecklistItem"]] = relationship(
        back_populates="property",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class Room(Base):
    """객실. 두 UNIQUE 제약은 목적이 다르므로 둘 다 유지한다(명세서 2.3절)."""

    __tablename__ = "rooms"
    __table_args__ = (
        # (room_id, property_id): room_id가 이미 PK라 중복방지 효과는 없다.
        #   RESERVATIONS가 (room_id, property_id) 복합FK로 "이 객실이 정말 이
        #   숙소 소속인가"를 DB에 검증시키기 위한 후보키(candidate key)다.
        UniqueConstraint("room_id", "property_id", name="uq_room_property_ref"),
        # 같은 숙소 안에서 게스트가 보는 객실명("101호") 중복 방지용 운영 제약.
        UniqueConstraint("property_id", "room_name", name="uq_property_room_name"),
        Index("idx_rooms_property", "property_id"),
    )

    room_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    property_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("properties.property_id", ondelete="CASCADE"), nullable=False
    )
    room_name: Mapped[str] = mapped_column(String(100), nullable=False)
    capacity: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    property: Mapped["Property"] = relationship(back_populates="rooms")
    beds: Mapped[list["Bed"]] = relationship(
        back_populates="room",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class Bed(Base):
    """침대(호스텔 도미토리 BED 단위 판매용)."""

    __tablename__ = "beds"
    __table_args__ = (
        # ROOMS와 동일한 이유: RESERVATIONS의 (bed_id, room_id) 복합FK 참조용 후보키
        UniqueConstraint("bed_id", "room_id", name="uq_bed_room_ref"),
        # 같은 객실 안 침대 라벨("A", "B") 중복 방지용 운영 제약
        UniqueConstraint("room_id", "bed_label", name="uq_room_bed_label"),
        Index("idx_beds_room", "room_id"),
    )

    bed_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    room_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("rooms.room_id", ondelete="CASCADE"), nullable=False
    )
    bed_label: Mapped[str] = mapped_column(String(50), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    room: Mapped["Room"] = relationship(back_populates="beds")
