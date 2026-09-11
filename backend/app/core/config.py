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

    # 실행 환경. **기본값을 production으로 둔다(fail-safe)** — 환경변수를
    #   빠뜨린 배포는 "개발 환경"으로 오인되지 않고 그 자리에서 막힌다.
    #   로컬은 .env에 ENV=development를 둔다.
    #   이 기본값과 아래 is_development의 판정은 tests/test_config.py가 지킨다.
    ENV: str = "production"

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
    def is_development(self) -> bool:
        """실행 환경이 개발인가.

        ⚠️ **지금 호출자가 0이다.** 9/11 인증 스텁 제거로 유일한 호출자
        (`dependencies.assert_auth_stub_safe`)가 사라졌다. 그래도 존치하는
        이유는 둘이다(9/10 조사 후 결정, 9/11 삭제 시 재확인).

        1. `ENV`는 `.env.example`과 배포 환경변수에 **이미 노출된 계약**이다.
           필드를 지우면 `model_config`의 `extra="ignore"` 때문에 환경변수를
           넣어도 **에러 없이 조용히 무시된다.**
        2. 기본값 `production`은 fail-safe다. 지웠다 되살리면 필드·프로퍼티·
           테스트·`.env.example` **네 곳**을 다시 건드려야 한다.

        **첫 실사용처 예정 — `JWT_SECRET_KEY` 기본값 가드(10/1).** 배포인데
        값이 `"change-me-in-production"` 그대로면 기동을 막는다.

        호출자가 없는 동안 판정 로직이 무검증으로 남지 않도록
        `tests/test_config.py`가 직접 검증한다 — 스텁 테스트에 얹혀 있던
        것을 9/11에 옮겼다.
        """
        return self.ENV.strip().lower() == "development"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
