"""환경설정(`Settings`) 자체의 회귀 테스트.

**스텁 테스트에서 분리해 둔 이유(9/10):**

기본값 `production`은 **인증 스텁을 위한 것이 아니라 fail-safe 그
자체다.** 환경변수를 빠뜨린 배포가 "개발 환경"으로 오인되지 않게 하는
장치이므로, 스텁 테스트와 수명이 묶여 있을 이유가 없다.

9/10 조사에서 **이 테스트가 기본값을 지키는 유일한 장치**인데
`test_auth_stub_guard.py`가 9/11 스텁 제거 때 파일째 삭제될 예정임이
확인돼 분리했다 — 규칙을 지키던 장치가 규칙과 함께 딸려 나가는 것을
막는다.
"""

from app.core.config import Settings


def test_env_defaults_to_production():
    """**fail-safe 방향**: 환경변수를 빠뜨린 배포가 개발 환경으로 오인되면 안 된다.

    이 기본값이 `"development"`로 바뀌면 `ENV`를 보고 갈라지는 모든 판정이
    한꺼번에 뒤집힌다. 환경변수 주입을 잊은 배포는 **개발 환경으로
    조용히 동작하는 것보다 기동에 실패하는 편이 낫다.**
    """
    assert Settings.model_fields["ENV"].default == "production"
