from fastapi.testclient import TestClient
from faultline.api import app, get_repo
from tests.conftest import FakeGraphRepository


def test_api_end_to_end():
    fake = FakeGraphRepository()
    app.dependency_overrides[get_repo] = lambda: fake
    try:
        # Avoid lifespan requiring Docker; TestClient without `with` doesn't run startup.
        client = TestClient(app)
        assert client.get("/api/v1/health/live").status_code == 200
        ready = client.get("/api/v1/health/ready")
        assert ready.status_code == 200
        assert len(client.get("/api/v1/changes").json()) == 3
        assert len(client.get("/api/v1/graph").json()["edges"]) > 0
        response = client.post("/api/v1/investigations", json={"change_id": "CHG-PAY-001"})
        assert response.status_code == 201, response.text
        report = response.json()
        assert report["verdict"] == "reproduced"
        assert client.get(f"/api/v1/investigations/{report['id']}").status_code == 200
        assert len(client.get("/api/v1/investigations").json()) == 1
        assert client.post("/api/v1/investigations", json={"change_id": "NOT-REAL"}).status_code == 404
        assert client.post("/api/v1/investigations", json={"change_id": "../../x"}).status_code == 422
    finally:
        app.dependency_overrides.clear()
