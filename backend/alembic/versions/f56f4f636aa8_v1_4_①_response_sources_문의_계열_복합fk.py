"""v1.4 ① response_sources + 문의 계열 복합FK

Revision ID: f56f4f636aa8
Revises: 939bc1d14754
Create Date: 2026-09-13 10:07:23.262648

⚠️ **downgrade는 완전한 역연산이 아니다 — `sources` 값은 돌아오지 않는다.**
`INQUIRY_RESPONSES.sources`(JSONB) 컬럼은 downgrade에서 **빈 채로만** 되살아나고,
그 내용이 옮겨 갈 자리였던 `RESPONSE_SOURCES`의 행은 `drop_table`로 **영구
소실**된다. 되돌리기 전에 값을 남기려면 따로 덤프해야 한다.

**시점 구분** — 오늘(2026-09-13) 로컬은 `inquiry_responses` 0건이라
**실손해가 없다.** 문제가 되는 것은 **10/1 Supabase 반영 이후**다. 그때는
운영 데이터가 들어 있으므로, downgrade 전에 반드시
`SELECT * FROM response_sources` 를 덤프해 두어야 한다.

---

**자동생성 후 손으로 고친 것** (CLAUDE.md 코딩규칙 10 — upgrade 전 검토):

  1. **upgrade 연산 순서를 db_spec 5절 [v1.4] ①의 1)~5)로 재배치했다.**
     autogenerate는 `create_table response_sources`를 **맨 위**에 놓았는데,
     그 시점에는 참조 대상인 `uq_response_property_ref`(그 컬럼 자체가 아직
     없다)와 `uq_chunk_property_ref`가 존재하지 않아
     `there is no unique constraint matching given keys...`로 실패한다.
  2. **downgrade도 1의 정확한 역순으로 재배치했다.** 자동생성본은 upgrade를
     상하 반전한 것이라, `response_sources`가 아직 살아 있는 상태에서 그
     테이블의 복합 FK가 의존하는 UNIQUE와 컬럼을 먼저 지우려 해
     `cannot drop constraint ... because other objects depend on it`으로
     실패한다.
  3. **upgrade 맨 위에 0행 가드를 넣었다.** 아래 주석 참고.

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'f56f4f636aa8'
down_revision: Union[str, None] = '939bc1d14754'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── 0행 가드 ────────────────────────────────────────────────────────────
    # 아래 3)은 property_id를 **NOT NULL로 한 번에** 추가한다. 기존 행이 하나도
    # 없을 때만 성립하는 경로다(db_spec 5절 [v1.4] ① 3)의 단서).
    # 행이 있는 DB에서는 이 파일을 다음 3단계로 고쳐야 한다:
    #   ① nullable로 추가
    #   ② UPDATE inquiry_responses r SET property_id = i.property_id
    #        FROM inquiries i WHERE i.inquiry_id = r.inquiry_id
    #   ③ ALTER TABLE inquiry_responses ALTER COLUMN property_id SET NOT NULL
    # 로컬은 0건이라 오늘 이 가드는 통과한다. 넣는 이유는 **10/1 Supabase에서
    # 같은 파일이 한 번 더 돌기 때문**이다 — 그때 행이 있으면 여기서 멈춘다.
    n = op.get_bind().execute(
        sa.text("SELECT count(*) FROM inquiry_responses")
    ).scalar()
    if n:
        raise RuntimeError(
            f"inquiry_responses에 {n}건이 있어 property_id를 NOT NULL로 바로 "
            "추가할 수 없다. db_spec 5절 [v1.4] 마이그레이션 순서 ①의 3) 단서대로 "
            "① nullable 추가 → ② UPDATE ... FROM inquiries → ③ SET NOT NULL "
            "3단계로 이 파일을 고친 뒤 다시 실행하라."
        )

    # ── 1) inquiries: 복합 FK의 참조 대상 후보키 ───────────────────────────
    op.create_unique_constraint(
        'uq_inquiry_property_ref', 'inquiries', ['inquiry_id', 'property_id']
    )

    # ── 2) knowledge_chunks: 복합 FK의 참조 대상 후보키 ────────────────────
    #   1)·2)가 3)·4)보다 먼저다. 복합 FK는 참조 대상에 그 컬럼 조합의
    #   UNIQUE(또는 PK)가 **먼저 있어야** 걸린다(db_spec 5절 [v1.4]).
    op.create_unique_constraint(
        'uq_chunk_property_ref', 'knowledge_chunks', ['chunk_id', 'property_id']
    )

    # ── 3) inquiry_responses: property_id 추가 → 단독 FK를 복합 FK로 교체 ──
    op.add_column(
        'inquiry_responses', sa.Column('property_id', sa.BigInteger(), nullable=False)
    )
    op.create_unique_constraint(
        'uq_response_property_ref', 'inquiry_responses', ['response_id', 'property_id']
    )
    op.drop_constraint(
        'inquiry_responses_inquiry_id_fkey', 'inquiry_responses', type_='foreignkey'
    )
    op.create_foreign_key(
        'fk_inquiry_responses_inquiry_property',
        'inquiry_responses',
        'inquiries',
        ['inquiry_id', 'property_id'],
        ['inquiry_id', 'property_id'],
        ondelete='CASCADE',
    )

    # ── 4) response_sources 신설 (복합 FK 2개) ─────────────────────────────
    op.create_table(
        'response_sources',
        sa.Column('response_id', sa.BigInteger(), nullable=False),
        sa.Column('chunk_id', sa.BigInteger(), nullable=False),
        sa.Column('property_id', sa.BigInteger(), nullable=False),
        sa.Column('rank', sa.SmallInteger(), nullable=False),
        sa.Column(
            'created_at',
            sa.DateTime(timezone=True),
            server_default=sa.text('now()'),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ['chunk_id', 'property_id'],
            ['knowledge_chunks.chunk_id', 'knowledge_chunks.property_id'],
            name='fk_response_sources_chunk_property',
            ondelete='CASCADE',
        ),
        sa.ForeignKeyConstraint(
            ['response_id', 'property_id'],
            ['inquiry_responses.response_id', 'inquiry_responses.property_id'],
            name='fk_response_sources_response_property',
            ondelete='CASCADE',
        ),
        sa.PrimaryKeyConstraint('response_id', 'chunk_id'),
    )
    op.create_index(
        'idx_response_sources_chunk', 'response_sources', ['chunk_id'], unique=False
    )

    # ── 5) inquiry_responses: sources(JSONB) 제거 — 반드시 맨 뒤 ───────────
    #   먼저 지우면 중간 실패 시 **옮길 원본이 사라진 채로 남는다**
    #   (db_spec 5절 [v1.4] ① 5)의 사유). 지금은 0건이라 실제 이관이 없지만
    #   순서 자체를 안전한 쪽으로 고정해 둔다.
    op.drop_column('inquiry_responses', 'sources')


def downgrade() -> None:
    # upgrade 1)~5)의 **정확한 역순**이다: 5') 4') 3') 2') 1').

    # ── 5') sources 컬럼 복원 ──────────────────────────────────────────────
    # ⚠️ **컬럼만 돌아오고 값은 빈 채(NULL)다.** 이 컬럼의 내용이 옮겨 간
    #   response_sources의 행은 바로 아래 4')의 drop_table로 **영구 소실**된다.
    #   alembic이 복원해 주지 않는다 — downgrade 전에 직접 덤프해야 한다.
    #   오늘(9/13) 로컬은 0건이라 실손해가 없고, **10/1 Supabase 이후**가
    #   문제다.
    op.add_column(
        'inquiry_responses',
        sa.Column(
            'sources',
            postgresql.JSONB(astext_type=sa.Text()),
            autoincrement=False,
            nullable=True,
        ),
    )

    # ── 4') response_sources 제거 ──────────────────────────────────────────
    #   이 테이블의 복합 FK 2개가 아래 3')의 uq_response_property_ref와
    #   2')의 uq_chunk_property_ref에 의존하므로, **그 UNIQUE들보다 먼저**
    #   지워야 한다. 순서를 바꾸면
    #   `cannot drop constraint ... because other objects depend on it`.
    op.drop_index('idx_response_sources_chunk', table_name='response_sources')
    op.drop_table('response_sources')

    # ── 3') inquiry_responses: 복합 FK → 단독 FK로 되돌리고 property_id 제거 ─
    #   옛 FK는 **원래 이름 그대로**(inquiry_responses_inquiry_id_fkey) 되살린다.
    #   이름이 달라지면 왕복 후 제약 대조가 삭제+추가로 잡힌다.
    op.drop_constraint(
        'fk_inquiry_responses_inquiry_property', 'inquiry_responses', type_='foreignkey'
    )
    op.create_foreign_key(
        'inquiry_responses_inquiry_id_fkey',
        'inquiry_responses',
        'inquiries',
        ['inquiry_id'],
        ['inquiry_id'],
        ondelete='CASCADE',
    )
    #   property_id를 지우기 **전에** 그 컬럼을 쓰는 UNIQUE를 먼저 지운다.
    op.drop_constraint('uq_response_property_ref', 'inquiry_responses', type_='unique')
    op.drop_column('inquiry_responses', 'property_id')

    # ── 2') knowledge_chunks 후보키 제거 ───────────────────────────────────
    op.drop_constraint('uq_chunk_property_ref', 'knowledge_chunks', type_='unique')

    # ── 1') inquiries 후보키 제거 ──────────────────────────────────────────
    #   3')에서 이 UNIQUE를 참조하던 복합 FK를 이미 지웠으므로 지금 지울 수 있다.
    op.drop_constraint('uq_inquiry_property_ref', 'inquiries', type_='unique')
