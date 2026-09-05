"""RESERVATIONS — DB명세서 v1.3 2.6절 (핵심 테이블).

PROPERTY / ROOM / BED 세 가지 판매 단위를 한 테이블로 표현한다
(`room_id`, `bed_id`가 nullable). 겹침 방지는 단위별 EXCLUDE 3개로 분리하며,
`COALESCE(room_id, 0)` 트릭은 폐기됐다(0을 "값 없음"과 "실제 0번 ID"로
구분하지 못해 데이터 오염 위험).
"""

from __future__ import annotations

from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import ExcludeConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.enums import (
    FinancialStatus,
    RefundStatus,
    ReservationStatus,
    financial_status_enum,
    refund_status_enum,
    reservation_status_enum,
)

if TYPE_CHECKING:
    from app.models.channel import ChannelConnection
    from app.models.cleaning import CleaningTask
    from app.models.property import Bed, Property, Room

# EXCLUDE 3종 공통 조건: 확정 상태(CONFIRMED/MODIFIED)인 예약끼리만 겹침을 막는다.
#   취소(CANCELLED)/완료(COMPLETED) 예약은 같은 날짜에 새 예약을 막지 않아야 한다.
_ACTIVE_STATUS_SQL = "reservation_status IN ('CONFIRMED', 'MODIFIED')"
_STAY_RANGE_SQL = "tsrange(check_in::timestamp, check_out::timestamp)"


class Reservation(Base):
    """예약. reservation_status / refund_status / financial_status는 각각
    독립된 축이므로 절대 하나의 필드로 합치지 않는다(CLAUDE.md 핵심 원칙)."""

    __tablename__ = "reservations"
    __table_args__ = (
        # (A) 계층적 무결성: room/bed/channel이 실제로 해당 property/room 소속인지
        #     DB가 보장한다. room_id/bed_id가 NULL이면 MATCH SIMPLE 규칙에 따라
        #     FK 검사가 스킵되므로 PROPERTY 단위 예약과 자연스럽게 호환된다.
        ForeignKeyConstraint(
            ["room_id", "property_id"],
            ["rooms.room_id", "rooms.property_id"],
            name="fk_reservations_room_property",
        ),
        ForeignKeyConstraint(
            ["bed_id", "room_id"],
            ["beds.bed_id", "beds.room_id"],
            name="fk_reservations_bed_room",
        ),
        ForeignKeyConstraint(
            ["channel_connection_id", "property_id"],
            ["channel_connections.connection_id", "channel_connections.property_id"],
            name="fk_reservations_channel_property",
        ),
        # (B) room_id/bed_id 조합의 "내부 형태(shape)"만 검증한다.
        #     ⚠️ 이 CHECK는 PROPERTIES.bookable_unit_type과의 일치는 검증하지
        #     못한다(PostgreSQL 일반 CHECK는 다른 테이블을 참조할 수 없음).
        #     그 교차일치 검증은 예약 생성 서비스 레이어의 책임이다.
        CheckConstraint(
            "(room_id IS NULL AND bed_id IS NULL) OR "
            "(room_id IS NOT NULL AND bed_id IS NULL) OR "
            "(room_id IS NOT NULL AND bed_id IS NOT NULL)",
            name="ck_reservations_unit_shape",
        ),
        CheckConstraint("check_out > check_in", name="ck_reservations_date_order"),
        # 플랫폼별 UID 충돌 방지
        UniqueConstraint(
            "channel_connection_id", "external_uid", name="uq_reservation_channel_uid"
        ),
        # CLEANING_TASKS / INQUIRIES / ACTION_ITEMS의 복합FK 참조용 후보키
        UniqueConstraint("reservation_id", "property_id", name="uq_reservation_property_ref"),
        # 예약 겹침 방지 — 판매 단위별로 3개 분리(명세서 2.6.1절)
        # ① PROPERTY 단위(독채 통대여: room/bed 둘 다 NULL인 경우만)
        ExcludeConstraint(
            ("property_id", "="),
            (text(_STAY_RANGE_SQL), "&&"),
            name="excl_property_overlap",
            using="gist",
            where=text(
                f"room_id IS NULL AND bed_id IS NULL AND {_ACTIVE_STATUS_SQL}"
            ),
        ),
        # ② ROOM 단위
        ExcludeConstraint(
            ("room_id", "="),
            (text(_STAY_RANGE_SQL), "&&"),
            name="excl_room_overlap",
            using="gist",
            where=text(
                f"room_id IS NOT NULL AND bed_id IS NULL AND {_ACTIVE_STATUS_SQL}"
            ),
        ),
        # ③ BED 단위
        ExcludeConstraint(
            ("bed_id", "="),
            (text(_STAY_RANGE_SQL), "&&"),
            name="excl_bed_overlap",
            using="gist",
            where=text(f"bed_id IS NOT NULL AND {_ACTIVE_STATUS_SQL}"),
        ),
        Index("idx_reservations_property", "property_id"),
        Index("idx_reservations_room", "room_id"),
        Index("idx_reservations_bed", "bed_id"),
        Index("idx_reservations_channel", "channel_connection_id"),
        Index("idx_reservations_dates", "property_id", "check_in", "check_out"),
    )

    reservation_id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=True
    )
    property_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("properties.property_id", ondelete="CASCADE"), nullable=False
    )
    # room_id / bed_id는 복합FK로만 참조된다(단독 FK 없음 — 위 __table_args__ 참고)
    room_id: Mapped[int | None] = mapped_column(BigInteger)
    bed_id: Mapped[int | None] = mapped_column(BigInteger)
    channel_connection_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    external_uid: Mapped[str | None] = mapped_column(String(150))
    guest_name: Mapped[str | None] = mapped_column(String(100))
    guest_language: Mapped[str | None] = mapped_column(String(10))
    check_in: Mapped[date] = mapped_column(Date, nullable=False)
    check_out: Mapped[date] = mapped_column(Date, nullable=False)
    booked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # 아래 3개 상태는 서로 다른 축이다. 하나로 합치지 말 것.
    reservation_status: Mapped[ReservationStatus] = mapped_column(
        reservation_status_enum, nullable=False, server_default=text("'CONFIRMED'")
    )
    refund_status: Mapped[RefundStatus] = mapped_column(
        refund_status_enum, nullable=False, server_default=text("'NONE'")
    )
    financial_status: Mapped[FinancialStatus] = mapped_column(
        financial_status_enum, nullable=False, server_default=text("'ESTIMATED'")
    )
    gross_amount: Mapped[int | None] = mapped_column(Integer)
    fee_amount: Mapped[int | None] = mapped_column(Integer)
    # ⚠️ 예약 건별 금액은 net_amount, 월정산 금액은 MONTHLY_SETTLEMENTS.net_payout.
    #    이름을 혼동하지 말 것(명세서 v1.3 체크포인트 6번).
    net_amount: Mapped[int | None] = mapped_column(Integer)
    expected_settlement_at: Mapped[date | None] = mapped_column(Date)
    actual_settlement_at: Mapped[date | None] = mapped_column(Date)
    host_confirmation_required: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    property: Mapped["Property"] = relationship(
        back_populates="reservations", foreign_keys=[property_id]
    )
    # 아래 3개는 복합FK 기반이라 property_id/room_id 컬럼을 다른 관계와 공유한다.
    #   쓰기 경로가 겹쳐 생기는 혼란을 막기 위해 조회 전용(viewonly)으로 둔다.
    room: Mapped["Room | None"] = relationship(
        primaryjoin="and_(Reservation.room_id == Room.room_id, "
        "Reservation.property_id == Room.property_id)",
        viewonly=True,
    )
    bed: Mapped["Bed | None"] = relationship(
        primaryjoin="and_(Reservation.bed_id == Bed.bed_id, "
        "Reservation.room_id == Bed.room_id)",
        viewonly=True,
    )
    channel_connection: Mapped["ChannelConnection"] = relationship(
        primaryjoin="and_("
        "Reservation.channel_connection_id == ChannelConnection.connection_id, "
        "Reservation.property_id == ChannelConnection.property_id)",
        viewonly=True,
    )
    # 예약 1건 : 청소작업 1건 (CLEANING_TASKS.reservation_id UNIQUE)
    cleaning_task: Mapped["CleaningTask | None"] = relationship(
        back_populates="reservation",
        uselist=False,
        viewonly=True,
    )
