"""대시보드 응답 DTO (api_contract.md 4.1절).

## 🔴 12필드다 — 문서의 "11개"는 문구 오류다

4.1절 본문이 두 곳에서 *"11개 필드"*·*"11필드 고정 계약"*이라고 적었으나
**같은 절의 JSON 예시 키는 12개**다. 프론트 수기 타입도 12로 적혀 있다
(`frontend/src/types/api.ts`: *"12개 키 전부 항상 존재한다(옵셔널 아님)"*).

앞쪽 *"아래 11개 필드는 전부 기존 16개 테이블의 **실재 컬럼에서 집계**"*는
읽기에 따라 맞다 — `conflict_count`는 같은 절이 *"DB 컬럼이 아니라 서버가
매 조회 시 계산하는 파생 필드"*로 못박았으므로 실재 컬럼 11 + 파생 1이다.
**틀린 것은 뒤쪽 "11필드 고정 계약"이다.**

문서 문구 정정은 9/15 목록으로 넘긴다(14-30 결정). 구현은 12로 간다.

## 기본값을 두지 않는다

`data: T | None = None`처럼 기본값을 주면 OpenAPI에서 `required`가 빠지고
`openapi-typescript`가 **`?:`(optional)**로 뽑는다. 프론트는 12개를 전부
필수로 알고 있으므로 **타입이 조용히 어긋난다**(`schemas/common.py`가
`Envelope.data`에 기본값을 두지 않은 것과 같은 이유, 9/14 실측).

`conflict_count`는 `int | None`이지만 **기본값은 없다** — "값이 null일 수
있다"와 "키가 없어도 된다"는 다르다. 4.1절: *"**키는 항상 포함한다.** 계산
실패 시 값을 `null`로 반환한다."*
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class DashboardSummaryResponse(BaseModel):
    """`GET /properties/{property_id}/dashboard/summary`의 `data`.

    필드 순서는 4.1절 JSON 예시와 같게 둔다 — 식별 2개 / 오늘 3개 /
    액션 4개 / 청소 2개 / 파생 1개. 생성되는 TS와 문서를 나란히 놓고
    읽을 수 있어야 한다.
    """

    # `dashboard_service.DashboardSummary`(frozen dataclass)를 그대로 받는다.
    model_config = ConfigDict(from_attributes=True)

    property_id: int
    # ⚠️ 컬럼은 `PROPERTIES.name`인데 응답 키는 `property_name`이다(4.1절).
    #   프론트가 3~5개 숙소분을 병렬 호출해 합산하므로 **어느 숙소의
    #   응답인지 식별이 필요**하다.
    property_name: str

    today_checkin_count: int
    today_checkout_count: int
    today_turnover_count: int

    open_action_count: int
    red_now_count: int
    yellow_today_count: int
    green_auto_count: int

    cleaning_pending_count: int
    cleaning_issue_count: int

    # 🔴 유일하게 null이 될 수 있는 필드. 계산 실패 시 null이고 나머지
    #   11개는 정상값이다(Graceful Degradation, 4.1절).
    #   프론트는 **0(충돌 없음)과 null(계산 실패)을 구분해 표시**하며,
    #   합산에서도 제외한다(`useDashboardSummary.sumTotals` 도크스트링).
    conflict_count: int | None
