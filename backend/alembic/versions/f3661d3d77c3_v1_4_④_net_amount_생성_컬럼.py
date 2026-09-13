"""v1.4 ④ net_amount 생성 컬럼

Revision ID: f3661d3d77c3
Revises: 67097358e024
Create Date: 2026-09-13 11:15:45.262954

`RESERVATIONS.net_amount`를 일반 컬럼에서 **생성 컬럼**으로 교체한다
(db_spec 2.6절). 이름은 유지한다.

    net_amount INTEGER GENERATED ALWAYS AS (gross_amount - fee_amount) STORED

---

⚠️ **이 파일은 autogenerate가 만들어 주지 않는다 — 본문을 전부 손으로 썼다.**
alembic 1.13.3은 `Computed`를 **렌더링은 하지만 감지하지는 못한다**.
`autogenerate/compare.py:988 _compare_computed_default()`는 차이를 발견해도
연산을 만들지 않고 `util.warn("Computed default on %s.%s cannot be modified")`
경고만 낸다. 실제로 이 revision의 자동생성 결과는 `pass` 두 줄짜리 빈 파일이었고
그 경고만 떴다.

**같은 이유로 `alembic check`도 ④를 검증하지 못한다.** `command.py:250 check()`가
`revision_context.run_autogenerate()`로 **autogenerate와 같은 경로**를 돌린 뒤
`upgrade_ops.as_diffs()`가 비었는지만 보므로, DB에 생성 컬럼이 있든 없든
*"No new upgrade operations detected"*가 나온다. ④의 적용 여부는
`pg_attribute.attgenerated = 's'`로 직접 확인해야 한다.

⚠️ **왕복해도 컬럼 순서는 복원되지 않는다.** `ADD COLUMN`은 항상 테이블 맨 뒤에
붙으므로, upgrade에서 뒤로 간 `net_amount`가 downgrade에서도 뒤에 남는다.
**④의 왕복은 완전한 원상복구가 아니다.** 코드는 전부 컬럼 이름으로 접근하므로
동작에는 영향이 없다(`SELECT *`의 컬럼 순서만 달라진다).

⚠️ **`ADD COLUMN ... GENERATED ... STORED`는 테이블 재작성을 유발한다.** 모든 행의
계산값을 물리적으로 다시 쓰기 때문이다. 오늘(2026-09-13)은 `reservations`가
0행이라 순식간이지만, **④만 다른 네 revision과 달리 메타데이터 변경이 아니다.**
행이 많은 상태에서는 테이블 전체 락과 재작성 시간을 예상해야 한다.

🔴 **10/1 Supabase 배포 전에 이 조회를 먼저 돌려라:**

    SELECT count(*) FROM reservations
     WHERE net_amount IS DISTINCT FROM gross_amount - fee_amount;

**0이면 이 변경은 값 보존이다.** 0이 아니면 저장돼 있던 값이 수식 결과와 다르다는
뜻이고, 마이그레이션은 **성공한 채로 그 값을 조용히 바꾼다.** 그 자리에서 멈추고
어느 쪽이 맞는지 판단해야 한다(0행 가드를 넣지 않는 이유이기도 하다 — ④는 컬럼
교체라 행이 있어도 DDL 자체는 성공한다. 문제는 값이지 실패가 아니다).

**함께 바뀌는 코드**: `ReservationCreateRequest.net_amount`를 제거했다.
`reservation_service`가 `Reservation(**payload.model_dump())`로 모델을 만들기
때문에, 요청 본문에 `net_amount`가 실려 오면 그 값이 INSERT에 들어가
`cannot insert a non-DEFAULT value into column "net_amount"`로 거부된다.
`ReservationResponse.net_amount`는 유지한다(읽기는 정상이다).
`ical_sync._to_create_request`는 금액을 넘기지 않아 영향이 없다.

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'f3661d3d77c3'
down_revision: Union[str, None] = '67097358e024'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 일반 컬럼 → 생성 컬럼. PostgreSQL은 기존 컬럼에 GENERATED를 붙이는 ALTER를
    #   지원하지 않으므로 **drop 후 add**가 유일한 경로다. drop이 add보다 먼저다.
    #   (선행 확인: reservations에 net_amount를 참조하는 인덱스 0건, 뷰 0건,
    #    pg_depend 의존 객체 0건 — DROP COLUMN이 함께 지울 것이 없다.)
    op.drop_column("reservations", "net_amount")
    # persisted=True는 **필수**다 — 생략하면 VIRTUAL로 렌더링되고 PostgreSQL은
    #   17까지 STORED만 지원해 실패한다.
    op.add_column(
        "reservations",
        sa.Column(
            "net_amount",
            sa.Integer(),
            sa.Computed("gross_amount - fee_amount", persisted=True),
            nullable=True,
        ),
    )


def downgrade() -> None:
    # upgrade의 역순 — 생성 컬럼을 지우고 같은 이름의 일반 컬럼으로 되돌린다.
    op.drop_column("reservations", "net_amount")
    op.add_column("reservations", sa.Column("net_amount", sa.Integer(), nullable=True))
    # ⚠️ **값을 반드시 복원한다.** 이 UPDATE가 없으면 downgrade가 모든 net_amount를
    #   NULL로 만들면서 **성공한 것처럼 보인다.** 오늘은 0행이라 차이가 없지만
    #   10/1 이후에는 조용한 값 소실이다.
    #   이 복원은 추측이 아니라 **정확한 재현**이다 — 생성 컬럼이 담고 있던 값의
    #   정의가 gross - fee이고, 두 원본 컬럼은 downgrade 후에도 그대로 남는다.
    #   (gross/fee 중 하나가 NULL이면 결과도 NULL이며, 이는 생성 컬럼일 때와 같다.)
    op.execute("UPDATE reservations SET net_amount = gross_amount - fee_amount")
