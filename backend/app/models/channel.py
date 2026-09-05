"""CHANNEL_CONNECTIONS — DB명세서 v1.3 2.5절."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.enums import Channel, SyncStatus, channel_enum, sync_status_enum

if TYPE_CHECKING:
    from app.models.property import Property


class ChannelConnection(Base):
    """OTA 채널 연결(iCal 동기화). MVP는 채널당 연결 1개로 제한."""

    __tablename__ = "channel_connections"
    __table_args__ = (
        # RESERVATIONS의 (channel_connection_id, property_id) 복합FK 참조용 후보키
        UniqueConstraint(
            "connection_id", "property_id", name="uq_channel_connection_property_ref"
        ),
        # MVP: 한 숙소당 같은 채널 연결은 1개만
        UniqueConstraint("property_id", "channel", name="uq_property_channel"),
        Index("idx_channel_connections_property", "property_id"),
    )

    connection_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    property_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("properties.property_id", ondelete="CASCADE"), nullable=False
    )
    channel: Mapped[Channel] = mapped_column(channel_enum, nullable=False)
    ical_url: Mapped[str | None] = mapped_column(Text)
    external_property_id: Mapped[str | None] = mapped_column(String(100))
    sync_status: Mapped[SyncStatus] = mapped_column(
        sync_status_enum, nullable=False, server_default=text("'SYNCING'")
    )
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # v1.3 추가: 마지막 동기화 실패 사유 1건만 보관.
    #   운용 규칙(명세서 2.5절) — sync_status='FAILED'일 때 사람이 읽을 수 있는
    #   1줄 사유를 저장하고, 성공(SYNCED) 시에는 반드시 NULL로 초기화한다.
    #   원문 스택트레이스는 여기에 넣지 않고 서버 로그로만 남긴다(정보노출 방지).
    last_error_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    property: Mapped["Property"] = relationship(back_populates="channel_connections")
