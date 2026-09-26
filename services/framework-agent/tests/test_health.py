from fastapi.testclient import TestClient

from app.main import app


def test_app_imports_without_secrets() -> None:
    assert app.title == "framework-agent"


def test_health_does_not_require_model_config() -> None:
    response = TestClient(app).get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "framework-agent"}
