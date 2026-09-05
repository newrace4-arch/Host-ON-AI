"""HOSTS — DB명세서 v1.3 2.1절."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.property import Property


class Host(Base):
    """숙소 운영자(1인 멀티호스트).

    ※ phone 컬럼은 의도적으로 두지 않는다(명세서 2.1절): 호스트 본인에게
      전화/문자를 보내는 기능이 현재 설계에 없어 실사용처가 없다.
    """

    __tablename__ = "hosts"

    host_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    properties: Mapped[list["Property"]] = relationship(
        back_populates="host",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
