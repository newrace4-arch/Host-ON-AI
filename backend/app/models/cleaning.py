"""CLEANING_TASKS — DB명세서 v1.3 2.9절."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKeyConstraint,
    Index,
    String,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.enums import TaskStatus, task_status_enum

if TYPE_CHECKING:
    from app.models.reservation import Reservation


class CleaningTask(Base):
    """청소 작업. 예약과 1:1(reservation_id UNIQUE).

    생성 시점: 예약이 CONFIRMED 되는 **즉시** PENDING으로 선제생성한다
    (체크아웃 당일이 아님). 전날/당일 자동알림이 성립하려면 미리 존재해야
    하기 때문이다(state_events.md, 명세서 2.9절).

    property_id는 단독 FK가 아니라 (reservation_id, property_id) 복합FK로
    RESERVATIONS를 경유해 확보한다 — reservation_id가 NOT NULL이라 복합FK가
    항상 동작하므로 단독 FK 없이도 데이터 격리가 보장된다(명세서 4절 -1번).
    """

    __tablename__ = "cleaning_tasks"
    __table_args__ = (
        ForeignKeyConstraint(
            ["reservation_id", "property_id"],
            ["reservations.reservation_id", "reservations.property_id"],
            name="fk_cleaning_tasks_reservation_property",
            ondelete="CASCADE",
        ),
        Index("idx_cleaning_tasks_property_status", "property_id", "task_status"),
    )

    task_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    # 예약당 정확히 1개(1:1)
    reservation_id: Mapped[int] = mapped_column(BigInteger, nullable=False, unique=True)
    property_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    task_status: Mapped[TaskStatus] = mapped_column(
        task_status_enum, nullable=False, server_default=text("'PENDING'")
    )
    cleaner_name: Mapped[str | None] = mapped_column(String(100))
    amenity_shortage: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    # v1.3: scheduled_date에서 개명(타입은 TIMESTAMPTZ 그대로).
    #   저장값 = reservations.check_out(DATE) + properties.checkout_time(TIME)을
    #   결합한 "실제 체크아웃 시각"(예: 2026-09-12 11:00+09). 00:00이 아니다.
    #   전날/당일 알림 스케줄러가 이 값에서 역산하므로 시각까지 필요하다.
    scheduled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # v1.3 추가: 완료사진 URL 배열. POST /cleaning-tasks/{id}/photo는 기존 값을
    #   교체하지 않고 배열 끝에 **append**한다(구역별 분할 촬영 운영 패턴).
    photo_urls: Mapped[list[Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'[]'::jsonb")
    )
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    reservation: Mapped["Reservation"] = relationship(
        back_populates="cleaning_task",
        viewonly=True,
    )
