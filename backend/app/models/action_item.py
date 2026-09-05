"""ACTION_ITEMS — DB명세서 v1.3 2.15절 (Action Center 큐)."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    DDL,
    BigInteger,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    String,
    Text,
    event,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.enums import (
    ActionRiskLevel,
    ActionStatus,
    action_risk_level_enum,
    action_status_enum,
)

if TYPE_CHECKING:
    from app.models.property import Property


class ActionItem(Base):
    """호스트가 오늘 처리해야 할 일 카드.

    ⚠️ `risk_level`은 AI의 법적/안전 판단이 아니라 **규칙기반 운영 우선순위**다
    (명세서 4절 1번). RED_NOW는 "체크인 임박 + 청소 미완료"처럼 시간·상태로
    결정되는 값일 뿐이며, AI가 게스트 위험도를 판정하는 기능이 아니다.

    중복 생성 방지는 DB UNIQUE가 아니라 애플리케이션 idempotency로 처리한다
    (동일 reservation_id + category + status='OPEN'이 이미 있으면 재사용).
    """

    __tablename__ = "action_items"
    __table_args__ = (
        # v1.3: reservation_id 단독 FK를 복합 FK로 교체.
        #   기존 설계는 "강남 숙소의 액션아이템인데 참조 예약은 홍대 호스텔 예약"
        #   같은 행을 DB가 막지 못했다(4절 -1번 데이터 격리 위반).
        #   reservation_id가 NULL이면(서류만료 알림 등) MATCH SIMPLE 규칙에 따라
        #   검사가 스킵되고, property_id는 아래 단독 FK가 보장한다.
        #
        #   ⚠️ ON DELETE SET NULL (컬럼목록)은 PostgreSQL 15+ 전용 문법이다.
        #      컬럼 목록 없이 SET NULL만 쓰면 NOT NULL인 property_id까지
        #      NULL로 만들려다 삭제 자체가 실패한다.
        #      SQLAlchemy 2.0.35는 ondelete 문자열을 정규식으로 검증해
        #      "SET NULL (reservation_id)"를 거부하므로(CompileError), 여기서는
        #      표준 "SET NULL"로 선언하고 아래 after_create 이벤트에서 실제
        #      컬럼목록 문법으로 교체한다(마이그레이션도 동일하게 처리).
        ForeignKeyConstraint(
            ["reservation_id", "property_id"],
            ["reservations.reservation_id", "reservations.property_id"],
            name="fk_action_items_reservation_property",
            ondelete="SET NULL",
        ),
        Index("idx_action_items_property_status", "property_id", "status", "risk_level"),
    )

    action_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    property_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("properties.property_id", ondelete="CASCADE"), nullable=False
    )
    reservation_id: Mapped[int | None] = mapped_column(BigInteger)
    risk_level: Mapped[ActionRiskLevel] = mapped_column(action_risk_level_enum, nullable=False)
    category: Mapped[str] = mapped_column(String(50), nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    content: Mapped[str | None] = mapped_column(Text)
    status: Mapped[ActionStatus] = mapped_column(
        action_status_enum, nullable=False, server_default=text("'OPEN'")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    property: Mapped["Property"] = relationship(
        back_populates="action_items", foreign_keys=[property_id]
    )


# PostgreSQL 15+ 전용 `ON DELETE SET NULL (reservation_id)`를 실제로 적용한다.
#   SQLAlchemy가 이 문법을 직접 렌더링하지 못해(위 주석 참고) 테이블 생성
#   직후 제약을 교체하는 방식으로 처리한다. 이 이벤트가 없으면 예약 삭제 시
#   property_id까지 NULL로 만들려다 NOT NULL 위반으로 삭제가 실패한다.
#   Alembic 마이그레이션에도 동일한 ALTER가 들어가 있다(create_all/마이그레이션
#   어느 경로로 만들어도 같은 결과가 되도록 양쪽에 둔다).
FK_SET_NULL_COLUMN_LIST_DDL = (
    "ALTER TABLE action_items "
    "DROP CONSTRAINT IF EXISTS fk_action_items_reservation_property, "
    "ADD CONSTRAINT fk_action_items_reservation_property "
    "FOREIGN KEY (reservation_id, property_id) "
    "REFERENCES reservations (reservation_id, property_id) "
    "ON DELETE SET NULL (reservation_id)"
)

event.listen(
    ActionItem.__table__,
    "after_create",
    DDL(FK_SET_NULL_COLUMN_LIST_DDL).execute_if(dialect="postgresql"),
)
