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

from app.core.config import Settings, settings

logger = logging.getLogger(__name__)

# 9/11 인증 구현 시 False로 내리고, 이후 스텁 코드를 삭제한다.
DEV_AUTH_STUB_ACTIVE: bool = True


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


async def get_current_host_id() -> int:
    """현재 요청의 호스트 id. **9/11에 JWT 검증으로 교체된다.**

    라우터는 이 의존성만 바라보고, 소유권 검증은 서비스 레이어의
    `get_owned_property(db, property_id, host_id)`가 조회 조건으로
    처리한다(부존재·타인소유 모두 404 `RESOURCE_NOT_FOUND`).
    """
    if not DEV_AUTH_STUB_ACTIVE:  # pragma: no cover - 9/11 교체 시점의 안전망
        raise NotImplementedError(
            "인증 스텁이 꺼져 있는데 JWT 검증이 구현되지 않았습니다."
        )

    # 기동 가드를 통과했더라도 런타임에 한 번 더 확인한다 — 기동 이후
    #   설정이 바뀌거나, 라이프스팬을 타지 않는 경로로 앱이 만들어질 수 있다.
    if settings.DEV_AUTH_HOST_ID is None:
        raise DevAuthStubMisconfigured(
            "DEV_AUTH_HOST_ID가 설정되지 않아 요청을 처리할 수 없습니다."
        )

    return settings.DEV_AUTH_HOST_ID
