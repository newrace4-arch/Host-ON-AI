"""채널 연동 서비스 — CHANNEL_CONNECTIONS CRUD.

소유권 검증은 전부 **조회 조건**으로 처리한다. 파이썬 `if`로 나중에
검사하지 않는다(빠뜨리면 조용히 통과하는 종류라서). 부존재와 타인 소유를
구분하지 않고 똑같이 404를 던지는 이유는 api_contract.md 0절 참고 —
id를 1씩 올려가며 403/404를 구분해 받으면 어떤 id가 실재하는지 외부에서
추론할 수 있다.

`connection_id`만 받는 엔드포인트(`DELETE /channels/{id}`,
`POST /channels/{id}/sync`)는 URL에 `property_id`가 없으므로
**`JOIN properties ON ... WHERE properties.host_id = :host_id`를 단일
쿼리로** 묶어 검증한다(CLAUDE.md 코딩 규칙 1).
"""

from __future__ import annotations

from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppError, ResourceNotFoundError
from app.models.channel import ChannelConnection
from app.models.property import Property
from app.schemas.channel import ChannelConnectionCreateRequest
from app.services.reservation_service import get_owned_property
from app.utils.db_errors import violates_constraint


class ChannelAlreadyConnectedError(AppError):
    """같은 숙소에 같은 채널을 두 번 연결하려 한 경우(409).

    DB의 `UNIQUE(property_id, channel)` 제약과 짝을 이룬다
    (api_contract.md 3절: MVP는 채널당 연결 1개).
    """

    status_code = 409
    code = "CHANNEL_ALREADY_CONNECTED"


async def list_channels(
    db: AsyncSession, *, property_id: int, host_id: int
) -> list[ChannelConnection]:
    """숙소의 채널 연결 목록. 숙소 소유권을 먼저 확인한다."""
    await get_owned_property(db, property_id, host_id)

    stmt = (
        select(ChannelConnection)
        .where(ChannelConnection.property_id == property_id)
        .order_by(ChannelConnection.connection_id)
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_owned_connection(
    db: AsyncSession, connection_id: int, host_id: int
) -> ChannelConnection:
    """`connection_id`만으로 접근하는 경로의 IDOR 방어(단일 쿼리).

    properties를 조인해 `host_id`를 조회 조건에 함께 넣는다. 연결이 없든
    타인 소유든 똑같이 404다.
    """
    stmt = (
        select(ChannelConnection)
        .join(Property, Property.property_id == ChannelConnection.property_id)
        .where(
            ChannelConnection.connection_id == connection_id,
            Property.host_id == host_id,
        )
    )
    conn = await db.scalar(stmt)
    if conn is None:
        raise ResourceNotFoundError("요청한 채널 연결을 찾을 수 없습니다.")
    return conn


async def create_channel(
    db: AsyncSession,
    *,
    property_id: int,
    host_id: int,
    payload: ChannelConnectionCreateRequest,
) -> ChannelConnection:
    """채널 연결 등록.

    **등록 시점에 iCal URL 유효성을 검증하지 않는다**(api_contract 3.2절).
    확인하려면 외부 네트워크 호출이 필요한데 코딩규칙 11번이 그 호출에
    5초 타임아웃을 요구한다 — 등록 요청을 그만큼 붙잡아 두는 대신
    `SYNCING`으로 저장하고, 실패는 동기화가 `FAILED`로 남긴다.
    """
    await get_owned_property(db, property_id, host_id)

    conn = ChannelConnection(
        property_id=property_id,
        channel=payload.channel,
        ical_url=payload.ical_url,
        external_property_id=payload.external_property_id,
    )
    db.add(conn)
    try:
        await db.flush()
    except IntegrityError as exc:
        await db.rollback()
        if violates_constraint(exc, "uq_property_channel"):
            raise ChannelAlreadyConnectedError(
                "이 숙소에 이미 연결된 채널입니다. "
                "URL을 바꾸려면 연결을 해제한 뒤 다시 등록하십시오."
            ) from exc
        raise

    return conn


async def delete_channel(db: AsyncSession, *, connection_id: int, host_id: int) -> None:
    """채널 연결 해제.

    ⚠️ RESERVATIONS.channel_connection_id는 NOT NULL이고 FK가 걸려 있어,
    이 연결로 들어온 예약이 남아 있으면 DB가 삭제를 거부한다(23503).
    그 경우 500으로 새어 나가지 않게 도메인 예외로 옮긴다.
    """
    conn = await get_owned_connection(db, connection_id, host_id)

    try:
        await db.execute(
            delete(ChannelConnection).where(
                ChannelConnection.connection_id == conn.connection_id
            )
        )
        await db.flush()
    except IntegrityError as exc:
        await db.rollback()
        raise AppError(
            "이 채널로 등록된 예약이 남아 있어 연결을 해제할 수 없습니다.",
            code="CHANNEL_HAS_RESERVATIONS",
        ) from exc
