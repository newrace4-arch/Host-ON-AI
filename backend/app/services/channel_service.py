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

from app.core.exceptions import (
    AppError,
    InvalidUnitHierarchyError,
    ResourceNotFoundError,
)
from app.models.channel import ChannelConnection
from app.models.enums import BookableUnitType
from app.models.property import Property, Room
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


async def _validate_room_for_channel(
    db: AsyncSession, prop: Property, room_id: int | None
) -> None:
    """[v1.4] 채널 연결의 `room_id`가 이 숙소의 계층과 맞는지 검증한다.

    **404와 400을 나눈다**(api_contract 3.2절).

    | 경우 | 응답 |
    |---|---|
    | 존재하지 않는 `room_id` | **404** `RESOURCE_NOT_FOUND` |
    | 다른 숙소의 `room_id` | **404** `RESOURCE_NOT_FOUND` |
    | 내 숙소의 실재하는 객실인데 판매단위가 `PROPERTY` | **400** `INVALID_UNIT_HIERARCHY` |

    🔴 **앞의 둘을 400으로 돌려주면 존재 정보가 샌다.** 경로의
    `{property_id}`는 부존재와 타인 소유를 구분하지 않고 404로 막는데
    (0절), 본문의 `room_id`만 400을 주면 **"그 id는 존재하되 내 것이
    아니거나, 아예 없다"까지 좁혀진다.** id를 1씩 올려가며 응답 코드를
    비교하면 남의 객실 id 공간을 추론할 수 있다 — 0절이 403을 금지한
    것과 같은 이유다. 그래서 **한 쿼리로 `room_id`와 `property_id`를
    함께 조회해 없으면 404**를 던지고, 두 경우를 구분하지 않는다.

    **세 번째만 400인 이유**: 그 응답은 **요청자가 이미 아는 정보만으로
    판정된다.** 자기 숙소의 판매단위와 자기 객실의 존재는 이미 알고 있고,
    이 400은 새로운 사실을 알려주지 않는다. 고칠 방법도 명확하다 —
    `room_id`를 빼면 된다.

    🔴 **`reservation_service.validate_unit_hierarchy`를 재사용하면 안 된다.**
    이름이 비슷하고 에러 코드도 같아 **합치고 싶어지는 자리**지만 뜻이
    다르다.

      - `ROOM`/`BED` 숙소에서 `room_id`를 **그 함수는 필수로 본다**
        (없으면 `ROOM_ID_REQUIRED`/`BED_ID_REQUIRED`). **이 함수는
        선택으로 본다** — 없으면 숙소 전체 피드다.
      - `bed_id`는 이 함수가 다루지 않는다(채널 연결에 그 컬럼이 없다).

    재사용하면 **호스텔이 숙소 전체 피드 하나만 등록하려는 정상 요청이
    `ROOM_ID_REQUIRED`로 거부된다.** 예약은 어느 객실을 파는지가 반드시
    정해져야 하지만, iCal 피드는 숙소 단위로 하나만 걸 수도 있다.

    **남의 객실과 없는 객실을 구분하지 않는다** — 조회 한 번으로 존재와
    소속을 함께 보고, 둘 다 같은 404를 던진다.
    """
    if room_id is None:
        # 모든 판매단위에서 정상이다. 독채는 항상 이 경로이고,
        #   ROOM/BED 숙소도 '숙소 전체 피드'를 등록할 수 있다.
        return

    # ① 존재·소속을 **한 쿼리로** 본다. 소유(host_id)는 위
    #   get_owned_property가 이미 확인했으므로 여기서는 '그 객실이 이 숙소
    #   소속인가'만 보면 된다. DB의 복합 FK
    #   fk_channel_connections_room_property와 같은 조건이며, 그것은
    #   동시성 대비 마지막 방어선으로 남는다.
    #   **없으면 404다** — 부존재와 타인 숙소를 구분하지 않는다(위 도크스트링).
    room = await db.scalar(
        select(Room).where(
            Room.room_id == room_id,
            Room.property_id == prop.property_id,
        )
    )
    if room is None:
        raise ResourceNotFoundError("요청한 객실을 찾을 수 없습니다.")

    # ② 여기까지 왔으면 **내 숙소의 실재하는 객실**이다. 그런데 판매단위가
    #   PROPERTY면 그 숙소에는 객실 개념이 없어(GET .../rooms가 빈 배열인
    #   것이 정상 — 2.1절) 객실별 피드를 걸 수 없다. 이 400은 요청자가
    #   이미 아는 정보만으로 판정되므로 새어 나가는 것이 없다.
    if prop.bookable_unit_type is BookableUnitType.PROPERTY:
        raise InvalidUnitHierarchyError(
            "이 숙소는 전체(PROPERTY) 단위로 판매합니다. "
            "객실별 피드를 등록할 수 없습니다.",
            code="INVALID_UNIT_HIERARCHY",
        )


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

    **[v1.4] `room_id`를 받는다**(api_contract 3.2절). 선택 필드이며
    생략하면 숙소 전체 피드다. 검증은 `_validate_room_for_channel`이
    하며, **DB 오류 번역이 아니라 미리 막는다** — 아래 주석 참고.
    """
    prop = await get_owned_property(db, property_id, host_id)

    # [v1.4] room_id 검증을 **flush() 앞**에 둔다.
    #   DB 복합 FK(fk_channel_connections_room_property)에 맡기면
    #   IntegrityError가 아래 except로 흘러가는데, 그 분기는
    #   **rollback()으로 트랜잭션 전체를 되돌린다.** 게다가 제약 이름이
    #   uq_property_channel이 아니라 409로 번역되지도 않고,
    #   reservation_service._translate_integrity_error는
    #   'fk_reservations_' 접두사로만 판정해 이 제약을 404로 떨어뜨린다
    #   (api_contract 3.2절은 400을 요구한다).
    #   세 경우 중 '독채에 room_id 지정'은 DB가 아예 막지 못하므로
    #   (bookable_unit_type이 다른 테이블에 있다) 어차피 서비스 레이어가
    #   필요하다 — 셋을 한 곳에서 처리해 경로를 하나로 묶는다.
    await _validate_room_for_channel(db, prop, payload.room_id)

    conn = ChannelConnection(
        property_id=property_id,
        channel=payload.channel,
        room_id=payload.room_id,
        ical_url=payload.ical_url,
        external_property_id=payload.external_property_id,
    )
    db.add(conn)
    try:
        await db.flush()
    except IntegrityError as exc:
        await db.rollback()
        if violates_constraint(exc, "uq_property_channel"):
            # [v1.4] 제약이 3컬럼이 되면서 **객실별 중복도 여기로 온다.**
            #   메시지가 '숙소에 이미 연결된 채널'이면 호스텔 호스트는
            #   다른 객실 피드를 등록하려다 이 문구를 보고 원인을 오해한다.
            raise ChannelAlreadyConnectedError(
                "이미 연결된 채널입니다(같은 숙소·채널·객실 조합). "
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
