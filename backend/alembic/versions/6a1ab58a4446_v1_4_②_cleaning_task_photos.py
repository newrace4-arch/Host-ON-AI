"""v1.4 ② cleaning_task_photos

Revision ID: 6a1ab58a4446
Revises: f56f4f636aa8
Create Date: 2026-09-13 10:23:50.236566

⚠️ **downgrade는 완전한 역연산이 아니다 — `photo_urls` 값은 돌아오지 않는다.**
`CLEANING_TASKS.photo_urls`(JSONB 배열) 컬럼은 downgrade에서 **빈 배열
(`'[]'::jsonb`)로만** 되살아나고, 그 내용이 옮겨 간 `CLEANING_TASK_PHOTOS`의
행은 `drop_table`로 **영구 소실**된다. 사진 URL 목록이 통째로 사라진다는 뜻이며,
되돌리기 전에 값을 남기려면 따로 덤프해야 한다(①의 `sources`와 같은 구조다).

**시점 구분** — 오늘(2026-09-13) 로컬은 `cleaning_tasks` 0건이라 **실손해가
없다.** 문제가 되는 것은 **10/1 Supabase 반영 이후**다. 그때는 호스트가 실제로
올린 사진 URL이 들어 있으므로, downgrade 전에 반드시
`SELECT * FROM cleaning_task_photos` 를 덤프해 두어야 한다.

---

**자동생성 후 손으로 고친 것** (CLAUDE.md 코딩규칙 10 — upgrade 전 검토):

  - **연산 순서는 고치지 않았다.** 자동생성본이 이미
    `create_table` → `create_index` → `drop_column` 순으로, ①의 5)와 같은
    원칙(옮길 원본을 먼저 지우지 않는다)을 만족한다. downgrade도
    `add_column` → `drop_index` → `drop_table`로 그 정확한 역순이다.
    ①에서 재배치가 필요했던 것은 복합 FK가 참조 대상 UNIQUE에 의존해
    순서가 강제됐기 때문이며, ②에는 그런 의존이 없다.
  - **0행 가드를 넣지 않았다.** ①은 NOT NULL 컬럼을 백필 없이 추가해서
    행이 있으면 DDL 자체가 실패했다. ②는 컬럼을 **지우기만** 하므로 행이
    있어도 DDL이 성공한다. 문제는 *값이 사라지는 것*이고 그건 가드가
    아니라 위 경고와 downgrade 주석이 담당한다. 가드를 넣으면 오히려
    10/1 Supabase에서 마이그레이션이 막힌다.
  - 주석만 보강했다(아래 downgrade 참고).

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '6a1ab58a4446'
down_revision: Union[str, None] = 'f56f4f636aa8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # create_table을 drop_column보다 **먼저** 둔다(①의 5)와 같은 원칙) —
    #   옮길 원본을 먼저 지우면 중간 실패 시 원본이 사라진 채로 남는다.
    #   지금은 0건이라 실차이가 없지만 순서를 안전한 쪽으로 고정해 둔다.
    op.create_table('cleaning_task_photos',
    sa.Column('photo_id', sa.BigInteger(), autoincrement=True, nullable=False),
    sa.Column('task_id', sa.BigInteger(), nullable=False),
    sa.Column('photo_url', sa.Text(), nullable=False),
    sa.Column('sort_order', sa.Integer(), server_default=sa.text('0'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['task_id'], ['cleaning_tasks.task_id'], name='fk_cleaning_task_photos_task', ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('photo_id')
    )
    op.create_index('idx_cleaning_task_photos_task', 'cleaning_task_photos', ['task_id', 'sort_order'], unique=False)
    op.drop_column('cleaning_tasks', 'photo_urls')


def downgrade() -> None:
    # upgrade의 **정확한 역순**이다.

    # ⚠️ **컬럼만 돌아오고 값은 빈 배열('[]'::jsonb)이다.** 이 컬럼의 내용이
    #   옮겨 간 cleaning_task_photos의 행은 바로 아래 drop_table로 **영구
    #   소실**된다 — 호스트가 올린 사진 URL이 전부 사라진다. alembic이
    #   복원해 주지 않으므로 downgrade 전에 직접 덤프해야 한다.
    #   오늘(9/13) 로컬은 0건이라 실손해가 없고, **10/1 Supabase 이후**가
    #   문제다.
    #   원래 정의 3요소를 그대로 되살린다: JSONB / NOT NULL /
    #   server_default "'[]'::jsonb". 하나라도 빠지면 왕복 후 정의가 달라진다.
    op.add_column('cleaning_tasks', sa.Column('photo_urls', postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'::jsonb"), autoincrement=False, nullable=False))
    op.drop_index('idx_cleaning_task_photos_task', table_name='cleaning_task_photos')
    op.drop_table('cleaning_task_photos')
