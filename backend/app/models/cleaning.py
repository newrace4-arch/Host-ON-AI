"""CLEANING_TASKS / CLEANING_TASK_PHOTOS — DB명세서 v1.4 2.9·2.18절."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    Text,
    func,
    text,
)
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
    # v1.4: photo_urls(JSONB) 제거 → 2.18 CLEANING_TASK_PHOTOS 테이블로 분리.
    #   POST /cleaning-tasks/{id}/photo의 **append 운용 규칙은 그대로**이며,
    #   배열 끝에 원소를 더하는 대신 행을 하나 INSERT하는 것으로 실현된다.
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    reservation: Mapped["Reservation"] = relationship(
        back_populates="cleaning_task",
        viewonly=True,
    )


class CleaningTaskPhoto(Base):
    """CLEANING_TASK_PHOTOS — 청소 완료사진. 명세서 v1.4 2.18절.

    v1.3의 `CLEANING_TASKS.photo_urls`(JSONB 배열)를 대체한다. 2.17
    `RESPONSE_SOURCES`와 같은 이유다 — JSONB 배열에는 FK가 걸리지 않아 DB가
    아무것도 검증하지 못한다.

    **append 운용 규칙은 바뀌지 않는다**(api_contract v1.6): 사진 업로드는
    기존 것을 교체하지 않고 **행을 하나 INSERT**한다. 목록은 `sort_order`
    순으로 돌려준다. 덤으로 사진 한 장만 지우는 것이
    `DELETE ... WHERE photo_id = ?` 한 줄이 된다(JSONB 시절에는 배열 전체를
    덮어써야 했다). `VERIFIED` 전이 조건도 그대로이며, *사진 0장*은 이제
    *"이 task_id를 가진 행이 0건"*을 뜻한다.

    ⚠️ **파일 자체를 어디에 저장할지는 아직 정하지 않았다.** 이 테이블은
    **URL 문자열만** 보관한다(9/11 전수 확인 — db_spec·api_contract·
    ui_design 어디에도 저장처를 정한 문장이 없다).
    **Render 무료 플랜의 디스크는 후보가 아니다** — 인스턴스가 재시작·슬립
    복귀할 때마다 초기화돼 업로드한 사진이 사라진다. 15분 무요청 슬립이 잦은
    환경이라 실제로 발생한다. 결정 시점은 청소 화면 구현(체크리스트 4단계)
    전이며, 그때까지 이 컬럼은 시드 데이터의 정적 URL을 담는다.

    ⚠️ **relationship을 만들지 않는다.** 2.17 `ResponseSource`와 같은
    판단이다 — 행을 쓰는 곳이 사진 업로드 API 한 곳뿐이라 ORM 캐스케이드가
    필요 없고, 삭제 정리는 DB의 ON DELETE CASCADE가 담당한다.
    """

    __tablename__ = "cleaning_task_photos"
    __table_args__ = (
        # 목록 조회가 항상 WHERE task_id = ? ORDER BY sort_order 이므로
        #   task_id 단독이 아니라 **복합 인덱스**다.
        Index("idx_cleaning_task_photos_task", "task_id", "sort_order"),
    )

    photo_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    task_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey(
            "cleaning_tasks.task_id",
            name="fk_cleaning_task_photos_task",
            ondelete="CASCADE",
        ),
        nullable=False,
    )
    photo_url: Mapped[str] = mapped_column(Text, nullable=False)
    # 화면 표시 순서. **파이썬측 default=가 아니라 서버 기본값**이다 —
    #   마이그레이션 DDL과 모델이 1:1이어야 하고, 서버 기본값이 없으면
    #   ORM을 거치지 않는 raw SQL INSERT가 NOT NULL에 걸린다.
    sort_order: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
