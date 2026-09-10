"""인증 스텁 안전장치 회귀 테스트.

이 스텁이 배포로 새어 나가면 **인증 없이 남의 숙소를 조회할 수 있는
구멍**이 된다. 9/11에 스텁을 걷어낼 때까지 이 테스트가 가드를 지킨다.

가드가 세 겹이라 각각 따로 확인한다 — 하나가 무력해져도 나머지가 남는지
보기 위함이다.
"""

import pytest

from app.core.config import Settings
from app.core.dependencies import DevAuthStubMisconfigured, assert_auth_stub_safe


def test_development_with_host_id_passes():
    """개발 환경 + DEV_AUTH_HOST_ID가 있으면 기동을 막지 않는다."""
    assert_auth_stub_safe(Settings(ENV="development", DEV_AUTH_HOST_ID=1))


@pytest.mark.parametrize("env", ["production", "staging", "prod", "", "Production"])
def test_non_development_env_blocks_startup(env):
    """개발 환경이 아니면 **기동 시점에** 막는다.

    요청 시점에만 막으면 "배포는 성공했는데 특정 API만 500"이 되어 발견이
    늦다. 기동을 막으면 배포 로그에서 즉시 드러난다.
    """
    with pytest.raises(DevAuthStubMisconfigured):
        assert_auth_stub_safe(Settings(ENV=env, DEV_AUTH_HOST_ID=1))


def test_missing_host_id_blocks_startup():
    """개발 환경이라도 DEV_AUTH_HOST_ID가 없으면 막는다(기본값 없음)."""
    with pytest.raises(DevAuthStubMisconfigured):
        assert_auth_stub_safe(Settings(ENV="development", DEV_AUTH_HOST_ID=None))


def test_env_defaults_to_production():
    """**fail-safe 방향**: 환경변수를 빠뜨린 배포가 개발 환경으로 오인되면 안 된다.

    이 기본값이 'development'로 바뀌면 위 가드가 통째로 무력해진다.
    """
    assert Settings.model_fields["ENV"].default == "production"


def test_dev_auth_host_id_has_no_default():
    """하드코딩 금지 — 값을 명시적으로 주지 않으면 스텁이 동작하지 않는다."""
    assert Settings.model_fields["DEV_AUTH_HOST_ID"].default is None


def test_startup_warns_when_stub_active(caplog):
    """스텁이 활성인 채로 기동하면 경고 로그가 남는다."""
    with caplog.at_level("WARNING"):
        assert_auth_stub_safe(Settings(ENV="development", DEV_AUTH_HOST_ID=7))

    assert any("인증 스텁이 활성" in r.getMessage() for r in caplog.records)
