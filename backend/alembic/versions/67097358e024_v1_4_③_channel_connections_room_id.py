"""v1.4 ③ channel_connections room_id

Revision ID: 67097358e024
Revises: 6a1ab58a4446
Create Date: 2026-09-13 10:39:33.834708

객실별 iCal 리스팅을 지원한다(db_spec 2.5절). iCal 피드는 객실을 알려주지
않고, 실제로는 호스텔 객실마다 별도 리스팅·별도 iCal URL이 나온다. 기존
`UNIQUE(property_id, channel)`은 숙소당 채널 1개만 허용해 객실 3개짜리
호스텔의 에어비앤비 피드 3개를 등록할 방법이 없었다.

🔴 **제약 이름 `uq_property_channel`을 컬럼만 바꿔 그대로 유지한다.**
`services/channel_service.py`가 이 **이름으로** IntegrityError를 409로
번역한다. 이름이 바뀌면 그 판정이 조용히 거짓이 되어 500으로 새어 나간다.

⚠️ **downgrade는 실패할 수 있다 — 객실별 연결이 생긴 뒤에는 되돌릴 수
없다.** downgrade는 UNIQUE를 3컬럼에서 2컬럼 `(property_id, channel)`로
되돌리는데, 같은 `(property_id, channel)`에 `room_id`만 다른 행이 둘 이상
있으면 그 제약을 다시 걸 수 없어 `could not create unique index`로 멈춘다.
이것이 정확히 이 revision이 가능하게 만든 상태다 — 호스텔 객실 3개에
에어비앤비 피드를 각각 등록하면 바로 그 모양이 된다. **되돌리려면 먼저
중복을 정리해야 한다**(숙소·채널 조합마다 연결을 1개만 남기고 나머지를
삭제). 오늘(2026-09-13) 로컬은 연결 1행뿐이고 그 행의 `room_id`가 NULL이라
실패하지 않는다. 문제가 되는 것은 **객실별 연결을 실제로 만든 뒤**다.

---

**자동생성 후 손으로 고친 것** (CLAUDE.md 코딩규칙 10 — upgrade 전 검토):

  - **연산·순서·`postgresql_nulls_not_distinct`를 고치지 않았다.**
    autogenerate가 *changed unique constraint*를 감지해 drop→create를
    스스로 냈고, `NULLS NOT DISTINCT` 옵션까지 실었다. 순서도
    add_column → drop → create(UNIQUE) → create(FK)로 이미 안전하다.
  - **0행 가드를 넣지 않았다.** ③은 nullable 컬럼 추가라 기존 행이 있어도
    성공한다. 기존 1행은 `room_id`가 NULL이 되고, `NULLS NOT DISTINCT`
    아래에서도 자기 자신과만 비교되므로 위반이 없다.
  - 주석만 보강했다.

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '67097358e024'
down_revision: Union[str, None] = '6a1ab58a4446'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1) 컬럼이 먼저다 — 아래 FK와 UNIQUE가 이 컬럼을 참조한다.
    op.add_column('channel_connections', sa.Column('room_id', sa.BigInteger(), nullable=True))
    # 2) UNIQUE 교체 — 같은 이름이라 drop이 create보다 **반드시 먼저**다.
    #   🔴 이름 uq_property_channel을 유지한다(409 번역이 이 이름에 걸려 있다).
    #   NULLS NOT DISTINCT가 없으면 room_id가 NULL인 독채 연결을 몇 개든 넣을
    #   수 있어 "채널당 연결 1개" 보장이 조용히 깨진다(db_spec 2.5절).
    op.drop_constraint('uq_property_channel', 'channel_connections', type_='unique')
    op.create_unique_constraint('uq_property_channel', 'channel_connections', ['property_id', 'channel', 'room_id'], postgresql_nulls_not_distinct=True)
    # 3) 다른 숙소의 객실을 가리키는 연결을 DB가 막는다. room_id가 NULL이면
    #   MATCH SIMPLE 규칙으로 검사가 스킵되고, property_id는 기존 단독 FK가
    #   보장한다(2.10절 INQUIRIES와 같은 구조).
    op.create_foreign_key('fk_channel_connections_room_property', 'channel_connections', 'rooms', ['room_id', 'property_id'], ['room_id', 'property_id'])


def downgrade() -> None:
    # upgrade의 **정확한 역순**이다.
    op.drop_constraint('fk_channel_connections_room_property', 'channel_connections', type_='foreignkey')
    op.drop_constraint('uq_property_channel', 'channel_connections', type_='unique')
    # ⚠️ **여기서 실패할 수 있다.** 같은 (property_id, channel)에 room_id만 다른
    #   행이 둘 이상 있으면 2컬럼 UNIQUE를 다시 걸 수 없어
    #   `could not create unique index` 로 멈춘다 — **객실별 연결이 생긴
    #   뒤에는 되돌릴 수 없다. 먼저 중복을 정리해야 한다**(숙소·채널 조합마다
    #   연결 1개만 남기고 나머지 삭제).
    #   nulls_not_distinct 없이 되돌린다 — v1.3 원형이 그렇다.
    op.create_unique_constraint('uq_property_channel', 'channel_connections', ['property_id', 'channel'])
    op.drop_column('channel_connections', 'room_id')
