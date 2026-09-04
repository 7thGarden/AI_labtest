from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_root():
    resp = client.get("/")
    assert resp.status_code == 200
    data = resp.json()
    assert data["application"] == "OpenSRE Backend"
    assert data["status"] == "running"


def test_health():
    resp = client.get("/api/health")
    assert resp.status_code == 200
    data = resp.json()
    assert "status" in data


def test_investigation_routes_exist():
    resp = client.get("/api/investigation/analyze")
    assert resp.status_code in (200, 500, 503)


def test_github_health_requires_token():
    resp = client.get("/api/github/health")
    assert resp.status_code == 200
    data = resp.json()
    assert "success" in data
