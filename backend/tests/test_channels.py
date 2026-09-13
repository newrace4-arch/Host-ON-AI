"""채널 연동 CRUD 회귀 테스트 (api_contract.md 3절).

특히 두 가지를 고정한다.

1. **IDOR 방어** — 타인 소유 리소스는 403이 아니라 404여야 한다. 403을 쓰면
   id를 1씩 올려가며 어떤 id가 실재하는지 외부에서 추론할 수 있다(0절).
2. **`ical_url` 원문 비노출** — URL 자체가 자격증명이라, 응답 어디에도
   원문이 섞이면 안 된다.
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import InvalidUnitHierarchyError, ResourceNotFoundError
from app.models.channel import ChannelConnection
from app.models.enums import BookableUnitType, Channel, SyncStatus
from app.models.host import Host
from app.models.property import Room
from app.schemas.channel import (
    ChannelConnectionCreateRequest,
    ChannelConnectionResponse,
    mask_ical_url,
)
from app.services import channel_service
from app.services.channel_service import ChannelAlreadyConnectedError

REAL_URL = "https://www.airbnb.com/calendar/ical/12345678.ics?s=abc1234567890"


# ---------------------------------------------------------------- 마스킹


def test_mask_hides_the_secret_part():
    masked = mask_ical_url(REAL_URL)

    # 호스트가 "어느 URL인지" 알아볼 앞부분은 남되, 비밀 토큰은 사라져야 한다.
    assert "abc1234567890" not in masked
    assert "12345678.ics" not in masked
    assert masked.startswith("https://")
    assert "****" in masked


def test_mask_handles_short_and_empty():
    assert mask_ical_url(None) is None
    assert mask_ical_url("short") == "****"


# ---------------------------------------------------------------- CRUD


@pytest.mark.asyncio
async def test_create_and_list_channel(db: AsyncSession, host: Host, make_property):
    prop, existing = await make_property(BookableUnitType.PROPERTY)

    conn = await channel_service.create_channel(
        db,
        property_id=prop.property_id,
        host_id=host.host_id,
        payload=ChannelConnectionCreateRequest(
            channel=Channel.BOOKING_COM, ical_url=REAL_URL
        ),
    )
    await db.commit()

    assert conn.sync_status is SyncStatus.SYNCING  # 등록 직후엔 아직 동기화 전
    assert conn.last_synced_at is None
    assert conn.last_error_message is None

    conns = await channel_service.list_channels(
        db, property_id=prop.property_id, host_id=host.host_id
    )
    # 픽스처가 만든 AIRBNB 연결 + 방금 만든 BOOKING_COM
    assert {c.channel for c in conns} == {Channel.AIRBNB, Channel.BOOKING_COM}


@pytest.mark.asyncio
async def test_response_never_leaks_raw_url(db: AsyncSession, host: Host, make_property):
    """응답 DTO 전체를 문자열로 펼쳐도 원문이 나오면 안 된다."""
    prop, _ = await make_property(BookableUnitType.PROPERTY)
    conn = await channel_service.create_channel(
        db,
        property_id=prop.property_id,
        host_id=host.host_id,
        payload=ChannelConnectionCreateRequest(
            channel=Channel.NAVER, ical_url=REAL_URL
        ),
    )
    await db.commit()

    body = ChannelConnectionResponse.from_model(conn).model_dump()

    assert REAL_URL not in str(body)
    assert "ical_url" not in body  # 필드명 자체가 ical_url_masked여야 한다
    assert body["ical_url_masked"].startswith("https://")


@pytest.mark.asyncio
async def test_duplicate_channel_is_409(db: AsyncSession, host: Host, make_property):
    """UNIQUE(property_id, channel)과 짝을 이루는 도메인 예외."""
    prop, _ = await make_property(BookableUnitType.PROPERTY)  # AIRBNB 연결이 이미 있다

    with pytest.raises(ChannelAlreadyConnectedError) as exc:
        await channel_service.create_channel(
            db,
            property_id=prop.property_id,
            host_id=host.host_id,
            payload=ChannelConnectionCreateRequest(
                channel=Channel.AIRBNB, ical_url=REAL_URL
            ),
        )

    assert exc.value.status_code == 409
    assert exc.value.code == "CHANNEL_ALREADY_CONNECTED"


@pytest.mark.asyncio
async def test_blank_ical_url_rejected():
    """`ical_url`은 DB에서 nullable이지만 API에서는 필수다(3.2절)."""
    with pytest.raises(ValueError):
        ChannelConnectionCreateRequest(channel=Channel.AIRBNB, ical_url="   ")


# ---------------------------------------------------------------- IDOR


@pytest.mark.asyncio
async def test_other_hosts_connection_is_404(
    db: AsyncSession, host: Host, make_property
):
    """타인 소유 연결은 **403이 아니라 404**다(정보노출 방지)."""
    prop, conn = await make_property(BookableUnitType.PROPERTY)

    stranger = Host(
        email=f"stranger-{uuid.uuid4().hex[:12]}@test.local",
        password_hash="not-a-real-hash",
        name="남의호스트",
    )
    db.add(stranger)
    await db.commit()

    # rollback은 인스턴스 속성을 만료시켜 이후 stranger.host_id 접근이 지연로딩
    #   (동기 IO)을 유발한다 → async 컨텍스트에서 MissingGreenlet.
    #   conftest의 host 픽스처와 같은 이유로 id를 미리 값으로 뽑아둔다.
    stranger_id = stranger.host_id
    connection_id = conn.connection_id
    property_id = prop.property_id

    try:
        with pytest.raises(ResourceNotFoundError):
            await channel_service.get_owned_connection(db, connection_id, stranger_id)

        # 목록 경로도 숙소 소유권에서 먼저 막힌다.
        with pytest.raises(ResourceNotFoundError):
            await channel_service.list_channels(
                db, property_id=property_id, host_id=stranger_id
            )
    finally:
        await db.rollback()
        stored = await db.get(Host, stranger_id)
        if stored is not None:
            await db.delete(stored)
            await db.commit()


@pytest.mark.asyncio
async def test_missing_connection_is_404(db: AsyncSession, host: Host):
    with pytest.raises(ResourceNotFoundError):
        await channel_service.get_owned_connection(db, 9_999_999, host.host_id)


@pytest.mark.asyncio
async def test_delete_channel(db: AsyncSession, host: Host, make_property):
    prop, conn = await make_property(BookableUnitType.PROPERTY)

    await channel_service.delete_channel(
        db, connection_id=conn.connection_id, host_id=host.host_id
    )
    await db.commit()

    with pytest.raises(ResourceNotFoundError):
        await channel_service.get_owned_connection(
            db, conn.connection_id, host.host_id
        )


# ------------------------------------------------- [v1.4 ③] room_id / NULLS NOT DISTINCT
#
# 아래 4건은 revision ③(channel_connections.room_id)이 DB에 실제로 걸렸는지 본다.
#
# **위 `test_duplicate_channel_is_409`를 고치지 않는다.** UNIQUE의 컬럼이 2개에서
# 3개로 늘었지만 제약 **이름**(`uq_property_channel`)을 유지했으므로,
# `channel_service`의 409 번역이 그대로 동작해야 한다. 그 테스트가 **수정 없이**
# 통과하는 것이 이름 유지의 증거다 — 고쳐야 한다면 이름 유지에 실패한 것이다.
#
# `channel_service.create_channel`은 `room_id`를 받지 않는다(api_contract 3.2절에
# 요청 필드가 없어 문서가 선행이다). 그래서 아래 테스트는 모델을 직접 INSERT해
# DB 제약까지 도달시킨다.


async def _insert_raw_connection(
    db: AsyncSession,
    *,
    property_id: int,
    channel: Channel = Channel.AIRBNB,
    room_id: int | None = None,
) -> ChannelConnection:
    """서비스를 우회해 연결을 직접 만든다(서비스가 room_id를 받지 않는다)."""
    conn = ChannelConnection(
        property_id=property_id, channel=channel, room_id=room_id, ical_url=REAL_URL
    )
    db.add(conn)
    await db.flush()
    return conn


async def _expect_integrity_error(db: AsyncSession, obj) -> IntegrityError:
    db.add(obj)
    try:
        await db.flush()
    except IntegrityError as exc:
        await db.rollback()
        return exc

    await db.rollback()
    pytest.fail("DB 제약이 발동하지 않았다 — 테스트 전제가 깨졌다")


@pytest.mark.asyncio
async def test_null_room_id_duplicate_is_rejected(db: AsyncSession, make_property):
    """같은 (숙소, 채널)에 room_id=NULL 연결이 **두 개 생기면 안 된다.**

    기본 UNIQUE는 NULL을 서로 다른 값으로 취급하므로, `NULLS NOT DISTINCT`가
    없으면 이 INSERT가 **통과해버린다.** 독채 숙소에 에어비앤비 연결이 2개·3개
    생겨 "채널당 연결 1개" 보장이 조용히 깨지는 자리다(db_spec 2.5절).

    아래 test_same_channel_different_room_is_allowed와 **한 쌍**이다. 이 테스트만
    있으면 room_id를 아예 넣지 않아도 통과해버린다.
    """
    prop, _ = await make_property(BookableUnitType.PROPERTY)  # AIRBNB(room_id=NULL) 존재
    await db.commit()

    exc = await _expect_integrity_error(
        db,
        ChannelConnection(
            property_id=prop.property_id,
            channel=Channel.AIRBNB,
            room_id=None,
            ical_url=REAL_URL,
        ),
    )
    assert "uq_property_channel" in str(exc.orig)


@pytest.mark.asyncio
async def test_same_channel_different_room_is_allowed(db: AsyncSession, make_property):
    """호스텔 객실별 피드 — 같은 (숙소, 채널)이라도 room_id가 다르면 허용된다.

    이것이 ③의 존재 이유다. iCal 피드는 객실을 알려주지 않아 객실마다 별도
    리스팅·별도 URL이 나오는데, v1.3의 2컬럼 UNIQUE는 그걸 등록할 방법이
    없었다(db_spec 2.5절).

    위 test_null_room_id_duplicate_is_rejected와 **한 쌍**이다. 이 테스트만
    있으면 NULLS NOT DISTINCT를 빠뜨려도 통과해버린다.
    """
    prop, _ = await make_property(BookableUnitType.ROOM)  # 101호 + AIRBNB(NULL) 존재
    room_101 = await db.scalar(
        select(Room).where(Room.property_id == prop.property_id)
    )
    room_102 = Room(property_id=prop.property_id, room_name="102호")
    db.add(room_102)
    await db.flush()

    # 같은 숙소 · 같은 채널 · 다른 객실 → 둘 다 들어간다
    await _insert_raw_connection(
        db, property_id=prop.property_id, channel=Channel.AIRBNB, room_id=room_101.room_id
    )
    await _insert_raw_connection(
        db, property_id=prop.property_id, channel=Channel.AIRBNB, room_id=room_102.room_id
    )
    await db.commit()

    conns = (
        await db.scalars(
            select(ChannelConnection).where(
                ChannelConnection.property_id == prop.property_id,
                ChannelConnection.channel == Channel.AIRBNB,
            )
        )
    ).all()
    # 픽스처의 room_id=NULL 연결 + 객실별 2개 = 3개
    assert len(conns) == 3
    assert {c.room_id for c in conns} == {None, room_101.room_id, room_102.room_id}


@pytest.mark.asyncio
async def test_room_of_other_property_is_rejected(db: AsyncSession, make_property):
    """다른 숙소의 객실을 가리키는 연결은 복합 FK가 거부한다(4절 -1번).

    room_id 단독 FK였다면 "강남 독채의 에어비앤비 연결이 홍대 호스텔 101호를
    가리키는" 행이 통과한다. 동기화된 예약이 엉뚱한 객실로 들어간다.
    """
    prop_a, _ = await make_property(BookableUnitType.PROPERTY)
    prop_b, _ = await make_property(BookableUnitType.ROOM)
    room_of_b = await db.scalar(
        select(Room).where(Room.property_id == prop_b.property_id)
    )
    await db.commit()

    exc = await _expect_integrity_error(
        db,
        ChannelConnection(
            property_id=prop_a.property_id,
            channel=Channel.BOOKING_COM,  # UNIQUE가 아니라 FK가 걸리도록 다른 채널
            room_id=room_of_b.room_id,  # ← 남의 숙소 객실
            ical_url=REAL_URL,
        ),
    )
    assert "fk_channel_connections_room_property" in str(exc.orig)


@pytest.mark.asyncio
async def test_existing_null_room_id_rows_survived_migration(
    db: AsyncSession, make_property
):
    """기존 연결은 room_id=NULL로 그대로 살아 있다.

    ③은 nullable 컬럼 추가라 백필이 없다. 독채(PROPERTY 판매단위)는 객실 개념이
    없으므로 앞으로도 NULL이 정상값이며, 서비스가 room_id를 받지 않는 동안에는
    모든 신규 연결도 NULL로 만들어진다.
    """
    prop, conn = await make_property(BookableUnitType.PROPERTY)
    await db.commit()

    assert conn.room_id is None

    stored = await db.scalar(
        select(ChannelConnection).where(
            ChannelConnection.connection_id == conn.connection_id
        )
    )
    assert stored is not None
    assert stored.room_id is None
    assert stored.channel is Channel.AIRBNB


# ------------------------------------------------- [v1.4] POST 요청의 room_id
#
# ③에서 컬럼을 만들고 API는 미뤘다. api_contract 3.2절이 9/13에 요청 필드를
# 확정하면서 선행 조건이 풀렸다(CLAUDE.md 9/10 규칙 — 엔드포인트를 구현하기
# 전에 응답 스펙이 있는지 확인한다).
#
# **세 가지를 전부 400 INVALID_UNIT_HIERARCHY로 거부한다** — 다른 숙소의 객실 /
# 없는 객실 / 독채에 room_id 지정. DB 복합 FK에 맡기지 않고 서비스 레이어가
# 미리 막는 이유는 `_validate_room_for_channel` 도크스트링과
# `create_channel`의 주석 참고.


async def test_room_id_is_optional(db: AsyncSession, host: Host, make_property):
    """생략하면 `null` — 숙소 전체 피드다.

    기존 테스트가 전부 이 경로를 쓰므로, 선택 필드로 두지 않으면 회귀가
    통째로 깨진다.
    """
    prop, _ = await make_property(BookableUnitType.PROPERTY)
    await db.commit()

    conn = await channel_service.create_channel(
        db,
        property_id=prop.property_id,
        host_id=host.host_id,
        payload=ChannelConnectionCreateRequest(
            channel=Channel.BOOKING_COM, ical_url=REAL_URL
        ),
    )
    await db.commit()

    assert conn.room_id is None
    assert ChannelConnectionResponse.from_model(conn).room_id is None


async def test_room_id_accepted_for_room_unit_property(
    db: AsyncSession, host: Host, make_property
):
    """호스텔의 객실별 피드 — 유효한 `room_id`는 저장되고 응답에도 실린다."""
    prop, _ = await make_property(BookableUnitType.ROOM)
    room = await db.scalar(select(Room).where(Room.property_id == prop.property_id))
    await db.commit()

    conn = await channel_service.create_channel(
        db,
        property_id=prop.property_id,
        host_id=host.host_id,
        payload=ChannelConnectionCreateRequest(
            channel=Channel.BOOKING_COM, ical_url=REAL_URL, room_id=room.room_id
        ),
    )
    await db.commit()

    assert conn.room_id == room.room_id
    assert ChannelConnectionResponse.from_model(conn).room_id == room.room_id


async def test_room_id_of_other_property_is_400(
    db: AsyncSession, host: Host, make_property
):
    """다른 숙소의 객실 → 400. **404가 아니다.**

    `property_id`는 경로에 있고 이미 소유권이 검증된 상태라, 문제는
    "남의 리소스"가 아니라 **요청 본문이 그 숙소의 계층과 맞지 않는 것**이다
    (api_contract 3.2절). 0절의 404 통일 규칙은 경로의 리소스에 적용된다.
    """
    prop_a, _ = await make_property(BookableUnitType.ROOM)
    prop_b, _ = await make_property(BookableUnitType.ROOM)
    room_of_b = await db.scalar(
        select(Room).where(Room.property_id == prop_b.property_id)
    )
    await db.commit()

    with pytest.raises(InvalidUnitHierarchyError) as exc:
        await channel_service.create_channel(
            db,
            property_id=prop_a.property_id,
            host_id=host.host_id,
            payload=ChannelConnectionCreateRequest(
                channel=Channel.BOOKING_COM,
                ical_url=REAL_URL,
                room_id=room_of_b.room_id,
            ),
        )

    assert exc.value.status_code == 400
    assert exc.value.code == "INVALID_UNIT_HIERARCHY"


async def test_nonexistent_room_id_is_400(
    db: AsyncSession, host: Host, make_property
):
    """없는 객실 → 같은 400이다. **남의 객실과 구분하지 않는다.**"""
    prop, _ = await make_property(BookableUnitType.ROOM)
    await db.commit()

    with pytest.raises(InvalidUnitHierarchyError) as exc:
        await channel_service.create_channel(
            db,
            property_id=prop.property_id,
            host_id=host.host_id,
            payload=ChannelConnectionCreateRequest(
                channel=Channel.BOOKING_COM, ical_url=REAL_URL, room_id=9_999_999
            ),
        )

    assert exc.value.code == "INVALID_UNIT_HIERARCHY"


async def test_room_id_on_property_unit_is_400(
    db: AsyncSession, host: Host, make_property
):
    """독채에 `room_id` 지정 → 400. **DB는 이것을 막지 못한다.**

    `bookable_unit_type`은 `PROPERTIES`에 있어 `channel_connections`의 제약으로
    볼 수 없다. 서비스 레이어가 없으면 그대로 저장되고, 화면이 그 `room_id`로
    객실명을 찾다가 실패한다(그 숙소의 `GET .../rooms`는 빈 배열이 정상이다).
    """
    prop, _ = await make_property(BookableUnitType.PROPERTY)
    await db.commit()

    with pytest.raises(InvalidUnitHierarchyError) as exc:
        await channel_service.create_channel(
            db,
            property_id=prop.property_id,
            host_id=host.host_id,
            payload=ChannelConnectionCreateRequest(
                channel=Channel.BOOKING_COM, ical_url=REAL_URL, room_id=1
            ),
        )

    assert exc.value.code == "INVALID_UNIT_HIERARCHY"


async def test_room_unit_property_may_omit_room_id(
    db: AsyncSession, host: Host, make_property
):
    """🔴 `ROOM` 숙소에서 `room_id` 생략이 **거부되지 않는다.**

    이것이 `reservation_service.validate_unit_hierarchy` 오용을 막는 유일한
    장치다. 그 함수를 재사용하면 `ROOM` 숙소에 `room_id`가 없을 때
    `ROOM_ID_REQUIRED`를 던지므로, **호스텔이 숙소 전체 피드 하나만 등록하려는
    정상 요청이 거부된다.** 예약은 어느 객실을 파는지가 반드시 정해져야 하지만
    iCal 피드는 숙소 단위로 하나만 걸 수도 있다.
    """
    prop, _ = await make_property(BookableUnitType.ROOM)
    await db.commit()

    conn = await channel_service.create_channel(
        db,
        property_id=prop.property_id,
        host_id=host.host_id,
        payload=ChannelConnectionCreateRequest(
            channel=Channel.NAVER, ical_url=REAL_URL
        ),
    )
    await db.commit()

    assert conn.room_id is None
