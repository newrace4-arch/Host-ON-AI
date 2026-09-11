"""환경설정(`Settings`) 자체의 회귀 테스트.

**스텁 테스트에서 분리해 둔 이유(9/10):**

기본값 `production`은 **인증 스텁을 위한 것이 아니라 fail-safe 그
자체다.** 환경변수를 빠뜨린 배포가 "개발 환경"으로 오인되지 않게 하는
장치이므로, 스텁 테스트와 수명이 묶여 있을 이유가 없다.

9/10 조사에서 **이 테스트가 기본값을 지키는 유일한 장치**인데
`test_auth_stub_guard.py`가 9/11 스텁 제거 때 파일째 삭제될 예정임이
확인돼 분리했다 — 규칙을 지키던 장치가 규칙과 함께 딸려 나가는 것을
막는다.

**9/11 추가 — `is_development` 판정도 여기로 옮겼다.**

같은 일이 한 번 더 있었다. `ENV` 값별 판정(`production` / `staging` /
`prod` / `""` / `Production`)은 `test_auth_stub_guard.py`가
`assert_auth_stub_safe`를 통해 **간접적으로** 검증하고 있었는데, 그
파일이 스텁과 함께 삭제되면서 **`is_development`를 검증하는 장치가
저장소에서 사라질 뻔했다.**

`is_development`는 **지금 호출자가 0**이고 첫 실사용처가 10/1
`JWT_SECRET_KEY` 가드다. 그때까지 무검증으로 두면, 정작 그 가드를 붙이는
날에 판정 로직이 맞는지 아무도 모르는 상태가 된다. 그래서 스텁을 거치지
않고 **프로퍼티를 직접 호출하는 형태**로 바꿔 옮겼다.
"""

import pytest

from app.core.config import Settings


def test_env_defaults_to_production():
    """**fail-safe 방향**: 환경변수를 빠뜨린 배포가 개발 환경으로 오인되면 안 된다.

    이 기본값이 `"development"`로 바뀌면 `ENV`를 보고 갈라지는 모든 판정이
    한꺼번에 뒤집힌다. 환경변수 주입을 잊은 배포는 **개발 환경으로
    조용히 동작하는 것보다 기동에 실패하는 편이 낫다.**
    """
    assert Settings.model_fields["ENV"].default == "production"


@pytest.mark.parametrize("env", ["production", "staging", "prod", "", "Production"])
def test_is_development_is_false_for_non_development(env):
    """개발 환경이 **아닌** 값은 전부 False다.

    `"Production"`(대문자 P)이 목록에 있는 이유: 판정이
    `ENV.strip().lower() == "development"`이라 대소문자를 흡수한다. 그
    동작이 유지되는지 본다 — 반대로 `"Development"`도 개발로 인정된다.

    이 방향이 fail-safe다. **판정이 헐거워져 운영 환경이 개발로 오인되는
    것**이 그 반대보다 훨씬 위험하다.
    """
    assert Settings(ENV=env).is_development is False


@pytest.mark.parametrize("env", ["development", "Development", "  development  "])
def test_is_development_is_true_for_development(env):
    """공백과 대소문자를 흡수해 개발 환경으로 인정한다."""
    assert Settings(ENV=env).is_development is True
