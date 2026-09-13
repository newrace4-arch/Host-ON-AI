"""RESPONSE_SOURCES + 문의 계열 복합FK 회귀 테스트 (v1.4 revision ①).

### 왜 이 파일이 따로 필요한가

9/12까지의 회귀 137건은 **`sources`·`response_sources`·`property_id` 교체를
한 번도 실행하지 않는다**(테스트 전수 검색에서 이 식별자들이 0건이었다).
즉 137건이 전부 녹색이면서 이번 교체가 틀려 있는 상태가 가능하다. 이 파일은
revision ①이 **DB에 실제로 걸렸는지**를 직접 확인한다.

### 픽스처를 왜 지역에 두는가

`conftest.py`의 `make_property`는 숙소·채널·객실·침대까지만 만들고 **문의·
응답·청크를 만들지 않는다.** 그렇다고 `conftest.py`를 고치지 않는다 —
회귀 137건이 그 픽스처에 걸려 있어 영향 범위가 파일 하나를 넘는다.
`test_reservation_integrity.py`의 `_insert_raw_reservation` 전례대로
**이 파일 안에 지역 헬퍼**를 둔다.

### 애플리케이션 레이어를 거치지 않는 이유

`test_integrity_error_translation.py`와 같다 — 검증하려는 것이 **DB 제약
자체**이므로, 서비스 레이어를 거치면 그 앞에서 막혀 제약이 발동하지 않는다.
"""

from __future__ import annotations

import pytest
from sqlalchemy import delete, func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    Inquiry,
    InquiryResponse,
    KnowledgeChunk,
    Property,
    ResponseSource,
)
from app.models.enums import BookableUnitType, DocumentType

# ---------------------------------------------------------------------------
# 지역 헬퍼 — conftest.make_property가 만들어 주지 않는 4종을 여기서 만든다
# ---------------------------------------------------------------------------


async def _make_inquiry(db: AsyncSession, prop: Property) -> Inquiry:
    """게스트 문의. `reservation_id=None`(v1.3 사전문의 경로)로 만든다."""
    obj = Inquiry(
        reservation_id=None,
        property_id=prop.property_id,
        channel="AIRBNB",
        message="체크인 몇 시부터 가능한가요?",
        language="ko",
    )
    db.add(obj)
    await db.flush()
    return obj


async def _make_response(
    db: AsyncSession,
    inquiry: Inquiry,
    *,
    property_id: int | None = None,
    is_latest: bool = True,
    text_: str = "체크인은 15시부터입니다.",
) -> InquiryResponse:
    """AI 응답. `property_id`는 **문의에서 복사한다**(db_spec 2.12절).

    `property_id`를 명시로 넘기는 것은 4번 테스트(복합 FK가 실제로 거르는지)
    전용이다. 정상 경로에서는 절대 다른 값을 넣지 않는다.
    """
    obj = InquiryResponse(
        inquiry_id=inquiry.inquiry_id,
        property_id=inquiry.property_id if property_id is None else property_id,
        response_text=text_,
        language="ko",
        is_latest=is_latest,
    )
    db.add(obj)
    await db.flush()
    return obj


async def _make_chunk(db: AsyncSession, prop: Property) -> KnowledgeChunk:
    """지식 청크. `embedding`은 nullable이라 비워 둔다(임베딩 모델 불필요)."""
    obj = KnowledgeChunk(
        property_id=prop.property_id,
        document_type=DocumentType.HOUSE_RULE,
        category="체크인",
        content="체크인은 15시, 체크아웃은 11시입니다.",
        embedding=None,
    )
    db.add(obj)
    await db.flush()
    return obj


async def _link(
    db: AsyncSession,
    response: InquiryResponse,
    chunk: KnowledgeChunk,
    *,
    rank: int = 1,
    property_id: int | None = None,
) -> ResponseSource:
    """응답 ↔ 청크 인용 1건."""
    obj = ResponseSource(
        response_id=response.response_id,
        chunk_id=chunk.chunk_id,
        property_id=response.property_id if property_id is None else property_id,
        rank=rank,
    )
    db.add(obj)
    await db.flush()
    return obj


async def _expect_integrity_error(db: AsyncSession, obj) -> IntegrityError:
    """DB 제약까지 도달시키고 올라온 IntegrityError를 돌려준다."""
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
# 10. sources 컬럼이 사라졌는가 — 모델 속성과 information_schema 양쪽
#     (가장 먼저 둔다. 이 단언이 깨지면 아래 전부가 의미를 잃는다)
# ---------------------------------------------------------------------------


async def test_sources_column_is_gone(db: AsyncSession):
    """v1.4 ① 5): `INQUIRY_RESPONSES.sources`(JSONB)가 **양쪽에서** 사라졌다.

    모델만 보면 "코드가 고쳐졌다"까지만 알 수 있고, DB만 보면 "모델이 아직
    옛 컬럼을 들고 있다"를 놓친다. 둘을 함께 본다.
    """
    # (1) 모델 속성
    assert not hasattr(InquiryResponse, "sources")
    assert "sources" not in InquiryResponse.__table__.columns

    # (2) 실제 DB 컬럼
    rows = (
        await db.execute(
            text(
                "SELECT column_name, is_nullable FROM information_schema.columns "
                "WHERE table_name = 'inquiry_responses'"
            )
        )
    ).all()
    names = {r[0] for r in rows}
    assert "sources" not in names
    # 같은 조회로 v1.4 ① 3)의 신규 컬럼이 NOT NULL로 들어갔는지도 확인한다
    assert "property_id" in names
    assert dict(rows)["property_id"] == "NO"


# ---------------------------------------------------------------------------
# 1. 숙소 삭제 연쇄 — properties → inquiries → inquiry_responses →
#    response_sources 까지 전부 정리된다
#    (conftest teardown이 이 경로를 탄다. 끊기면 잔여 데이터가 다음 테스트를
#     오염시킨다 — 테스트와 개발이 같은 DB이기 때문이다)
# ---------------------------------------------------------------------------


async def test_property_delete_cascades_to_response_sources(
    db: AsyncSession, make_property
):
    prop, _ = await make_property(BookableUnitType.PROPERTY)
    inquiry = await _make_inquiry(db, prop)
    response = await _make_response(db, inquiry)
    chunk = await _make_chunk(db, prop)
    await _link(db, response, chunk)
    await db.commit()

    assert await _count(db, ResponseSource, property_id=prop.property_id) == 1

    await db.execute(delete(Property).where(Property.property_id == prop.property_id))
    await db.commit()

    assert await _count(db, Inquiry, property_id=prop.property_id) == 0
    assert await _count(db, InquiryResponse, property_id=prop.property_id) == 0
    assert await _count(db, KnowledgeChunk, property_id=prop.property_id) == 0
    assert await _count(db, ResponseSource, property_id=prop.property_id) == 0


# ---------------------------------------------------------------------------
# 2. 중복 행 거부 — 같은 (response_id, chunk_id)를 두 번
# ---------------------------------------------------------------------------


async def test_duplicate_pair_is_rejected(db: AsyncSession, make_property):
    """복합 PK가 "같은 응답이 같은 청크를 두 번 인용"을 막는다(db_spec 2.17)."""
    prop, _ = await make_property(BookableUnitType.PROPERTY)
    inquiry = await _make_inquiry(db, prop)
    response = await _make_response(db, inquiry)
    chunk = await _make_chunk(db, prop)
    await _link(db, response, chunk, rank=1)
    await db.commit()

    exc = await _expect_integrity_error(
        db,
        ResponseSource(
            response_id=response.response_id,
            chunk_id=chunk.chunk_id,
            property_id=prop.property_id,
            rank=1,
        ),
    )
    assert "response_sources_pkey" in str(exc.orig)


# ---------------------------------------------------------------------------
# 3. 다른 숙소 청크 인용 거부 — 숙소 A 응답 + 숙소 B 청크
# ---------------------------------------------------------------------------


async def test_cross_property_citation_is_rejected(db: AsyncSession, make_property):
    """`property_id`가 **어느 쪽 값이든** 두 복합 FK를 동시에 만족할 수 없다.

    이것이 JSONB `sources`가 못 하던 일이다 — "강남 숙소 문의에 홍대 호스텔
    하우스룰을 인용"하는 행을 DB가 거부한다(db_spec 2.17, 4절 -1번).
    """
    prop_a, _ = await make_property(BookableUnitType.PROPERTY)
    prop_b, _ = await make_property(BookableUnitType.PROPERTY)

    inquiry_a = await _make_inquiry(db, prop_a)
    response_a = await _make_response(db, inquiry_a)
    chunk_b = await _make_chunk(db, prop_b)
    await db.commit()

    # ⚠️ _expect_integrity_error가 rollback하면 인스턴스 속성이 만료돼 이후
    #   접근이 지연로딩(동기 IO) → MissingGreenlet이 된다(conftest 27~33행과
    #   같은 계열). 두 번 시도하는 테스트이므로 id를 **값으로** 먼저 뽑는다.
    response_id = response_a.response_id
    chunk_id = chunk_b.chunk_id
    pid_a, pid_b = prop_a.property_id, prop_b.property_id

    # (1) property_id = A → 응답 쪽 FK는 만족하지만 청크 쪽 FK가 거부
    exc_a = await _expect_integrity_error(
        db,
        ResponseSource(
            response_id=response_id, chunk_id=chunk_id, property_id=pid_a, rank=1
        ),
    )
    assert "fk_response_sources_chunk_property" in str(exc_a.orig)

    # (2) property_id = B → 이번엔 응답 쪽 FK가 거부
    exc_b = await _expect_integrity_error(
        db,
        ResponseSource(
            response_id=response_id, chunk_id=chunk_id, property_id=pid_b, rank=1
        ),
    )
    assert "fk_response_sources_response_property" in str(exc_b.orig)


# ---------------------------------------------------------------------------
# 4. 응답의 property_id가 문의와 다르면 거부
#    — v1.4 ① 3)의 복합 FK가 실제로 동작하는지 보는 유일한 테스트
# ---------------------------------------------------------------------------


async def test_response_property_must_match_inquiry(db: AsyncSession, make_property):
    """`fk_inquiry_responses_inquiry_property`가 없으면 이 INSERT가 통과한다.

    교체 전(단독 FK)에는 `inquiry_id`만 맞으면 `property_id`가 남의 숙소여도
    들어갔다. 그 행이 있으면 RESPONSE_SOURCES의 격리가 통째로 뚫린다.
    """
    prop_a, _ = await make_property(BookableUnitType.PROPERTY)
    prop_b, _ = await make_property(BookableUnitType.PROPERTY)
    inquiry_a = await _make_inquiry(db, prop_a)
    await db.commit()

    exc = await _expect_integrity_error(
        db,
        InquiryResponse(
            inquiry_id=inquiry_a.inquiry_id,
            property_id=prop_b.property_id,  # ← 문의는 A 숙소 것이다
            response_text="남의 숙소 id로 만든 응답",
            is_latest=True,
        ),
    )
    assert "fk_inquiry_responses_inquiry_property" in str(exc.orig)


# ---------------------------------------------------------------------------
# 5. 청크 삭제 → 인용 연쇄 삭제, 그러나 response_text는 남는다
# ---------------------------------------------------------------------------


async def test_chunk_delete_cascades_but_response_text_survives(
    db: AsyncSession, make_property
):
    """CASCADE의 대가를 고정한다 — 이 단언이 없으면 누가 RESTRICT로 되돌린다.

    `RESTRICT`를 쓸 수 없는 이유(db_spec 2.17): api_contract 8절에 청크 수정
    API가 없어 하우스룰을 고치는 유일한 방법이 "지우고 다시 등록"이다.
    RESTRICT면 인용된 청크를 **영원히 고칠 수 없게 된다.**

    대가는 "무엇을 근거로 답했는지"가 사라지는 것뿐이며, **게스트에게 실제로
    나간 답변 원문은 그대로 남는다.**
    """
    prop, _ = await make_property(BookableUnitType.PROPERTY)
    inquiry = await _make_inquiry(db, prop)
    response = await _make_response(db, inquiry, text_="체크인은 15시부터 가능합니다.")
    chunk = await _make_chunk(db, prop)
    await _link(db, response, chunk)
    await db.commit()

    await db.execute(
        delete(KnowledgeChunk).where(KnowledgeChunk.chunk_id == chunk.chunk_id)
    )
    await db.commit()

    # 인용 기록은 사라진다
    assert await _count(db, ResponseSource, response_id=response.response_id) == 0

    # 응답 본문은 남는다 — 화면에서는 "근거 0건"으로 보일 뿐이다
    survived = await db.get(InquiryResponse, response.response_id)
    assert survived is not None
    assert survived.response_text == "체크인은 15시부터 가능합니다."


# ---------------------------------------------------------------------------
# 6. 응답 삭제 → 인용 연쇄 삭제
# ---------------------------------------------------------------------------


async def test_response_delete_cascades_to_sources(db: AsyncSession, make_property):
    prop, _ = await make_property(BookableUnitType.PROPERTY)
    inquiry = await _make_inquiry(db, prop)
    response = await _make_response(db, inquiry)
    chunk = await _make_chunk(db, prop)
    await _link(db, response, chunk)
    await db.commit()

    await db.execute(
        delete(InquiryResponse).where(
            InquiryResponse.response_id == response.response_id
        )
    )
    await db.commit()

    assert await _count(db, ResponseSource, chunk_id=chunk.chunk_id) == 0
    # 청크 자체는 남는다 — 삭제 방향이 반대다
    assert await db.get(KnowledgeChunk, chunk.chunk_id) is not None


# ---------------------------------------------------------------------------
# 7. 같은 쌍을 rank만 다르게 두 번 → 거부
# ---------------------------------------------------------------------------


async def test_same_pair_with_different_rank_is_rejected(
    db: AsyncSession, make_property
):
    """`rank`는 PK에 들어가지 않는다 — 순위는 속성이지 식별자가 아니다.

    2번과 다른 시나리오다. 2번은 "완전히 같은 행", 이쪽은 "rank만 다른 행"이며,
    `rank`를 PK에 넣는 설계였다면 **이쪽만 통과해버린다.**
    """
    prop, _ = await make_property(BookableUnitType.PROPERTY)
    inquiry = await _make_inquiry(db, prop)
    response = await _make_response(db, inquiry)
    chunk = await _make_chunk(db, prop)
    await _link(db, response, chunk, rank=1)
    await db.commit()

    exc = await _expect_integrity_error(
        db,
        ResponseSource(
            response_id=response.response_id,
            chunk_id=chunk.chunk_id,
            property_id=prop.property_id,
            rank=2,  # ← 순위만 다르다
        ),
    )
    assert "response_sources_pkey" in str(exc.orig)


# ---------------------------------------------------------------------------
# 8. NOT NULL — rank / property_id
# ---------------------------------------------------------------------------


async def test_rank_and_property_id_cannot_be_null(db: AsyncSession, make_property):
    """둘 다 NOT NULL이다.

    `property_id`가 NULL이면 MATCH SIMPLE 규칙으로 **두 복합 FK가 모두
    스킵된다.** NOT NULL이 그 구멍을 막는 유일한 장치다(db_spec 4절 -1번).
    `rank`는 검색 순위라 비어 있으면 인용 목록의 순서가 정해지지 않는다.
    """
    prop, _ = await make_property(BookableUnitType.PROPERTY)
    inquiry = await _make_inquiry(db, prop)
    response = await _make_response(db, inquiry)
    chunk = await _make_chunk(db, prop)
    await db.commit()

    # rollback이 인스턴스 속성을 만료시키므로 id를 값으로 먼저 뽑는다
    response_id, chunk_id, pid = response.response_id, chunk.chunk_id, prop.property_id

    exc_rank = await _expect_integrity_error(
        db,
        ResponseSource(
            response_id=response_id, chunk_id=chunk_id, property_id=pid, rank=None
        ),
    )
    assert "rank" in str(exc_rank.orig)

    exc_pid = await _expect_integrity_error(
        db,
        ResponseSource(
            response_id=response_id, chunk_id=chunk_id, property_id=None, rank=1
        ),
    )
    assert "property_id" in str(exc_pid.orig)


# ---------------------------------------------------------------------------
# 9. uniq_inquiry_latest_response 회귀
#    — inquiry_responses의 FK와 컬럼을 건드렸으므로 부분 UNIQUE가 살아 있는지
# ---------------------------------------------------------------------------


async def test_partial_unique_latest_response_survived_migration(
    db: AsyncSession, make_property
):
    """revision ①은 이 인덱스를 건드리지 않았어야 한다.

    한 문의에 `is_latest=true` 응답은 정확히 1개다. 이 안전장치가 사라지면
    재시도 경로(UPDATE(false) 먼저 → INSERT(true) 나중)의 순서 위반이
    조용히 통과한다(db_spec 2.12, 코딩규칙 4).
    """
    prop, _ = await make_property(BookableUnitType.PROPERTY)
    inquiry = await _make_inquiry(db, prop)
    await _make_response(db, inquiry, is_latest=True)
    await db.commit()

    # rollback이 인스턴스 속성을 만료시키므로 id를 값으로 먼저 뽑는다
    inquiry_id, pid = inquiry.inquiry_id, prop.property_id

    # (1) 두 번째 is_latest=true → 거부
    exc = await _expect_integrity_error(
        db,
        InquiryResponse(
            inquiry_id=inquiry_id,
            property_id=pid,
            response_text="재시도 응답",
            is_latest=True,
        ),
    )
    assert "uniq_inquiry_latest_response" in str(exc.orig)

    # (2) 정상 경로 — 기존 행을 먼저 false로 내린 뒤 INSERT하면 통과한다
    await db.execute(
        text(
            "UPDATE inquiry_responses SET is_latest = false WHERE inquiry_id = :i"
        ).bindparams(i=inquiry_id)
    )
    db.add(
        InquiryResponse(
            inquiry_id=inquiry_id,
            property_id=pid,
            response_text="재시도 응답",
            is_latest=True,
        )
    )
    await db.commit()

    latest = await _count(db, InquiryResponse, inquiry_id=inquiry_id, is_latest=True)
    total = await _count(db, InquiryResponse, inquiry_id=inquiry_id)
    assert (latest, total) == (1, 2)
