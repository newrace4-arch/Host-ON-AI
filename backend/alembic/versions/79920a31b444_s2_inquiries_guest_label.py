"""S2 inquiries.guest_label

Revision ID: 79920a31b444
Revises: 01360d2e135a
Create Date: 2026-09-15 21:50:30.166412

`INQUIRIES`에 게스트 표시명 컬럼 하나를 추가한다.

## guest_label은 호스트가 입력하는 게스트 표시명이다

이 앱은 게스트 대면 채널을 두지 않는다(`ui_design.md` 「게스트 대면 채널을
만들지 않는다 — 시스템 경계 정의」). 게스트는 기존 OTA에서 호스트와
소통하고, **문의를 앱에 넣는 주체는 호스트**다. 따라서 담을 수 있는 식별자도
호스트가 직접 적는 이름뿐이다.

외부 식별자를 쓰지 않은 이유: **iCal이 게스트 식별자를 주지 않는다.**
`ical_sync.py`가 읽는 필드는 `UID`·`DTSTART`·`DTEND`·`SUMMARY` 넷뿐이고,
`UID`는 게스트가 아니라 **예약**의 식별자다(이미 `RESERVATIONS.external_uid`).
OTA 스레드 id를 담을 컬럼을 만들면 **채울 출처가 없는 컬럼**이 된다
(CLAUDE.md 9/10 규칙).

## 🔴 PII가 아니지만 Claude 프롬프트 제외 대상이다

전화·이메일·여권·카드번호를 담지 않는다. 다만 `RESERVATIONS.guest_name`과
같은 등급의 값이므로, 코딩규칙 12번이 `guest_name`을 프롬프트에서 빼도록
정한 것과 **같은 취급**을 한다.

    N4(`backend/app/utils/pii_masking.py`) 구현 시 제외 목록에 넣을 것.

DB에는 원본을 그대로 저장한다 — 호스트는 원본을 봐야 한다. 마스킹은
**외부(Claude)로 나가는 텍스트에만** 적용한다.

## 사전문의에서 누가 보냈는지를 담는 유일한 컬럼이다

`reservation_id`는 v1.3에서 nullable이 됐다(예약 전 사전문의 지원). 그런데
`INQUIRIES`에는 게스트를 가리키는 컬럼이 하나도 없어서, **`reservation_id`가
NULL인 사전문의는 누가 보냈는지 담을 자리가 없었다.** 예약 후 문의는
`reservation_id → RESERVATIONS.guest_name`으로 간접 확인되지만 사전문의는
그 경로가 끊긴다.

⚠️ **동일인 판정에는 쓸 수 없다.** 호스트가 적는 표시명이라 표기가 흔들린다
(`홍길동` / `홍 길동` / `Hong`). 같은 게스트의 두 번째 문의를 결정론적으로
묶는 것은 이 컬럼의 목적이 아니다.

⚠️ **사전문의가 나중에 예약으로 이어질 때 `reservation_id`를 채우는 절차는
아직 어느 문서에도 없다**(9/15 전수 확인 — `INQUIRIES`에 `PATCH`
엔드포인트가 api_contract 7절에 없다). 이 컬럼은 그 공백을 메우지 않는다.

## S1(직접예약)은 철회됐다

같은 마이그레이션에 `channel_enum`의 `DIRECT` 추가와
`RESERVATIONS.channel_connection_id` nullable 전환을 함께 담으려 했으나,
운영자 확인 결과 **직접예약을 받지 않아 실제로 쓰지 않는 기능**이라
철회했다. 적용까지 갔던 revision(`b61136acaf18`)은
`.backup/host_on_ai_20260915_175209.sql` 복원으로 되돌렸다 —
**enum 라벨은 downgrade로 지울 수 없어 백업 복원이 유일한 경로였다.**
경위는 `docs/troubleshooting.md` 34번.

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '79920a31b444'
down_revision: Union[str, None] = '01360d2e135a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('inquiries', sa.Column('guest_label', sa.String(length=100), nullable=True))


def downgrade() -> None:
    # 컬럼을 지우면 들어 있던 표시명도 함께 사라진다.
    # (S1과 달리 이 revision은 downgrade로 완전히 원상복구된다 — enum을
    #  건드리지 않기 때문이다.)
    op.drop_column('inquiries', 'guest_label')
