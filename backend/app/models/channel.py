"""CHANNEL_CONNECTIONS — DB명세서 v1.4 2.5절."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
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
    """OTA 채널 연결(iCal 동기화).

    **[v1.4] room_id 추가 — 객실별 리스팅 지원** (명세서 2.5절):
    iCal 피드는 **객실을 알려주지 않는다.** 실제로는 호스텔 객실마다 별도
    리스팅이 만들어지고 **객실마다 별도 iCal URL**이 나온다. 기존
    `UNIQUE(property_id, channel)`은 숙소당 채널 1개만 허용해 객실 3개짜리
    호스텔의 에어비앤비 피드 3개를 등록할 방법이 없었다. `room_id`가 있어야
    동기화된 예약을 어느 객실에 넣을지도 정할 수 있다.

    ⚠️ **UNIQUE에 `NULLS NOT DISTINCT`를 반드시 붙인다.** PostgreSQL의 기본
    UNIQUE는 **NULL을 서로 다른 값으로 취급**한다. 독채(`PROPERTY` 판매단위)
    연결은 `room_id`가 NULL인데, 그냥 `UNIQUE(property_id, channel, room_id)`로
    쓰면 NULL 행을 **몇 개든 넣을 수 있어** 에어비앤비 연결이 2개·3개 생기고
    *"채널당 연결 1개"* 보장이 조용히 깨진다. `NULLS NOT DISTINCT`는 NULL을
    보통 값처럼 취급해 그 구멍을 막는다. 호스텔은 `room_id`가 서로 달라
    여러 개가 정상적으로 허용된다. **PostgreSQL 15+ 문법**이며 로컬·Supabase
    모두 17이라 사용 가능하다.

    🔴 **제약 이름 `uq_property_channel`을 바꾸지 마라.** 컬럼이 2개에서
    3개로 늘었지만 이름은 그대로 유지한다 —
    `services/channel_service.py`가 `violates_constraint(exc,
    "uq_property_channel")`로 IntegrityError를 **409로 번역**한다. 이름이
    바뀌면 그 판정이 조용히 거짓이 되어 **500으로 새어 나간다**
    (`core/db_errors.py`의 도크스트링 예시 문자열도 이 이름을 담고 있다).

    ⚠️ **③ 시점에는 스키마만 앞서 있다 — API는 아직 객실별 연결을 만들지
    못한다.** `api_contract` 3.2절에 `room_id` 요청 필드가 없어
    `ChannelConnectionCreateRequest`·`channel_service.create_channel`도
    그것을 받지 않는다. 컬럼이 nullable이라 서비스를 그대로 두면 지금과
    동일하게 `room_id=NULL` 연결이 만들어져 깨지는 것은 없지만, **객실별
    피드 등록은 api_contract 3.2절을 먼저 고친 뒤에야 가능하다**
    (CLAUDE.md 9/10 규칙 — 엔드포인트 구현 전에 문서에 스펙이 있어야 한다).
    """

    __tablename__ = "channel_connections"
    __table_args__ = (
        # RESERVATIONS의 (channel_connection_id, property_id) 복합FK 참조용 후보키.
        #   v1.4에서 건드리지 않는다 — 남이 참조하는 후보키다.
        UniqueConstraint(
            "connection_id", "property_id", name="uq_channel_connection_property_ref"
        ),
        # v1.4: (property_id, channel) → (property_id, channel, room_id)로 확장.
        #   독채는 room_id가 NULL이므로 NULLS NOT DISTINCT가 없으면
        #   "채널당 연결 1개" 보장이 깨진다(위 도크스트링 참고).
        #   🔴 이름은 uq_property_channel 그대로다 — 409 번역이 이 이름에 걸려 있다.
        UniqueConstraint(
            "property_id",
            "channel",
            "room_id",
            name="uq_property_channel",
            postgresql_nulls_not_distinct=True,
        ),
        # v1.4: 다른 숙소의 객실을 가리키는 연결을 DB가 막는다.
        #   room_id가 NULL이면 MATCH SIMPLE 규칙에 따라 검사가 스킵되고,
        #   property_id는 아래 단독 FK가 보장한다(2.10절 INQUIRIES와 같은 구조).
        ForeignKeyConstraint(
            ["room_id", "property_id"],
            ["rooms.room_id", "rooms.property_id"],
            name="fk_channel_connections_room_property",
        ),
        Index("idx_channel_connections_property", "property_id"),
    )

    connection_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    property_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("properties.property_id", ondelete="CASCADE"), nullable=False
    )
    # v1.4 추가: 객실별 리스팅용. NULL이면 숙소 전체 피드(독채는 항상 NULL).
    room_id: Mapped[int | None] = mapped_column(BigInteger)
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
