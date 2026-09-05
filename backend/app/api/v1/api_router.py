"""모든 도메인 라우터 취합 지점 (CLAUDE.md 디렉토리 규격).

경로에 `/api/v1` 같은 접두사를 붙이지 않는다 — api_contract.md가
`GET /health`, `POST /reservations`처럼 **접두사 없는 경로**로 스펙을
정의하고 있어서다. `v1` 디렉토리는 코드 구조상의 버전 구분일 뿐이며,
버전 접두사를 도입하려면 API Contract를 먼저 고쳐야 한다.

도메인 라우터는 구현되는 대로 여기에 추가한다(12개 예정:
auth / properties / channels / reservations / settlements / cleaning /
inquiries / rag / action_items / compliance / health).
"""

from fastapi import APIRouter

from app.api.v1.endpoints import health

api_router = APIRouter()

api_router.include_router(health.router)
