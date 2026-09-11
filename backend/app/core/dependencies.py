"""요청 컨텍스트 의존성 — 현재 호스트 식별.

⚠️ **이 모듈의 `get_current_host_id`는 9/11 인증 구현 전까지의 임시
스텁이다.** JWT 검증이 아직 없어서(`core/security.py` 미구현) 라우터가
`host_id`를 얻을 방법이 없는데, IDOR 방어(`WHERE p.host_id = :host_id`)는
`host_id`가 있어야 성립한다. 그래서 **얻는 경로만 이 함수 하나로
격리**해두고, 9/11에는 이 함수 본문만 JWT 검증으로 갈아끼운다. 라우터와
서비스 레이어는 그때 손대지 않아도 된다.

**스텁이 조용히 배포로 새어 나가지 못하게 3중으로 막는다.**

1. `DEV_AUTH_HOST_ID` 환경변수를 읽는다. **기본값이 없다** — 값을 주지
   않으면 스텁은 동작하지 않는다.
2. `ENV`가 `development`가 아니면 **애플리케이션 기동 자체를 실패**시킨다
   (요청 시점이 아니라 기동 시점이다 — 배포하면 그 자리에서 죽는다).
   `ENV`의 기본값은 `production`이라, 환경변수를 빠뜨린 배포가 개발
   환경으로 오인되는 일도 없다.
3. 스텁이 활성인 채로 기동하면 경고 로그를 남긴다.

2번이 핵심이다. 요청 시점에만 막으면 "배포는 성공했는데 특정 API만
500"이 되어 발견이 늦다. 기동을 막으면 배포 로그에서 즉시 드러난다.

### 9/11에 할 일

`get_current_host_id`를 JWT 검증으로 교체하고 `DEV_AUTH_STUB_ACTIVE`를
`False`로 내린다. 그 뒤 이 파일에서 스텁 관련 코드를 전부 지운다.
`verify_property_access` 같은 소유권 주입 의존성도 여기에 들어온다
(CLAUDE.md 디렉토리 규격).
"""

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer

from app.core.config import Settings, settings
from app.core.exceptions import UnauthorizedError
from app.core.security import decode_access_token

logger = logging.getLogger(__name__)

# **9/11 인증 구현 완료로 내렸다.** 아래 스텁 코드(`DevAuthStubMisconfigured`,
#   `assert_auth_stub_safe`)는 아직 남아 있으나 이 플래그가 False라 어느
#   경로로도 실행되지 않는다. 삭제는 별도 커밋으로 한다 — 교체가 실제로
#   동작하는 것을 확인한 뒤 지우기 위해서다.
DEV_AUTH_STUB_ACTIVE: bool = False


class DevAuthStubMisconfigured(RuntimeError):
    """인증 스텁이 안전하지 않은 상태로 활성화됐다.

    기동 시점(`assert_auth_stub_safe`)과 요청 시점(`get_current_host_id`)
    양쪽에서 쓴다. 어느 쪽이든 서비스가 인증 없이 동작하는 상태를 만들지
    않기 위한 것이라 복구를 시도하지 않고 그대로 터뜨린다.
    """


def assert_auth_stub_safe(config: Settings | None = None) -> None:
    """기동 시점 가드. `main.py` 라이프스팬이 **yield 전에** 호출한다.

    개발 환경이 아닌데 스텁이 살아 있으면 여기서 예외를 던져 기동을
    중단시킨다. 인증 없이 남의 숙소를 조회할 수 있는 상태로 서비스가
    떠 있는 것보다, 배포가 실패하는 편이 낫다.
    """
    config = config or settings

    if not DEV_AUTH_STUB_ACTIVE:
        return

    if not config.is_development:
        raise DevAuthStubMisconfigured(
            "인증 스텁(DEV_AUTH_STUB_ACTIVE)이 켜진 채로 "
            f"ENV={config.ENV!r} 환경에서 기동하려 했습니다. "
            "이 상태로 뜨면 인증 없이 타인의 숙소를 조회할 수 있습니다. "
            "9/11 인증 구현을 마치고 app/core/dependencies.py의 "
            "DEV_AUTH_STUB_ACTIVE를 False로 내리십시오."
        )

    if config.DEV_AUTH_HOST_ID is None:
        raise DevAuthStubMisconfigured(
            "인증 스텁이 활성인데 DEV_AUTH_HOST_ID가 설정되지 않았습니다. "
            "backend/.env에 DEV_AUTH_HOST_ID=<개발용 host_id>를 추가하십시오. "
            "(기본값을 두지 않는 것은 의도된 설계입니다 — 값을 명시적으로 "
            "주지 않으면 스텁이 동작하지 않습니다.)"
        )

    logger.warning(
        "⚠️  인증 스텁이 활성 상태입니다 — 모든 요청을 host_id=%s로 처리합니다. "
        "개발 환경 전용이며 배포본에서는 기동이 차단됩니다. (9/11 인증 구현 예정)",
        config.DEV_AUTH_HOST_ID,
    )


# `auto_error=False`가 핵심이다. 기본값(True)이면 토큰이 없을 때 FastAPI가
#   자체 `HTTPException`을 던져 `{"detail": "Not authenticated"}`로 응답한다 —
#   api_contract 0절 봉투가 아니라서 프론트가 에러 처리를 두 벌 만들어야 한다.
#   끄면 토큰이 없을 때 `None`이 들어오고, 우리가 `UnauthorizedError`를 던진다.
#
#   `tokenUrl`은 Swagger UI의 Authorize 버튼 표시용일 뿐 실제 동작에 관여하지
#   않는다(1.6절). `OAuth2PasswordRequestForm`은 쓰지 않지만 **헤더에서 토큰을
#   꺼내는 쪽은 응답 형식과 무관**하므로 이것은 그대로 쓴다.
_bearer_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login", auto_error=False)


async def get_current_host_id(
    token: Annotated[str | None, Depends(_bearer_scheme)],
) -> int:
    """현재 요청의 호스트 id. **`Authorization: Bearer <token>`에서 온다.**

    9/11 이전에는 이 함수가 `DEV_AUTH_HOST_ID` 환경변수를 읽는 스텁이었다.
    **본문만 바뀌었고 이름과 반환 타입은 그대로다** — 라우터는 여전히
    `Annotated[int, Depends(get_current_host_id)]` 하나만 바라보므로
    `channels` 등 기존 엔드포인트는 한 줄도 고치지 않았다.

    > `token` 파라미터는 **FastAPI가 주입**한다. 호출부가 넘기는 인자가
    > 아니라서 의존성으로 쓰는 쪽에는 변화가 없다. 헤더를 읽으려면
    > 주입 파라미터가 반드시 하나 필요하다.

    **DB를 조회하지 않는다.** 토큰이 유효하면 그 `host_id`를 그대로
    돌려준다. 호스트가 실제로 존재하는지는 소유권 검증이 이미 확인한다 —
    `get_owned_property`가 `WHERE p.host_id = :host_id`로 조회하므로 삭제된
    호스트의 토큰으로는 어떤 숙소도 잡히지 않아 404가 된다. 여기에 조회를
    넣으면 **모든 요청에 왕복이 하나 더 붙는다.**
    (`GET /auth/me`는 사용자 정보를 돌려주는 것이 목적이라 그쪽에서 따로
    조회하고, 없으면 401을 낸다.)

    소유권 검증 자체는 이 함수의 관심사가 아니다. 부존재·타인소유를 모두
    404 `RESOURCE_NOT_FOUND`로 통일하는 것은 서비스 레이어가 조회 조건으로
    처리한다(CLAUDE.md 코딩규칙 1).

    :raises UnauthorizedError: 토큰 없음(401 `UNAUTHORIZED`).
    :raises TokenExpiredError: 만료 — 같은 401 `UNAUTHORIZED`.
    :raises TokenInvalidError: 서명 무효·형식 오류 — 같은 401 `UNAUTHORIZED`.
    """
    if not token:
        raise UnauthorizedError("인증이 필요합니다. 로그인 후 다시 시도해 주세요.")

    # 만료·서명 오류는 여기서 잡지 않는다 — `security.py`가 던지는 예외가
    #   이미 401 `UNAUTHORIZED`이고, `main.py`의 `AppError` 핸들러가 봉투로
    #   감싼다. 셋을 응답에서 구분하지 않는 이유는 api_contract 1.1절 참고.
    return decode_access_token(token)
