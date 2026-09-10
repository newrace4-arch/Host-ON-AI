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
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ResourceNotFoundError
from app.models.enums import BookableUnitType, Channel, SyncStatus
from app.models.host import Host
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

    try:
        with pytest.raises(ResourceNotFoundError):
            await channel_service.get_owned_connection(
                db, conn.connection_id, stranger.host_id
            )

        # 목록 경로도 숙소 소유권에서 먼저 막힌다.
        with pytest.raises(ResourceNotFoundError):
            await channel_service.list_channels(
                db, property_id=prop.property_id, host_id=stranger.host_id
            )
    finally:
        await db.rollback()
        stored = await db.get(Host, stranger.host_id)
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
