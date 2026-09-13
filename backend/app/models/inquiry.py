"""INQUIRIES / INQUIRY_CLASSIFICATIONS / INQUIRY_RESPONSES / INQUIRY_APPROVALS
/ RESPONSE_SOURCES — DB명세서 v1.4 2.10~2.13·2.17절.
"""

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
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
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

    **[v1.4] UNIQUE (inquiry_id, property_id)** — `INQUIRY_RESPONSES`가
    (inquiry_id, property_id) 복합 FK로 이 조합을 참조하기 위한 **후보키**다
    (명세서 2.10절). 복합 FK는 참조 대상에 그 컬럼 조합의 UNIQUE(또는 PK)가
    먼저 있어야 걸린다. `inquiry_id`가 이미 PK라 **중복방지 효과는 없으며**,
    ROOMS/BEDS의 `uq_*_ref` UNIQUE와 같은 목적이다.
    """

    __tablename__ = "inquiries"
    __table_args__ = (
        ForeignKeyConstraint(
            ["reservation_id", "property_id"],
            ["reservations.reservation_id", "reservations.property_id"],
            name="fk_inquiries_reservation_property",
            ondelete="CASCADE",
        ),
        # v1.4 신규: INQUIRY_RESPONSES 복합 FK의 참조 대상 후보키(중복방지 아님)
        UniqueConstraint("inquiry_id", "property_id", name="uq_inquiry_property_ref"),
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

    **[v1.4] property_id 추가 + 단독 FK → 복합 FK 교체** (명세서 2.12절):
    `RESPONSE_SOURCES`가 "응답과 청크가 같은 숙소인가"를 복합 FK로 검증하려면
    응답 쪽에도 `property_id`가 있어야 한다. 값은 **서버가
    `INQUIRIES.property_id`를 복사해 채운다**(요청 본문에서 받지 않는다 —
    받으면 호출부가 다른 숙소 id를 넣을 수 있고, 복합 FK가 그 INSERT를 거부해
    500으로 새어 나간다).

    **[v1.4] UNIQUE (response_id, property_id)** — `RESPONSE_SOURCES`가
    참조할 후보키. `response_id`가 이미 PK라 중복방지 효과는 없다.
    """

    __tablename__ = "inquiry_responses"
    __table_args__ = (
        # v1.4: inquiry_id 단독 FK → 복합 FK로 교체.
        #   "이 응답이 정말 이 숙소의 문의에 달린 응답인가"를 DB가 보장한다.
        ForeignKeyConstraint(
            ["inquiry_id", "property_id"],
            ["inquiries.inquiry_id", "inquiries.property_id"],
            name="fk_inquiry_responses_inquiry_property",
            ondelete="CASCADE",
        ),
        # v1.4 신규: RESPONSE_SOURCES 복합 FK의 참조 대상 후보키(중복방지 아님)
        UniqueConstraint("response_id", "property_id", name="uq_response_property_ref"),
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
    # v1.4: 인라인 단독 FK 제거 → __table_args__의 복합 FK로 이동
    inquiry_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    # ⚠️ 여기에는 property_id 단독 FK를 붙이지 않는다. 위 Inquiry(2.10)가 단독
    #   FK를 함께 갖는 것과 이유가 다르다 — Inquiry는 reservation_id가 nullable
    #   이라 MATCH SIMPLE 스킵이 일어나지만, 여기는 inquiry_id·property_id가
    #   **둘 다 NOT NULL**이라 스킵이 없고 복합 FK 하나로 격리가 보장된다.
    property_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    response_text: Mapped[str] = mapped_column(Text, nullable=False)
    # v1.4: sources(JSONB) 제거 → 2.17 RESPONSE_SOURCES 테이블로 분리
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


class ResponseSource(Base):
    """RESPONSE_SOURCES — AI 응답 ↔ 인용 청크 (N:N). 명세서 v1.4 2.17절.

    v1.3까지 `INQUIRY_RESPONSES.sources`(JSONB)에 `["chunk_17"]` 형태로 담던
    것을 대체한다. JSONB는 **FK가 걸리지 않아** 청크가 삭제돼도 값이 그대로
    남아 끊어진 참조가 됐고, DB가 아무것도 검증하지 못했다.

    ⚠️ **이 테이블만 대리키(BIGSERIAL)를 쓰지 않는다.** 나머지 18개는 전부
    단일 대리키를 PK로 쓰므로, 나중에 "일관성"을 이유로 되돌리지 않도록
    사유를 여기 남긴다(명세서 2.17절):
      1. **다른 테이블이 이 행을 참조하지 않는다.** 대리키가 필요한 가장 큰
         이유는 "남이 이 행을 가리킬 짧은 키"인데, 이 테이블을 FK로 참조하는
         테이블이 하나도 없고 앞으로도 없다(순수 연결 테이블).
      2. **(응답, 청크) 쌍 자체가 식별자다.** 같은 응답이 같은 청크를 두 번
         인용하는 일은 없으므로 복합 PK가 그 규칙을 추가 제약 없이 강제한다.
         대리키를 두면 UNIQUE(response_id, chunk_id)를 따로 걸어야 한다.
    `rank`는 PK에 넣지 않는다 — 순위는 속성이지 식별자가 아니다.

    ⚠️ **relationship을 만들지 않는다.** `property_id`가 두 복합 FK에 동시에
    참여해 SQLAlchemy가 overlaps 경고를 낸다. 행을 쓰는 곳이 RAG 검색 결과를
    저장하는 서버 코드(`app/services/ai/`) 한 곳뿐이라 ORM 캐스케이드가
    필요 없고, 삭제 정리는 DB의 ON DELETE CASCADE가 담당한다.

    두 FK가 모두 CASCADE인 이유(2.17절): `response_id` 쪽은 자명하다.
    `chunk_id` 쪽은 **RESTRICT를 쓸 수 없어서**다 — api_contract 8절에 청크
    **수정 API가 없어** 하우스룰을 고치는 유일한 방법이 "지우고 다시 등록"
    이므로, RESTRICT면 인용된 청크를 영원히 고칠 수 없게 된다. 대가는
    "무엇을 근거로 답했는지"가 사라지는 것이며, 게스트에게 실제로 나간
    `response_text` 원문은 그대로 남는다.
    """

    __tablename__ = "response_sources"
    __table_args__ = (
        ForeignKeyConstraint(
            ["response_id", "property_id"],
            ["inquiry_responses.response_id", "inquiry_responses.property_id"],
            name="fk_response_sources_response_property",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["chunk_id", "property_id"],
            ["knowledge_chunks.chunk_id", "knowledge_chunks.property_id"],
            name="fk_response_sources_chunk_property",
            ondelete="CASCADE",
        ),
        Index("idx_response_sources_chunk", "chunk_id"),
    )

    response_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    chunk_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    property_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    # RAG 검색 결과 순위(1이 가장 유사). 검색이 돌려준 순서를 그대로 넣는다.
    rank: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
