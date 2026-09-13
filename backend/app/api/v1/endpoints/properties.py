"""숙소·객실·침대 라우터 (api_contract.md 2절).

경로에 `/api/v1` 접두사를 붙이지 않는다(api_router.py 참고).

응답은 공통 봉투 `{"data": ..., "error": null}`로 감싼다(0절). 실패 경로는
서비스가 `AppError`를 던지고 `main.py`의 예외 핸들러가 같은 봉투로 감싸므로
여기서 try/except를 두지 않는다 — `channels.py`와 같은 규약이다.

**목록 응답에 `meta`를 넣지 않는다.** 0절 규약의 예외를 2절·2.1절·2.2절이
각각 명시한다. 셋 다 이유가 같다 — 이 응답들은 화면이 그리는 **선택지의
입력**이라 일부만 받으면 존재하는 항목이 선택지에서 누락된다.

## 경로 등록 순서

이 파일은 `/properties` · `/properties/{property_id}` ·
`/properties/{property_id}/rooms` · `/rooms/{room_id}/beds` 넷을 등록한다.
**서로 삼키지 않는다** — `/properties`는 세그먼트 1개, `{property_id}`는 2개,
`rooms`는 3개로 길이가 갈리고, `{property_id}` 자리와 겹치는 **리터럴
세그먼트가 하나도 없다**(`/properties/summary` 같은 것이 생기면 그때는
`{property_id}`보다 **먼저** 등록해야 한다 — FastAPI는 선언 순서대로
매칭한다).

`channels.py`의 `/properties/{property_id}/channels`와도 마지막 세그먼트가
달라 충돌하지 않는다.
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_host_id
from app.schemas.property import (
    BedCreateRequest,
    BedResponse,
    PropertyCreateRequest,
    PropertyDetailResponse,
    PropertySummaryResponse,
    PropertyUpdateRequest,
    RoomCreateRequest,
    RoomResponse,
)
from app.services import property_service

router = APIRouter(tags=["properties"])

DbSession = Annotated[AsyncSession, Depends(get_db)]
CurrentHostId = Annotated[int, Depends(get_current_host_id)]


@router.get("/properties", summary="내 숙소 목록(드롭다운·대시보드 입력)")
async def list_properties(db: DbSession, host_id: CurrentHostId) -> dict[str, Any]:
    """**4필드만** 반환한다(2절). 상세 11필드는 아래 단건 조회 소관이다."""
    props = await property_service.list_properties(db, host_id=host_id)
    return {
        "data": [
            PropertySummaryResponse.model_validate(p).model_dump() for p in props
        ],
        "error": None,
    }


@router.get("/properties/{property_id}", summary="숙소 상세(/settings 화면)")
async def get_property(
    property_id: int, db: DbSession, host_id: CurrentHostId
) -> dict[str, Any]:
    """**11필드**를 반환한다(2.4절). 없거나 타인 소유면 404(0절)."""
    prop = await property_service.get_property_detail(
        db, property_id=property_id, host_id=host_id
    )
    return {
        "data": PropertyDetailResponse.model_validate(prop).model_dump(),
        "error": None,
    }


@router.get("/properties/{property_id}/rooms", summary="객실 목록")
async def list_rooms(
    property_id: int, db: DbSession, host_id: CurrentHostId
) -> dict[str, Any]:
    """판매단위가 `PROPERTY`면 **빈 배열이 정상**이다 — 404가 아니다(2.1절)."""
    rooms = await property_service.list_rooms(
        db, property_id=property_id, host_id=host_id
    )
    return {
        "data": [RoomResponse.model_validate(r).model_dump() for r in rooms],
        "error": None,
    }


@router.get("/rooms/{room_id}/beds", summary="침대 목록")
async def list_beds(
    room_id: int, db: DbSession, host_id: CurrentHostId
) -> dict[str, Any]:
    """경로에 `property_id`가 없어 조인으로 소유권을 본다(2.2절).

    내 객실인데 침대가 없으면 `200 + []`, 남의 객실이거나 없는 객실이면
    `404`다 — 둘을 혼동하지 않는다(2.2절).
    """
    beds = await property_service.list_beds(db, room_id=room_id, host_id=host_id)
    return {
        "data": [BedResponse.model_validate(b).model_dump() for b in beds],
        "error": None,
    }


@router.post(
    "/properties",
    status_code=status.HTTP_201_CREATED,
    summary="숙소 등록(온보딩 STEP 1)",
)
async def create_property(
    payload: PropertyCreateRequest, db: DbSession, host_id: CurrentHostId
) -> dict[str, Any]:
    """**201**이고 응답은 목록의 4필드가 아니라 **상세와 같은 11필드**다(2.3절).

    등록 직후 온보딩 위저드가 방금 만든 숙소의 전체 상태를 그려야 한다 —
    목록 형태로 돌려주면 클라이언트가 `GET /properties/{id}`를 곧바로 한 번
    더 호출하게 된다.
    """
    prop = await property_service.create_property(db, host_id=host_id, payload=payload)
    await db.commit()
    return {
        "data": PropertyDetailResponse.model_validate(prop).model_dump(),
        "error": None,
    }


@router.patch("/properties/{property_id}", summary="숙소 정보 수정(/settings)")
async def update_property(
    property_id: int,
    payload: PropertyUpdateRequest,
    db: DbSession,
    host_id: CurrentHostId,
) -> dict[str, Any]:
    """보낸 필드만 바꾸고 **갱신 후 전체 11필드**를 돌려준다(2.5절).

    `accommodation_type`·`bookable_unit_type`이 담겨 오면
    **400 `IMMUTABLE_FIELD`**다 — 무시하지 않는다. 빈 본문은 에러가 아니라
    현재 상태를 그대로 돌려주는 `200`이다.
    """
    prop = await property_service.update_property(
        db, property_id=property_id, host_id=host_id, payload=payload
    )
    await db.commit()
    return {
        "data": PropertyDetailResponse.model_validate(prop).model_dump(),
        "error": None,
    }


@router.post(
    "/properties/{property_id}/rooms",
    status_code=status.HTTP_201_CREATED,
    summary="객실 등록",
)
async def create_room(
    property_id: int,
    payload: RoomCreateRequest,
    db: DbSession,
    host_id: CurrentHostId,
) -> dict[str, Any]:
    """**201**이고 응답은 객실 목록의 원소 하나와 같은 모양이다(2.6절).

    등록 직후 화면이 목록에 그 항목을 덧붙이기만 하면 된다. 판매단위가
    `PROPERTY`면 400, 같은 이름이 있으면 409다.
    """
    room = await property_service.create_room(
        db, property_id=property_id, host_id=host_id, payload=payload
    )
    await db.commit()
    return {"data": RoomResponse.model_validate(room).model_dump(), "error": None}


@router.post(
    "/rooms/{room_id}/beds",
    status_code=status.HTTP_201_CREATED,
    summary="침대 등록",
)
async def create_bed(
    room_id: int,
    payload: BedCreateRequest,
    db: DbSession,
    host_id: CurrentHostId,
) -> dict[str, Any]:
    """경로에 `property_id`가 없어 **객실에서 숙소를 역추적**해 검증한다(2.6절).

    `BED` 단위 숙소가 아니면 400, 같은 라벨이 있으면 409, 남의 객실이거나
    없는 객실이면 404다.
    """
    bed = await property_service.create_bed(
        db, room_id=room_id, host_id=host_id, payload=payload
    )
    await db.commit()
    return {"data": BedResponse.model_validate(bed).model_dump(), "error": None}
