"""헬스체크 (api_contract.md 11절).

Render 무료 플랜은 15분 미사용 시 슬립되므로 외부 핑(UptimeRobot/GitHub
Actions)으로 깨워야 한다. 비즈니스 API로 핑을 보내면 매번 DB 조회가 발생해
불필요하게 무거우므로 **DB를 건드리지 않는 전용 경량 엔드포인트**를 둔다.

⚠️ 이 라우터에 DB 세션 의존성(get_db)을 추가하지 말 것 — 존재 이유가 사라진다.
"""

from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/health", summary="헬스체크(인증 불필요, DB 조회 없음)")
async def health_check() -> dict[str, str]:
    """공통 `{data, error}` 봉투를 쓰지 않는 유일한 엔드포인트.

    외부 모니터링 도구가 그대로 파싱할 수 있도록 api_contract.md 11절에
    적힌 `{"status": "ok"}` 형태를 그대로 유지한다.
    """
    return {"status": "ok"}
