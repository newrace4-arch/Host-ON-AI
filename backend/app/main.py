"""FastAPI 진입점 — CORS, 라이프스팬, 에러 응답 포맷 통일.

실행:
    cd backend && uvicorn app.main:app --reload
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.v1.api_router import api_router
from app.core.config import settings
from app.core.database import engine
from app.core.exceptions import AppError


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """시작 시 DB에 접속하지 않는다.

    Render 무료 플랜은 슬립에서 깨어날 때마다 이 과정을 다시 거치므로,
    기동 경로에 DB 왕복을 넣으면 첫 요청 지연이 그만큼 길어진다. 커넥션은
    실제 요청이 들어올 때 풀이 알아서 만든다. 종료 시에는 열린 커넥션을
    정리한다.
    """
    yield
    await engine.dispose()


app = FastAPI(
    title="Host ON (AI) API",
    description=(
        "여러 숙박업 유형을 운영하는 1인 멀티호스트를 위한 숙소 운영 자동화 API. "
        "모든 조회는 Property 단위 데이터 격리 원칙을 따른다."
    ),
    version="0.1.0",
    lifespan=lifespan,
)

# 프론트(Vercel) ↔ 백엔드(Render) 분리 배포라 CORS가 필수다.
#   허용 도메인은 .env의 CORS_ORIGINS(콤마 구분)로 관리한다 — 배포 전환 시
#   코드 수정 없이 환경변수만 바꾸기 위함.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(AppError)
async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    """도메인 예외 → api_contract.md 0절 응답 포맷."""
    return JSONResponse(
        status_code=exc.status_code,
        content={"data": None, "error": exc.to_error_body()},
    )


@app.exception_handler(RequestValidationError)
async def validation_error_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """Pydantic 검증 실패도 같은 봉투로 감싼다.

    FastAPI 기본 422 응답은 `{"detail": [...]}` 형태라 프론트가 에러 처리
    분기를 두 벌 만들어야 한다. 형식 오류는 400으로 통일한다.
    """
    return JSONResponse(
        status_code=400,
        content={
            "data": None,
            "error": {"code": "VALIDATION_ERROR", "message": str(exc.errors())},
        },
    )


app.include_router(api_router)
