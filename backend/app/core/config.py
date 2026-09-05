"""환경변수 SSOT (pydantic-settings).

CLAUDE.md 디렉토리 규격: backend/app/core/config.py
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # DB — 애플리케이션 런타임은 async 드라이버(asyncpg)를 사용한다
    DATABASE_URL: str = (
        "postgresql+asyncpg://hoston:hoston_local_dev@localhost:5432/host_on_ai"
    )

    # JWT
    JWT_SECRET_KEY: str = "change-me-in-production"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440

    # 외부 API
    ANTHROPIC_API_KEY: str = ""

    # CORS (콤마 구분 문자열)
    CORS_ORIGINS: str = "http://localhost:5173"

    @property
    def sync_database_url(self) -> str:
        """Alembic 마이그레이션 전용 동기 URL.

        Alembic은 동기 드라이버(psycopg)로 실행하는 편이 EXCLUDE 제약 등
        원시 DDL(op.execute)을 다루기 단순하다.
        """
        return self.DATABASE_URL.replace("+asyncpg", "+psycopg")

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
