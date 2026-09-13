"""v1.4 ⑤ channel_fee_rates + financial_configs 컬럼 이동

Revision ID: 01360d2e135a
Revises: f3661d3d77c3
Create Date: 2026-09-13 11:48:27.028261

`CHANNEL_FEE_RATES`를 신설하고 `FINANCIAL_CONFIGS`에서 컬럼 4개를 뺀다
(db_spec 2.7·2.19절). 테이블 18 → 19.

  - `fee_type` · `commission_rate` · `fee_source` → **channel_fee_rates로 이동**
  - `base_nightly_rate` → **제거**(이동 아님. 단가의 원본은 PROPERTIES.base_price)
  - `financial_configs`에 남는 것은 `vat_included` 하나다

`FINANCIAL_CONFIGS.property_id`가 UNIQUE라 그 테이블은 숙소당 한 행인데
`channel_enum`은 3값이고 `CHANNEL_CONNECTIONS`는 숙소당 채널 3개까지 허용한다.
채널마다 수수료가 다른 현실을 담을 자리가 구조적으로 없었다.

---

⚠️ **오늘 다섯 revision 중 유일하게 데이터를 쓴다.** ①~④는 전부 스키마만
바꿨다. 이 파일은 아래 백필로 `channel_fee_rates`에 **행을 INSERT**한다.

⚠️ **downgrade는 완전한 역연산이 아니다 — 두 가지가 돌아오지 않는다.**

  1. **호스트가 고친 요율은 소실된다.** `channel_fee_rates`가 통째로 사라지는데
     `financial_configs`는 `property_id`가 UNIQUE라 **숙소당 한 행**이다.
     채널별로 다른 값을 담을 자리가 없으므로, 채널 3개에 서로 다른 요율을
     넣어 두었다면 되돌릴 곳이 없다. 복원되는 것은 컬럼과 **기본값**뿐이다.
  2. **컬럼 순서가 복원되지 않는다.** `ADD COLUMN`은 항상 테이블 맨 뒤에
     붙으므로 복원된 4개는 `vat_included`·`created_at` **뒤**에 온다(④의
     `net_amount`와 같은 성질이다). **왕복이 스키마를 원상복구하지 않는다** —
     `pg_dump` 텍스트를 비교할 때 이 순서 차이를 실제 변경으로 오인하지 마라.

🔴 **10/1 Supabase 배포 때 실질적 방어선은 백필 앞의 조회 두 개다.** 오늘
(2026-09-13) 로컬은 `financial_configs` 0행 · `channel_connections` 1행이라
두 조회가 모두 0을 돌려주고 아무 일도 하지 않는다. 운영 데이터가 들어간
뒤에는 그렇지 않다 — 하나는 **마이그레이션을 실패시키고**, 다른 하나는
**조용한 누락**을 만든다. 아래 주석 참고.

---

**자동생성 후 손으로 고친 것** (CLAUDE.md 코딩규칙 10 — upgrade 전 검토):

  1. **upgrade의 ENUM 2개를 `postgresql.ENUM(..., create_type=False)`로 바꿨다.**
     자동생성본은 `sa.Enum('AIRBNB', ..., name='channel_enum')` 형태였고, 이는
     `create_type` 기본값이 `True`라 테이블 생성 시 `CREATE TYPE`을 함께
     발행한다. 두 타입은 초기 마이그레이션 `939bc1d14754`가 이미 만들어
     두었으므로 `type "channel_enum" already exists`로 실패한다.
     (`sqlalchemy/dialects/postgresql/named_types.py:75` — `create_type`이
     False면 `_check_for_name_in_memos`가 True를 돌려주어 `_on_table_create`가
     `create()`를 호출하지 않는다.)
  2. **백필을 손으로 넣었다.** autogenerate는 스키마 차이만 보므로 데이터
     이동을 만들지 않는다.
  3. **백필 앞에 검증 조회 2개를 넣었다**(아래 주석 참고). 이 검증은
     **온라인 실행에서만 동작한다** — `--sql` 오프라인 모드는 DB에 붙지
     않아 SELECT 결과를 읽을 수 없으므로 `as_sql`로 감쌌다.
  4. **downgrade의 ENUM에도 `create_type=False`를 명시**하고, `DROP TYPE`을
     넣지 않는 이유를 주석으로 남겼다.
  5. 0행 가드는 넣지 않는다 — ⑤는 행이 있어도 DDL이 성공한다. 위험은 DDL
     실패가 아니라 **값의 소실**이고, 그건 백필과 그 앞의 조회가 담당한다.

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '01360d2e135a'
down_revision: Union[str, None] = 'f3661d3d77c3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# 이미 존재하는 ENUM 타입을 **재사용**한다. create_type=False가 없으면
#   CREATE TYPE이 발행되어 "type already exists"로 실패한다.
#   라벨과 순서는 db_spec 1절 · models/enums.py · 실제 pg_enum 셋이 일치한다.
channel_enum = postgresql.ENUM(
    'AIRBNB', 'BOOKING_COM', 'NAVER', name='channel_enum', create_type=False
)
fee_type_enum = postgresql.ENUM(
    'SPLIT_FEE', 'SINGLE_FEE', name='fee_type_enum', create_type=False
)


def _assert_backfill_is_safe(bind) -> None:
    """백필이 값을 잃거나 CHECK에서 멈추지 않는지 먼저 확인한다.

    오늘(2026-09-13) 로컬은 financial_configs가 0행이라 둘 다 0을 돌려주고
    아무 일도 하지 않는다. **10/1 Supabase에서 의미가 생긴다.**
    """
    # (1) 새 CHECK가 기존 값을 거부할 수 있다.
    #     기존 financial_configs.commission_rate에는 범위 CHECK가 없었고
    #     NUMERIC(5,4)는 9.9999까지 담긴다. 범위 밖 값이 한 행이라도 있으면
    #     아래 백필이 ck_channel_fee_rate_range에서 멈춘다.
    bad_rate = bind.execute(
        sa.text(
            "SELECT count(*) FROM financial_configs "
            "WHERE commission_rate < 0 OR commission_rate > 1"
        )
    ).scalar()
    if bad_rate:
        raise RuntimeError(
            f"financial_configs에 0~1 범위를 벗어난 commission_rate가 {bad_rate}건 있다. "
            "새 CHECK(ck_channel_fee_rate_range)가 이 값을 거부하므로 백필이 실패한다. "
            "다음 조회로 해당 행을 찾아 값을 먼저 바로잡아라: "
            "SELECT property_id, commission_rate FROM financial_configs "
            "WHERE commission_rate < 0 OR commission_rate > 1;  "
            "(15.5%를 0.1550이 아니라 15.5로 넣은 경우가 전형적이다)"
        )

    # (2) 백필이 보존하지 못하는 설정이 있을 수 있다.
    #     백필은 channel_connections를 기준으로 돌기 때문에, **연결이 하나도
    #     없는 숙소의 financial_configs 행은 옮겨 갈 곳이 없다.** LEFT JOIN이
    #     보장하는 것은 "모든 연결이 요율을 얻는다"이지 "모든 설정이
    #     보존된다"가 아니다.
    #     ⚠️ 실패는 보이고 누락은 보이지 않는다 — 이 조회가 없으면 값이
    #     사라진 채로 마이그레이션이 성공한다.
    orphan_config = bind.execute(
        sa.text(
            "SELECT count(*) FROM financial_configs fc "
            "WHERE NOT EXISTS (SELECT 1 FROM channel_connections cc "
            "                  WHERE cc.property_id = fc.property_id)"
        )
    ).scalar()
    if orphan_config:
        raise RuntimeError(
            f"채널 연결이 하나도 없는 숙소의 financial_configs 행이 {orphan_config}건 있다. "
            "아래 백필은 channel_connections 기준이라 이 행들의 요율 설정을 "
            "channel_fee_rates로 옮기지 못하고, 그대로 진행하면 drop_column에서 "
            "조용히 사라진다. 다음 조회로 대상을 확인하고 처리 방법을 먼저 정하라: "
            "SELECT fc.property_id, fc.fee_type, fc.commission_rate, fc.fee_source "
            "FROM financial_configs fc WHERE NOT EXISTS "
            "(SELECT 1 FROM channel_connections cc WHERE cc.property_id = fc.property_id);  "
            "(채널별로 행을 만들어 수동 INSERT하거나, 해당 설정을 버려도 되는지 판단해야 한다)"
        )


def upgrade() -> None:
    # ── 1) channel_fee_rates 신설 ──────────────────────────────────────────
    op.create_table(
        'channel_fee_rates',
        sa.Column('channel_fee_rate_id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('property_id', sa.BigInteger(), nullable=False),
        sa.Column('channel', channel_enum, nullable=False),
        sa.Column('fee_type', fee_type_enum, server_default=sa.text("'SINGLE_FEE'"), nullable=False),
        sa.Column('commission_rate', sa.Numeric(precision=5, scale=4), server_default=sa.text('0.1550'), nullable=False),
        sa.Column('fee_source', sa.String(length=50), server_default=sa.text("'system_default_2026'"), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.CheckConstraint('commission_rate >= 0 AND commission_rate <= 1', name='ck_channel_fee_rate_range'),
        sa.ForeignKeyConstraint(['property_id'], ['properties.property_id'], name='fk_channel_fee_rates_property', ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('channel_fee_rate_id'),
        sa.UniqueConstraint('property_id', 'channel', name='uq_channel_fee_rate_property_channel'),
    )
    op.create_index('idx_channel_fee_rates_property', 'channel_fee_rates', ['property_id'], unique=False)

    # ── 2) 백필 전 검증 ────────────────────────────────────────────────────
    # ⚠️ 이 두 검증은 **온라인 실행에서만 동작한다.** `alembic upgrade --sql`
    #   (오프라인 모드)은 DB에 붙지 않아 SELECT 결과를 읽을 수 없다
    #   (`op.get_bind().execute()`가 None을 돌려준다). 그래서 아래 블록을
    #   `as_sql`로 감싼다 — 오프라인 출력에는 두 SELECT와 판정이 나오지 않는다.
    #   **즉 `--sql`로 뽑은 스크립트를 그대로 실행하면 이 방어선이 없다.**
    #   10/1 Supabase에는 `alembic upgrade head`(온라인)로 적용해야 한다.
    ctx = op.get_context()
    if not ctx.as_sql:
        _assert_backfill_is_safe(op.get_bind())

    # ── 3) 백필 — drop_column보다 **먼저**다 ──────────────────────────────
    #   옮길 원본을 먼저 지우면 백필이 없는 컬럼을 참조하게 되고, 순서를
    #   뒤집으면 그 자리에서 실패하므로 조용히 넘어가지 않는다.
    #   DISTINCT: ③ 이후 같은 (property, channel)에 room_id가 다른 연결이
    #     여럿일 수 있다. 요율은 연결이 아니라 (숙소, 채널)에 걸린다.
    #   LEFT JOIN: financial_configs는 0행일 수 있다(오늘이 그렇다).
    #     INNER JOIN이면 아무것도 들어가지 않는다.
    #   COALESCE의 리터럴은 ENUM·VARCHAR 컬럼에 들어가므로 캐스팅을 명시한다.
    op.execute(
        """
        INSERT INTO channel_fee_rates
            (property_id, channel, fee_type, commission_rate, fee_source)
        SELECT DISTINCT cc.property_id, cc.channel,
               COALESCE(fc.fee_type, 'SINGLE_FEE'::fee_type_enum),
               COALESCE(fc.commission_rate, 0.1550::numeric(5,4)),
               COALESCE(fc.fee_source, 'system_default_2026'::varchar(50))
          FROM channel_connections cc
          LEFT JOIN financial_configs fc ON fc.property_id = cc.property_id
        ON CONFLICT (property_id, channel) DO NOTHING
        """
    )

    # ── 4) financial_configs에서 컬럼 4개 제거 ────────────────────────────
    #   vat_included는 남긴다(명세서 2.7절 v1.4 — 표시 전용).
    op.drop_column('financial_configs', 'base_nightly_rate')
    op.drop_column('financial_configs', 'fee_source')
    op.drop_column('financial_configs', 'fee_type')
    op.drop_column('financial_configs', 'commission_rate')


def downgrade() -> None:
    # 🔴 **DROP TYPE을 한 줄도 넣지 마라.**
    #   초기 마이그레이션 939bc1d14754가 downgrade에서 ENUM 15종을 루프로
    #   지우는 것은 **16개 테이블을 전부 철거한 뒤**의 전체 정리다. 성격이
    #   다르다. ⑤ 하나만 되돌리는 이 자리에서 같은 짓을 하면
    #   `fee_type_enum`은 financial_configs가(아래에서 되살린다),
    #   `channel_enum`은 channel_connections가 여전히 쓰고 있어
    #   `cannot drop type ... because other objects depend on it`으로 실패한다.
    #   초기 마이그레이션을 보고 따라 하지 않도록 여기 적어 둔다.

    # ── 1') financial_configs에 컬럼 4개 복원 ─────────────────────────────
    #   ⚠️ 되돌아오는 것은 **컬럼과 기본값뿐이다.** 호스트가 채널별로 고쳐 둔
    #   요율은 복원되지 않는다 — 이 테이블은 숙소당 한 행이라 담을 자리가 없다.
    #   ⚠️ 복원된 4개는 vat_included·created_at **뒤**에 붙는다(순서 미복원).
    #   ENUM은 create_type=False다. 타입은 살아 있다.
    op.add_column('financial_configs', sa.Column('commission_rate', sa.NUMERIC(precision=5, scale=4), server_default=sa.text('0.1550'), autoincrement=False, nullable=False))
    op.add_column('financial_configs', sa.Column('fee_type', fee_type_enum, server_default=sa.text("'SINGLE_FEE'::fee_type_enum"), autoincrement=False, nullable=False))
    op.add_column('financial_configs', sa.Column('fee_source', sa.VARCHAR(length=50), server_default=sa.text("'system_default_2026'::character varying"), autoincrement=False, nullable=False))
    op.add_column('financial_configs', sa.Column('base_nightly_rate', sa.INTEGER(), autoincrement=False, nullable=True))

    # ── 2') channel_fee_rates 제거 ────────────────────────────────────────
    op.drop_index('idx_channel_fee_rates_property', table_name='channel_fee_rates')
    op.drop_table('channel_fee_rates')
