"""요청 컨텍스트 의존성 — 현재 호스트 식별.

라우터는 `host_id`를 **이 모듈의 `get_current_host_id` 하나로만** 얻는다.
얻는 경로를 하나로 묶어 두었기 때문에, 9/11에 환경변수 스텁을 JWT 검증으로
바꿀 때 라우터와 서비스 레이어를 한 줄도 고치지 않았다.

## 인증과 소유권은 다른 단계다

이 모듈은 **인증까지만** 한다 — *"요청자가 누구인가"*. *"그 리소스가 이
사람 것인가"*는 서비스 레이어가 조회 조건으로 처리한다
(`get_owned_property`의 `WHERE p.host_id = :host_id`).

둘을 섞으면 응답 코드가 어긋난다(api_contract 0절).

| 단계 | 실패 시 | 뜻 |
|---|---|---|
| 인증 | **401 `UNAUTHORIZED`** | 요청자가 누구인지 확인할 수 없다 |
| 소유권 | **404 `RESOURCE_NOT_FOUND`** | 인증은 유효하나 리소스가 없거나 내 것이 아니다 |

⚠️ **권한 문제에 401을 반환하면 프론트가 세션 만료로 오인해 토큰을 지우고
로그아웃시킨다.** 남의 숙소 id를 한 번 잘못 눌렀을 뿐인데 로그인이 풀린다.
반대로 인증 실패에 404를 쓰면 로그인이 풀려야 할 상황에서 화면이 그냥
비어 보인다.

**403은 쓰지 않는다.** 부존재와 타인소유를 구분해 반환하면 id를 1씩
올려가며 어떤 id가 실재하는지 알아낼 수 있다(CLAUDE.md 코딩규칙 1).

## 앞으로 여기 들어올 것

`verify_property_access` 같은 **소유권 주입 의존성**(CLAUDE.md 디렉토리
규격). 지금은 서비스 레이어가 직접 처리하고 있어 아직 없다.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer

from app.core.exceptions import UnauthorizedError
from app.core.security import decode_access_token

# `auto_error=False`가 핵심이다. 기본값(True)이면 토큰이 없을 때 FastAPI가
#   자체 `HTTPException`을 던져 `{"detail": "Not authenticated"}`로 응답한다 —
#   api_contract 0절 봉투가 아니라서 프론트가 에러 처리를 두 벌 만들어야 한다.
#   끄면 토큰이 없을 때 `None`이 들어오고, 우리가 `UnauthorizedError`를 던진다.
#
#   `tokenUrl`은 Swagger UI의 Authorize 버튼 표시용일 뿐 실제 동작에 관여하지
#   않는다(api_contract 1.6절). `OAuth2PasswordRequestForm`은 쓰지 않지만
#   **헤더에서 토큰을 꺼내는 쪽은 응답 형식과 무관**하므로 이것은 그대로 쓴다.
_bearer_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login", auto_error=False)


async def get_current_host_id(
    token: Annotated[str | None, Depends(_bearer_scheme)],
) -> int:
    """현재 요청의 호스트 id. **`Authorization: Bearer <token>`에서 온다.**

    > `token` 파라미터는 **FastAPI가 주입**한다. 의존성으로 쓰는 쪽
    > (`Annotated[int, Depends(get_current_host_id)]`)은 인자를 넘기지
    > 않는다. 헤더를 읽으려면 주입 파라미터가 반드시 하나 필요하다.

    **DB를 조회하지 않는다.** 토큰이 유효하면 그 `host_id`를 그대로
    돌려준다. 호스트가 실제로 존재하는지는 소유권 검증이 이미 확인한다 —
    `get_owned_property`가 `WHERE p.host_id = :host_id`로 조회하므로 삭제된
    호스트의 토큰으로는 어떤 숙소도 잡히지 않아 404가 된다. 여기에 조회를
    넣으면 **모든 요청에 왕복이 하나 더 붙는다.**

    (`GET /auth/me`는 사용자 정보를 돌려주는 것이 목적이라 그쪽에서 따로
    조회하고, 호스트가 없으면 401을 낸다.)

    :raises UnauthorizedError: 토큰 없음(401 `UNAUTHORIZED`).
    :raises TokenExpiredError: 만료 — 같은 401 `UNAUTHORIZED`.
    :raises TokenInvalidError: 서명 무효·형식 오류 — 같은 401 `UNAUTHORIZED`.
    """
    if not token:
        raise UnauthorizedError("인증이 필요합니다. 로그인 후 다시 시도해 주세요.")

    # 만료·서명 오류는 여기서 잡지 않는다 — `security.py`가 던지는 예외가
    #   이미 401 `UNAUTHORIZED`이고, `main.py`의 `AppError` 핸들러가 봉투로
    #   감싼다. 셋을 응답 코드에서 구분하지 않는 이유는 api_contract 1.1절 참고.
    return decode_access_token(token)
