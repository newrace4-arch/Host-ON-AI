"""채널 연동 라우터 (api_contract.md 3절).

경로에 `/api/v1` 접두사를 붙이지 않는다(api_router.py 참고).

응답은 공통 봉투 `{"data": ..., "error": null}`로 감싼다(0절). 실패 경로는
서비스가 `AppError`를 던지고 `main.py`의 예외 핸들러가 같은 봉투로
감싸므로 여기서 try/except를 두지 않는다.

**목록 응답에 `meta`를 넣지 않는다** — 0절 규약의 예외로 3절이 명시하고
있다(채널은 페이지네이션 대상이 아니다).
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_host_id
from app.schemas.channel import (
    ChannelConnectionCreateRequest,
    ChannelConnectionResponse,
    SyncErrorResponse,
    SyncResultResponse,
)
from app.services import channel_service, ical_sync

router = APIRouter(tags=["channels"])

DbSession = Annotated[AsyncSession, Depends(get_db)]
CurrentHostId = Annotated[int, Depends(get_current_host_id)]


@router.get(
    "/properties/{property_id}/channels",
    summary="연동 채널 목록(동기화 상태 포함)",
)
async def list_channels(
    property_id: int, db: DbSession, host_id: CurrentHostId
) -> dict[str, Any]:
    conns = await channel_service.list_channels(
        db, property_id=property_id, host_id=host_id
    )
    return {
        "data": [ChannelConnectionResponse.from_model(c).model_dump() for c in conns],
        "error": None,
    }


@router.post(
    "/properties/{property_id}/channels",
    status_code=status.HTTP_201_CREATED,
    summary="iCal URL 등록(Airbnb/Booking.com/네이버)",
)
async def create_channel(
    property_id: int,
    payload: ChannelConnectionCreateRequest,
    db: DbSession,
    host_id: CurrentHostId,
) -> dict[str, Any]:
    conn = await channel_service.create_channel(
        db, property_id=property_id, host_id=host_id, payload=payload
    )
    await db.commit()
    return {"data": ChannelConnectionResponse.from_model(conn).model_dump(), "error": None}


@router.delete(
    "/channels/{connection_id}",
    summary="채널 연동 해제",
)
async def delete_channel(
    connection_id: int, db: DbSession, host_id: CurrentHostId
) -> dict[str, Any]:
    await channel_service.delete_channel(
        db, connection_id=connection_id, host_id=host_id
    )
    await db.commit()
    return {"data": {"connection_id": connection_id, "deleted": True}, "error": None}


@router.post(
    "/channels/{connection_id}/sync",
    summary="수동 동기화 트리거",
)
async def sync_channel(
    connection_id: int, db: DbSession, host_id: CurrentHostId
) -> dict[str, Any]:
    """iCal을 가져와 예약에 반영한다.

    **동기화 실패는 이 엔드포인트의 실패가 아니다.** 외부 서버가 응답하지
    않거나 깨진 데이터를 보낸 것은 호스트가 조치할 일이지 요청 자체의
    오류가 아니므로, 200으로 응답하고 `sync_status=FAILED`와
    `last_error_message`로 결과를 알린다(Graceful Degradation, 규칙 11).
    404는 연결이 없거나 타인 소유일 때만 난다.
    """
    conn, outcome = await ical_sync.sync_connection(
        db, connection_id=connection_id, host_id=host_id
    )
    body = SyncResultResponse(
        connection_id=conn.connection_id,
        sync_status=conn.sync_status,
        last_synced_at=conn.last_synced_at,
        last_error_message=ChannelConnectionResponse.from_model(conn).last_error_message,
        created_count=outcome.created,
        updated_count=outcome.updated,
        unchanged_count=outcome.unchanged,
        skipped_no_room_count=outcome.skipped_no_room,
        skipped_overlap_count=outcome.skipped_overlap,
        failed_count=outcome.failed,
        invalid_event_count=outcome.invalid_events,
    )
    return {"data": body.model_dump(), "error": None}


@router.get(
    "/channels/{connection_id}/sync-errors",
    summary="동기화 실패 사유 조회(sync_status=FAILED일 때)",
)
async def get_sync_errors(
    connection_id: int, db: DbSession, host_id: CurrentHostId
) -> dict[str, Any]:
    """실패 이력을 누적하지 않는다 — `last_error_message` 1건만 반환(v1.6)."""
    conn = await channel_service.get_owned_connection(db, connection_id, host_id)
    body = SyncErrorResponse(
        connection_id=conn.connection_id,
        sync_status=conn.sync_status,
        last_synced_at=conn.last_synced_at,
        # FAILED가 아니면 항상 null(v1.3 운용 규칙) — 지난 에러가 화면에 남지 않게.
        last_error_message=ChannelConnectionResponse.from_model(conn).last_error_message,
    )
    return {"data": body.model_dump(), "error": None}
