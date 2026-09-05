"""SQLAlchemy 2.0 비동기 엔진/세션 + 선언적 Base.

모든 모델은 이 파일의 Base를 상속한다(claude_code_db_schema_instruction.md 2단계).
"""

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings


class Base(DeclarativeBase):
    """전체 모델의 공통 선언적 베이스."""


engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,
    pool_pre_ping=True,
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI 의존성 주입용 세션 제공자."""
    async with AsyncSessionLocal() as session:
        yield session
