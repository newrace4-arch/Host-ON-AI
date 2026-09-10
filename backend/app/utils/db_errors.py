"""DB 제약 위반 판정 유틸.

여러 서비스가 `IntegrityError`를 도메인 예외로 번역하는데, 그 판정 기준이
드라이버마다 다르다. 기준을 한 곳에 두어 서비스마다 제각각 구현하는 일을
막는다.

`channel_service`와 `reservation_service` 양쪽이 쓰므로 서비스 모듈이 아니라
여기에 둔다 — `channel_service`가 이미 `reservation_service`를 import하고
있어서, 둘 중 한쪽에 두면 순환 import가 된다.
"""

from __future__ import annotations

from sqlalchemy.exc import IntegrityError


def violates_constraint(exc: IntegrityError, constraint: str) -> bool:
    """제약 위반이 `constraint` 때문인지 판정한다.

    ⚠️ **asyncpg 경로에서는 `exc.orig`에 `constraint_name` 속성이 아예
    없다.** SQLAlchemy가 asyncpg 예외를 자체 DBAPI 예외로 번역하면서
    `sqlstate`/`pgcode`만 옮기고 제약명은 메시지 문자열에만 남긴다.
    9/10 실측:

        orig type       : IntegrityError (asyncpg의 UniqueViolationError 아님)
        sqlstate        : '23505'
        constraint_name : 속성 없음 (dir()에 constraint 관련 항목 0개)
        str(orig)       : ... unique constraint "uq_property_channel"

    그래서 `getattr(orig, "constraint_name", "")`로만 판정하면 **항상
    거짓**이 되어 분기가 죽는다. 속성과 메시지를 **둘 다** 본다.
    psycopg(동기, Alembic 경로)에서는 속성이 있으므로 드라이버가 바뀌어도
    판정이 유지된다.

    `constraint`는 접두사로도 쓸 수 있다(예: `"fk_reservations_"`).
    """
    orig = exc.orig
    name = getattr(orig, "constraint_name", "") or ""
    return constraint in name or constraint in str(orig)
