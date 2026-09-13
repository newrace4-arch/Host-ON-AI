"""CLEANING_TASK_PHOTOS 회귀 테스트 (v1.4 revision ②).

### 왜 이 파일이 따로 필요한가

`test_response_sources.py`와 같은 이유다 — 기존 회귀에는 `photo_urls`·
`photo_url`·`sort_order`가 **하나도 나오지 않는다.** 회귀가 전부 녹색이면서
이번 교체가 틀려 있는 상태가 가능하므로, revision ②가 **DB에 실제로
걸렸는지**를 직접 확인한다.

### 픽스처를 왜 지역에 두는가

`conftest.py`의 `make_property`는 숙소·채널·객실·침대까지만 만든다.
`CleaningTask`를 만들려면 **예약이 먼저 있어야 한다** — `reservation_id`가
NOT NULL이고 `(reservation_id, property_id)` 복합 FK로 RESERVATIONS를
경유하기 때문이다(db_spec 2.9). 그렇다고 `conftest.py`를 고치지 않는다
(회귀 147건이 그 픽스처에 걸려 있다). `test_reservation_integrity.py:41`의
`_insert_raw_reservation` 전례대로 **이 파일 안에 지역 헬퍼**를 둔다.
"""

from __future__ import annotations

from datetime import date

import pytest
from sqlalchemy import delete, func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    ChannelConnection,
    CleaningTask,
    CleaningTaskPhoto,
    Property,
    Reservation,
)
from app.models.enums import BookableUnitType, ReservationStatus, TaskStatus

D10 = date(2026, 9, 10)
D12 = date(2026, 9, 12)

# ---------------------------------------------------------------------------
# 지역 헬퍼
# ---------------------------------------------------------------------------


async def _insert_raw_reservation(
    db: AsyncSession, *, prop: Property, conn: ChannelConnection
) -> Reservation:
    """서비스 검증을 우회해 예약을 직접 만든다.

    청소작업의 전제일 뿐이며 예약 자체를 검증하는 것이 아니므로, 서비스
    레이어를 태우지 않는다(`test_reservation_integrity.py`와 같은 판단).
    """
    r = Reservation(
        property_id=prop.property_id,
        channel_connection_id=conn.connection_id,
        check_in=D10,
        check_out=D12,
        reservation_status=ReservationStatus.CONFIRMED,
    )
    db.add(r)
    await db.flush()
    return r


async def _make_task(
    db: AsyncSession, prop: Property, conn: ChannelConnection
) -> CleaningTask:
    """예약 → 청소작업. 예약 CONFIRMED 즉시 PENDING으로 선제생성하는 경로다."""
    reservation = await _insert_raw_reservation(db, prop=prop, conn=conn)
    task = CleaningTask(
        reservation_id=reservation.reservation_id,
        property_id=prop.property_id,
        task_status=TaskStatus.PENDING,
    )
    db.add(task)
    await db.flush()
    return task


async def _add_photo(
    db: AsyncSession,
    task: CleaningTask,
    *,
    url: str = "https://example.test/clean-a.jpg",
    sort_order: int | None = None,
) -> CleaningTaskPhoto:
    """사진 1장 = 행 1개. `sort_order`를 생략하면 서버 기본값(0)에 맡긴다."""
    kwargs = {"task_id": task.task_id, "photo_url": url}
    if sort_order is not None:
        kwargs["sort_order"] = sort_order
    obj = CleaningTaskPhoto(**kwargs)
    db.add(obj)
    await db.flush()
    return obj


async def _expect_integrity_error(db: AsyncSession, obj) -> IntegrityError:
    db.add(obj)
    try:
        await db.flush()
    except IntegrityError as exc:
        await db.rollback()
        return exc

    await db.rollback()
    pytest.fail("DB 제약이 발동하지 않았다 — 테스트 전제가 깨졌다")


async def _count(db: AsyncSession, model, **filters) -> int:
    stmt = select(func.count()).select_from(model)
    for col, val in filters.items():
        stmt = stmt.where(getattr(model, col) == val)
    return await db.scalar(stmt)


# ---------------------------------------------------------------------------
# 1. 청소작업 삭제 → 사진 행 연쇄 삭제
#    (conftest teardown이 이 경로를 탄다. 끊기면 잔여 데이터가 다음 테스트를
#     오염시킨다 — 테스트와 개발이 같은 DB이기 때문이다)
# ---------------------------------------------------------------------------


async def test_task_delete_cascades_to_photos(db: AsyncSession, make_property):
    prop, conn = await make_property(BookableUnitType.PROPERTY)
    task = await _make_task(db, prop, conn)
    await _add_photo(db, task, url="https://example.test/a.jpg", sort_order=0)
    await _add_photo(db, task, url="https://example.test/b.jpg", sort_order=1)
    await db.commit()

    task_id = task.task_id
    assert await _count(db, CleaningTaskPhoto, task_id=task_id) == 2

    await db.execute(delete(CleaningTask).where(CleaningTask.task_id == task_id))
    await db.commit()

    assert await _count(db, CleaningTaskPhoto, task_id=task_id) == 0


# ---------------------------------------------------------------------------
# 2. sort_order 기본값 0 — 생략하고 INSERT
# ---------------------------------------------------------------------------


async def test_sort_order_defaults_to_zero(db: AsyncSession, make_property):
    """`server_default`라서 **ORM을 거치지 않는 raw SQL INSERT도** 통과한다.

    파이썬측 `default=`였다면 아래 raw INSERT가 NOT NULL 위반으로 실패한다.
    사진 업로드 경로가 앞으로 어떻게 구현되든 기본값이 서버에 있어야 한다.
    """
    prop, conn = await make_property(BookableUnitType.PROPERTY)
    task = await _make_task(db, prop, conn)
    await db.commit()
    task_id = task.task_id

    # (1) ORM 경로 — sort_order를 아예 넘기지 않는다
    photo = await _add_photo(db, task, url="https://example.test/orm.jpg")
    await db.commit()
    assert photo.sort_order == 0

    # (2) raw SQL 경로 — 컬럼 목록에서 sort_order를 빼고 INSERT
    await db.execute(
        text(
            "INSERT INTO cleaning_task_photos (task_id, photo_url) "
            "VALUES (:t, :u)"
        ).bindparams(t=task_id, u="https://example.test/raw.jpg")
    )
    await db.commit()

    raw = await db.scalar(
        select(CleaningTaskPhoto).where(
            CleaningTaskPhoto.photo_url == "https://example.test/raw.jpg"
        )
    )
    assert raw is not None
    assert raw.sort_order == 0


# ---------------------------------------------------------------------------
# 3. photo_url NOT NULL 거부
# ---------------------------------------------------------------------------


async def test_photo_url_cannot_be_null(db: AsyncSession, make_property):
    prop, conn = await make_property(BookableUnitType.PROPERTY)
    task = await _make_task(db, prop, conn)
    await db.commit()
    task_id = task.task_id

    exc = await _expect_integrity_error(
        db, CleaningTaskPhoto(task_id=task_id, photo_url=None, sort_order=0)
    )
    assert "photo_url" in str(exc.orig)


# ---------------------------------------------------------------------------
# 4. 같은 task에 여러 장 + sort_order 순 정렬
#    — append 운용 규칙이 "행 INSERT"로 성립하는가
# ---------------------------------------------------------------------------


async def test_multiple_photos_are_appended_and_ordered(
    db: AsyncSession, make_property
):
    """api_contract v1.6의 append 규칙이 v1.4에서도 결과가 같아야 한다.

    JSONB 시절 "배열 끝에 원소 추가"가 이제 "행 하나 INSERT"다. 기존 사진이
    **교체되지 않고 누적**되며, 목록은 `sort_order` 순으로 나온다.
    """
    prop, conn = await make_property(BookableUnitType.PROPERTY)
    task = await _make_task(db, prop, conn)
    await db.commit()
    task_id = task.task_id

    # 일부러 순서를 섞어 넣는다 — 정렬이 INSERT 순서가 아니라 sort_order를
    #   따르는지 보기 위해서다
    await _add_photo(db, task, url="https://example.test/c.jpg", sort_order=2)
    await db.commit()
    await _add_photo(db, task, url="https://example.test/a.jpg", sort_order=0)
    await db.commit()
    await _add_photo(db, task, url="https://example.test/b.jpg", sort_order=1)
    await db.commit()

    # 교체가 아니라 누적이다
    assert await _count(db, CleaningTaskPhoto, task_id=task_id) == 3

    rows = (
        await db.scalars(
            select(CleaningTaskPhoto)
            .where(CleaningTaskPhoto.task_id == task_id)
            .order_by(CleaningTaskPhoto.sort_order)
        )
    ).all()
    assert [r.photo_url for r in rows] == [
        "https://example.test/a.jpg",
        "https://example.test/b.jpg",
        "https://example.test/c.jpg",
    ]

    # 한 장만 지우는 것이 DELETE 한 줄이다(JSONB 시절에는 배열 전체 덮어쓰기)
    await db.execute(
        delete(CleaningTaskPhoto).where(CleaningTaskPhoto.photo_id == rows[1].photo_id)
    )
    await db.commit()
    assert await _count(db, CleaningTaskPhoto, task_id=task_id) == 2


# ---------------------------------------------------------------------------
# 5. cleaning_tasks.photo_urls 컬럼이 사라졌는가 — 모델과 DB 양쪽
# ---------------------------------------------------------------------------


async def test_photo_urls_column_is_gone(db: AsyncSession):
    """v1.4 ②: `CLEANING_TASKS.photo_urls`(JSONB)가 **양쪽에서** 사라졌다.

    모델만 보면 "코드가 고쳐졌다"까지만 알 수 있고, DB만 보면 "모델이 아직
    옛 컬럼을 들고 있다"를 놓친다. 둘을 함께 본다.
    """
    # (1) 모델 속성
    assert not hasattr(CleaningTask, "photo_urls")
    assert "photo_urls" not in CleaningTask.__table__.columns

    # (2) 실제 DB 컬럼
    names = {
        r[0]
        for r in (
            await db.execute(
                text(
                    "SELECT column_name FROM information_schema.columns "
                    "WHERE table_name = 'cleaning_tasks'"
                )
            )
        ).all()
    }
    assert "photo_urls" not in names
    # 같은 조회로 나머지 컬럼이 멀쩡한지도 확인한다(② 밖 연산이 없었다는 증거)
    assert {"task_id", "reservation_id", "property_id", "scheduled_at"} <= names
