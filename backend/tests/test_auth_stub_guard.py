"""인증 스텁 안전장치 회귀 테스트.

이 스텁이 배포로 새어 나가면 **인증 없이 남의 숙소를 조회할 수 있는
구멍**이 된다.

## ⚠️ 9/11 r47 4단계 이후 — 이 파일의 성격이 바뀌었다

`DEV_AUTH_STUB_ACTIVE`가 **False로 내려갔다.** `assert_auth_stub_safe`는
플래그가 꺼져 있으면 **아무것도 하지 않고 반환**하므로, 이 파일의 가드
테스트 7건이 그대로 두면 전부 깨진다(실제로 깨졌다).

**테스트를 지우거나 약화시키지 않고 플래그를 명시적으로 켜서 검증한다.**
이유는 하나다 — **스텁 코드가 아직 파일에 남아 있기 때문이다.** 코드가
남아 있는 한 누군가 플래그를 다시 켤 수 있고, 그때 가드가 동작하지 않으면
원래의 구멍이 그대로 열린다. 가드가 살아 있는지는 계속 확인해야 한다.

`_stub_on` 픽스처가 그 일을 한다. 플래그를 켠 상태를 만들어 **가드 로직
자체**를 검증하며, 테스트가 끝나면 원래대로(False) 돌아간다.

**이 파일은 스텁 코드 삭제 커밋에서 함께 지운다.** 그때는 지킬 대상이
사라지므로 남겨둘 이유가 없다.

**`ENV` 기본값 테스트는 여기에 두지 않는다** — `tests/test_config.py`로
분리했다(9/10). 이 파일은 곧 삭제되지만 그 테스트는 남아야 한다.
"""

import pytest

from app.core import dependencies
from app.core.config import Settings
from app.core.dependencies import DevAuthStubMisconfigured, assert_auth_stub_safe


@pytest.fixture
def _stub_on(monkeypatch):
    """가드 로직을 검증하기 위해 플래그를 **명시적으로** 켠다.

    `assert_auth_stub_safe`는 모듈 전역 `DEV_AUTH_STUB_ACTIVE`를 읽으므로
    그 속성을 갈아끼운다. `monkeypatch`가 테스트 종료 시 되돌린다.
    """
    monkeypatch.setattr(dependencies, "DEV_AUTH_STUB_ACTIVE", True)


def test_stub_is_disabled_after_jwt_replacement():
    """**현재 상태를 못박는다 — 스텁은 꺼져 있다.**

    r47 4단계에서 `get_current_host_id`가 JWT 검증으로 교체됐다. 이 값이
    실수로 다시 True가 되면 **모든 요청이 같은 host_id로 처리되어** 인증이
    통째로 무력화된다. 아래 가드 테스트들과 달리 이것은 픽스처로 값을
    바꾸지 않고 **실제 모듈 값**을 본다.
    """
    assert dependencies.DEV_AUTH_STUB_ACTIVE is False


def test_guard_is_inert_while_stub_is_off():
    """플래그가 꺼져 있으면 가드는 아무 판정도 하지 않는다.

    운영 환경 + host_id 없음이라는 **가장 위험한 조합**을 줘도 통과한다 —
    막을 스텁 자체가 없기 때문이다. 이 동작을 확인해 두지 않으면 아래
    테스트들이 픽스처 없이도 통과하는 것처럼 오해하게 된다.
    """
    assert_auth_stub_safe(Settings(ENV="production", DEV_AUTH_HOST_ID=None))


def test_development_with_host_id_passes(_stub_on):
    """개발 환경 + DEV_AUTH_HOST_ID가 있으면 기동을 막지 않는다."""
    assert_auth_stub_safe(Settings(ENV="development", DEV_AUTH_HOST_ID=1))


@pytest.mark.parametrize("env", ["production", "staging", "prod", "", "Production"])
def test_non_development_env_blocks_startup(_stub_on, env):
    """개발 환경이 아니면 **기동 시점에** 막는다.

    요청 시점에만 막으면 "배포는 성공했는데 특정 API만 500"이 되어 발견이
    늦다. 기동을 막으면 배포 로그에서 즉시 드러난다.
    """
    with pytest.raises(DevAuthStubMisconfigured):
        assert_auth_stub_safe(Settings(ENV=env, DEV_AUTH_HOST_ID=1))


def test_missing_host_id_blocks_startup(_stub_on):
    """개발 환경이라도 DEV_AUTH_HOST_ID가 없으면 막는다(기본값 없음)."""
    with pytest.raises(DevAuthStubMisconfigured):
        assert_auth_stub_safe(Settings(ENV="development", DEV_AUTH_HOST_ID=None))


def test_dev_auth_host_id_has_no_default():
    """하드코딩 금지 — 값을 명시적으로 주지 않으면 스텁이 동작하지 않는다."""
    assert Settings.model_fields["DEV_AUTH_HOST_ID"].default is None


def test_startup_warns_when_stub_active(_stub_on, caplog):
    """스텁이 활성인 채로 기동하면 경고 로그가 남는다."""
    with caplog.at_level("WARNING"):
        assert_auth_stub_safe(Settings(ENV="development", DEV_AUTH_HOST_ID=7))

    assert any("인증 스텁이 활성" in r.getMessage() for r in caplog.records)
