"""KNOWLEDGE_CHUNKS — DB명세서 v1.3 2.14절 (RAG 정적 지식 콘텐츠).

벡터 저장소는 **PostgreSQL + pgvector 확장** 하나로 처리한다. 별도 벡터DB
서버(ChromaDB 등)를 도입하지 않는다(CLAUDE.md 확정 사항).
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.enums import DocumentType, document_type_enum

try:  # pragma: no cover - 임포트 형태만 다르고 동작은 동일
    from pgvector.sqlalchemy import Vector
except ImportError as exc:  # pragma: no cover
    raise ImportError(
        "pgvector 패키지가 필요합니다. `pip install pgvector` 후 다시 실행하세요."
    ) from exc

if TYPE_CHECKING:
    from app.models.property import Property

# 로컬 무료 임베딩 모델(sentence-transformers 계열) 기준 차원수.
#   모델을 바꾸면 이 값과 마이그레이션을 함께 수정해야 한다.
EMBEDDING_DIM = 384


class KnowledgeChunk(Base):
    """숙소별 지식 청크(하우스룰/정책/FAQ).

    ⚠️ 가장 위험한 누락 지점(명세서 4절 -1번): RAG 검색 시 반드시
    `WHERE property_id = :pid` 필터를 걸어야 한다. 이 필터가 없으면
    "숙소A 문의에 숙소B 하우스룰이 섞여 답변되는" 교차오답이 발생한다.
    """

    __tablename__ = "knowledge_chunks"
    __table_args__ = (Index("idx_knowledge_chunks_property", "property_id"),)

    chunk_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    property_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("properties.property_id", ondelete="CASCADE"), nullable=False
    )
    document_type: Mapped[DocumentType] = mapped_column(document_type_enum, nullable=False)
    category: Mapped[str | None] = mapped_column(String(50))
    content: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(EMBEDDING_DIM))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    property: Mapped["Property"] = relationship(back_populates="knowledge_chunks")

    # 초기 구현은 인덱스 없이 정확검색으로 시작한다(명세서 2.14절):
    #   SELECT ... WHERE property_id = :pid ORDER BY embedding <=> :query LIMIT 5;
    # 데이터가 늘어나면 HNSW 인덱스를 추가한다:
    #   CREATE INDEX ON knowledge_chunks USING hnsw (embedding vector_cosine_ops);
