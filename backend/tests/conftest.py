"""테스트 공용 픽스처.

로컬 Docker Postgres(host_on_ai)를 그대로 사용한다. 각 테스트는 자기 호스트를
새로 만들고 끝날 때 삭제하며, HOSTS 삭제가 CASCADE로 하위 데이터를 전부
정리하므로 테스트끼리 서로 오염되지 않는다.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import settings
from app.models import Bed, ChannelConnection, Host, Property, Room
from app.models.enums import AccommodationType, BookableUnitType, Channel


@pytest_asyncio.fixture
async def db() -> AsyncGenerator[AsyncSession, None]:
    """테스트 전용 엔진(NullPool)으로 세션을 만든다.

    앱의 공용 엔진(app.core.database.engine)을 그대로 쓰면 안 된다 — 풀에
    남은 asyncpg 커넥션이 **처음 테스트의 이벤트 루프에 묶여 있어**, 다음
    테스트(새 루프)에서 그 커넥션을 재사용하는 순간 MissingGreenlet으로
    깨진다. NullPool은 커넥션을 재사용하지 않아 이 문제가 생기지 않는다.
    """
    engine = create_async_engine(settings.DATABASE_URL, poolclass=NullPool)
    maker = async_sessionmaker(bind=engine, expire_on_commit=False, autoflush=False)
    try:
        async with maker() as session:
            yield session
    finally:
        await engine.dispose()


@pytest_asyncio.fixture
async def host(db: AsyncSession) -> AsyncGenerator[Host, None]:
    obj = Host(
        email=f"test-{uuid.uuid4().hex[:12]}@test.local",
        password_hash="not-a-real-hash",
        name="테스트호스트",
    )
    db.add(obj)
    await db.commit()
    # rollback은 인스턴스 속성을 만료시켜 이후 obj.host_id 접근이 지연로딩(동기 IO)을
    #   유발한다 → async 컨텍스트에서 MissingGreenlet. 그래서 id를 미리 값으로 뽑아둔다.
    host_id = obj.host_id
    yield obj

    # 호스트 삭제 → properties/rooms/beds/reservations... 전부 CASCADE 정리
    await db.rollback()
    stored = await db.get(Host, host_id)
    if stored is not None:
        await db.delete(stored)
        await db.commit()


@pytest.fixture
def make_property(db: AsyncSession, host: Host):
    """지정한 판매단위의 숙소 + 채널연결(+ROOM/BED면 객실·침대)을 만들어 준다."""

    async def _make(unit_type: BookableUnitType) -> tuple[Property, ChannelConnection]:
        prop = Property(
            host_id=host.host_id,
            name=f"테스트숙소-{unit_type.value}",
            accommodation_type=(
                AccommodationType.HOSTEL
                if unit_type is BookableUnitType.BED
                else AccommodationType.URBAN_HOMESTAY
            ),
            bookable_unit_type=unit_type,
        )
        db.add(prop)
        await db.flush()

        conn = ChannelConnection(property_id=prop.property_id, channel=Channel.AIRBNB)
        db.add(conn)

        if unit_type in (BookableUnitType.ROOM, BookableUnitType.BED):
            room = Room(property_id=prop.property_id, room_name="101호")
            db.add(room)
            await db.flush()
            db.add(Bed(room_id=room.room_id, bed_label="A"))
            db.add(Bed(room_id=room.room_id, bed_label="B"))

        await db.commit()
        return prop, conn

    return _make
