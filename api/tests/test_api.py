from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_does_not_expose_secrets() -> None:
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    payload = response.json()
    assert "secret" not in str(payload).lower()
    assert payload["data_mode"] == "demo"


def test_rejects_empty_and_over_limit_answers() -> None:
    assert client.post("/api/v1/audits", json={"answer": ""}).status_code == 422
    assert client.post("/api/v1/audits", json={"answer": "x" * 20_001}).status_code == 422


def test_audit_can_be_retrieved_in_demo_mode() -> None:
    created = client.post(
        "/api/v1/audits",
        json={"answer": "A legitimate interest is required [2007] SGCA 53.", "parser_mode": "local"},
    )
    assert created.status_code == 200
    public_id = created.json()["public_id"]
    fetched = client.get(f"/api/v1/audits/{public_id}")
    assert fetched.status_code == 200
    assert fetched.json()["claims"][0]["verdict"] == "unverified"


def test_refresh_endpoint_is_bounded_and_exposes_progress() -> None:
    response = client.post("/api/v1/corpora/refresh", json={"limit": 1})
    assert response.status_code == 202
    payload = response.json()
    assert payload["requested_limit"] == 1
    assert payload["status"] in {"queued", "running"}
    latest = client.get("/api/v1/corpora/refreshes/latest")
    assert latest.status_code == 200
