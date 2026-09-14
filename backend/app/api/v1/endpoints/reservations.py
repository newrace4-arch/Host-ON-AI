"""예약 라우터 (api_contract.md 4.3~4.6절).

경로에 `/api/v1` 접두사를 붙이지 않는다(api_router.py 참고).

`properties.py`와 같은 규약이다 — **라우터는 얇고**, 소유권은 서비스가
조회 조건에 묶고, **커밋은 라우터가** 하며, 실패 경로는 서비스가 `AppError`를
던지고 `main.py`의 예외 핸들러가 봉투로 감싸므로 **여기에 try/except를 두지
않는다.**

## 🔴 `response_model`을 붙인 첫 라우터다

기존 17개는 `-> dict[str, Any]`만 두어 **OpenAPI에 응답 스키마가 하나도
실리지 않았다**(9/14 실측 — `components.schemas` 12개가 전부 요청·검증용).
그래서 프론트 타입을 자동 생성해도 응답이 `Record<string, never>`가 된다.

`response_model=Envelope[X]`를 붙이면 **본문을 고치지 않고도** 스키마가
실린다 — 지금처럼 `{"data": ..., "error": None}` dict를 반환하면 된다.
기존 17개는 이번에 건드리지 않는다(예약 4개부터 적용).

> 대가가 하나 있다 — 반환 형태가 선언과 어긋나면 `ResponseValidationError`로
> **500**이 난다(400이 아니다). 그래서 엔드포인트마다 통합 테스트를 함께
> 둔다. 테스트가 없으면 배포 후에 안다.

**`meta`는 넣지 않는다.** 4.3절이 0절 메타 규약의 예외로 명시한다 —
캘린더는 그 기간 전부를 받아야 하므로 페이지네이션이 구조적으로 적용될 수
없다.
"""

from __future__ import annotations

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_host_id
from app.schemas.common import Envelope
from app.schemas.reservation import (
    ReservationCreateRequest,
    ReservationResponse,
    ReservationStatusUpdateRequest,
)
from app.services import reservation_service

router = APIRouter(tags=["reservations"])

DbSession = Annotated[AsyncSession, Depends(get_db)]
CurrentHostId = Annotated[int, Depends(get_current_host_id)]


@router.get(
    "/properties/{property_id}/reservations",
    response_model=Envelope[list[ReservationResponse]],
    summary="예약 목록(캘린더 그리드용, 기간 필터)",
)
async def list_reservations(
    property_id: int,
    db: DbSession,
    host_id: CurrentHostId,
    start: Annotated[date, Query(description="조회 시작일(포함)")],
    end: Annotated[date, Query(description="조회 종료일(포함)")],
) -> dict:
    """그 기간에 **걸치는** 예약 전부를 돌려준다(4.3절).

    달을 가로지르는 예약도 포함된다 — 빠뜨리면 그리드에서 막대가 끊긴다.
    `is_conflict`는 읽어 온 목록 안에서 쌍끼리 비교해 채운다(N+1 회피).
    """
    rows = await reservation_service.list_reservations(
        db, property_id=property_id, host_id=host_id, start=start, end=end
    )
    return {
        "data": [
            ReservationResponse.from_model(r, is_conflict=c) for r, c in rows
        ],
        "error": None,
    }


@router.get(
    "/reservations/{reservation_id}",
    response_model=Envelope[ReservationResponse],
    summary="예약 상세(캘린더 상세 모달)",
)
async def get_reservation(
    reservation_id: int, db: DbSession, host_id: CurrentHostId
) -> dict:
    """경로에 `property_id`가 없어 **조인으로 소유권을 본다**(0절·4.4절).

    없는 예약과 남의 예약을 구분하지 않고 둘 다 404다.
    """
    reservation = await reservation_service.get_owned_reservation(
        db, reservation_id, host_id
    )
    conflict = await reservation_service.is_conflicting(db, reservation)
    return {
        "data": ReservationResponse.from_model(reservation, is_conflict=conflict),
        "error": None,
    }


@router.post(
    "/reservations",
    status_code=status.HTTP_201_CREATED,
    response_model=Envelope[ReservationResponse],
    summary="예약 생성(수동 등록 / iCal 동기화 공용)",
)
async def create_reservation(
    payload: ReservationCreateRequest, db: DbSession, host_id: CurrentHostId
) -> dict:
    """**201**. 소유권(404) → 계층(400 3종) → 겹침(409) 순으로 막는다(4.5절).

    `net_amount`는 요청에서 받지 않는다 — 생성 컬럼이라 INSERT에 실리면
    PostgreSQL이 거부한다(`ReservationCreateRequest` 주석).

    **방금 만든 예약은 `is_conflict=false`다.** 겹치면 그 자리에서 409로
    막혀 여기까지 오지 못하므로, 다시 조회하지 않는다.
    """
    reservation = await reservation_service.create_reservation(
        db, host_id=host_id, payload=payload
    )
    await db.commit()
    return {
        "data": ReservationResponse.from_model(reservation, is_conflict=False),
        "error": None,
    }


@router.patch(
    "/reservations/{reservation_id}/status",
    response_model=Envelope[ReservationResponse],
    summary="예약상태/환불상태/정산상태 개별 수정",
)
async def update_reservation_status(
    reservation_id: int,
    payload: ReservationStatusUpdateRequest,
    db: DbSession,
    host_id: CurrentHostId,
) -> dict:
    """3필드 전부 Optional. 보낸 것만 바꾸고 **갱신 후 전체 상태**를 준다(4.6절).

    허용되지 않는 전이와 무의미한 조합은 **400 `INVALID_STATUS_TRANSITION`**
    이다. 빈 본문은 에러가 아니라 현재 상태를 그대로 돌려주는 200이다.
    """
    reservation = await reservation_service.update_reservation_status(
        db, reservation_id=reservation_id, host_id=host_id, payload=payload
    )
    await db.commit()
    conflict = await reservation_service.is_conflicting(db, reservation)
    return {
        "data": ReservationResponse.from_model(reservation, is_conflict=conflict),
        "error": None,
    }
