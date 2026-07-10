from fastapi.testclient import TestClient

from src.api.main import app

client = TestClient(app)


def test_health_endpoint() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "environment" in data


def test_auth_login_redirects_or_requires_config() -> None:
    response = client.get("/auth/login", follow_redirects=False)
    assert response.status_code in (307, 503)
    if response.status_code == 307:
        assert "accounts.google.com" in response.headers["location"]
