"""헬스체크 회귀 테스트.

Render 슬립 방지 핑이 의존하는 엔드포인트라, 경로나 응답 형태가 바뀌면
발표 당일 웨이크업이 조용히 실패한다. 그래서 형태까지 고정해둔다.
"""

from fastapi.testclient import TestClient

from app.main import app


def test_health_returns_ok():
    with TestClient(app) as client:
        res = client.get("/health")

    assert res.status_code == 200
    # api_contract.md 11절: 공통 {data, error} 봉투를 쓰지 않는 유일한 응답
    assert res.json() == {"status": "ok"}


def test_health_needs_no_auth():
    """Authorization 헤더 없이도 200이어야 한다(외부 모니터링 도구용)."""
    with TestClient(app) as client:
        assert client.get("/health").status_code == 200
