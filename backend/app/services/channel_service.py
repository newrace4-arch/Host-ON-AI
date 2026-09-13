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
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppError, ResourceNotFoundError
from app.models.channel import ChannelConnection
from app.models.property import Property
from app.models.settlement import ChannelFeeRate
from app.schemas.channel import ChannelConnectionCreateRequest
from app.services.reservation_service import get_owned_property
from app.utils.db_errors import violates_constraint


class ChannelAlreadyConnectedError(AppError):
    """같은 숙소·같은 채널·같은 객실 조합을 두 번 연결하려 한 경우(409).

    DB의 **`CHANNEL_CONNECTIONS.uq_property_channel`** 제약과 짝을 이룬다.
    **[v1.4] 컬럼이 `(property_id, channel)`에서
    `(property_id, channel, room_id)`로 늘었고 `NULLS NOT DISTINCT`가
    붙었다.** 제약 **이름은 그대로 유지**한다 — 이 클래스가 그 이름으로
    `IntegrityError`를 409로 번역하기 때문이다.

    **"채널당 연결 1개"는 독채에만 해당한다**(api_contract 3절).
    판매단위가 `PROPERTY`인 숙소는 `room_id`가 항상 NULL인데
    `NULLS NOT DISTINCT`가 NULL을 서로 같은 값으로 취급하므로
    `(숙소, 채널)`당 하나로 제한된다. **호스텔은 객실마다 별도 iCal
    피드가 나오므로 같은 채널의 연결이 여러 개 존재할 수 있다** —
    그것이 v1.4에서 `room_id`를 추가한 이유다(db_spec 2.5절).
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

    **[v1.4] 요율 행을 함께 만든다** — `CHANNEL_FEE_RATES`에
    `(property_id, channel)` 행이 없으면 기본값으로 만들고, **있으면
    그대로 둔다**(db_spec 2.19절). 요청·응답은 바뀌지 않는 내부
    불변식이라 api_contract 3.2절은 그대로다.

    ⚠️ **그 INSERT는 예외를 내지 않는다 — 그래야 한다.**
    `ON CONFLICT DO NOTHING`이라 중복이 있어도 조용히 0행을 넣는다.
    예외를 냈다면 아래 `except IntegrityError` 분기로 흘러가는데, 그
    분기의 `rollback()`은 **트랜잭션 전체를 되돌려 방금 만든 채널 연결까지
    사라지게 한다.** 게다가 제약 이름이 `uq_property_channel`이 아니므로
    409로 번역되지도 않고 `raise`로 500이 된다. 그래서 예외를 잡는 대신
    **예외가 발생할 여지 자체를 없앴다.**

    ⚠️ **`DO UPDATE`를 쓰지 않는다.** 호스트가 고쳐 둔 요율을 덮어쓴다.
    연결을 지웠다 다시 만드는 것은 흔한 일이고(iCal URL 변경에 `PATCH`가
    없다), 그때마다 요율이 기본값으로 되돌아가면 안 된다.
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

    # v1.4: 요율 행이 없으면 기본값으로 만든다. 있으면 그대로 둔다.
    #   ORM add()가 아니라 INSERT ... ON CONFLICT DO NOTHING을 쓰는 이유는
    #   위 도크스트링 참고(예외 경로로 가면 연결까지 롤백된다).
    #   충돌 대상을 제약 이름이 아니라 **컬럼 목록**으로 추론하게 둔다 —
    #   ⑤ 마이그레이션의 백필이 쓰는 형태와 같아 두 경로가 한 문장으로
    #   읽힌다. 기본값 3종(SINGLE_FEE / 0.1550 / system_default_2026)은
    #   DB의 server_default가 채운다.
    #   flush() **뒤**에 둔다 — 커밋은 라우터가 하므로 연결과 요율이 한
    #   트랜잭션에 묶이는 것은 그대로다.
    await db.execute(
        pg_insert(ChannelFeeRate)
        .values(property_id=property_id, channel=payload.channel)
        .on_conflict_do_nothing(index_elements=["property_id", "channel"])
    )

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
