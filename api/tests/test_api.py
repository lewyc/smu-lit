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
    # The citation exists in the official source-only snapshot, but no reviewed
    # proposition annotation supports or contradicts this claim yet.
    assert fetched.json()["claims"][0]["verdict"] == "unverified"


def test_demo_cache_creates_a_new_traceable_audit_and_reaudit_bypasses_it() -> None:
    payload = {
        "answer": "A fresh cache fixture says a restraint is invalid [2026] SGHC 49.",
        "parser_mode": "local",
        "reuse_cache": True,
    }
    first = client.post("/api/v1/audits", json=payload)
    second = client.post("/api/v1/audits", json=payload)
    assert first.status_code == second.status_code == 200
    assert first.json()["cache_status"] == "miss"
    assert second.json()["cache_status"] == "hit"
    assert first.json()["public_id"] != second.json()["public_id"]

    reaudited = client.post(f"/api/v1/audits/{second.json()['public_id']}/re-audit")
    assert reaudited.status_code == 200
    assert reaudited.json()["cache_status"] == "bypassed"
    assert reaudited.json()["re_audited_from_public_id"] == second.json()["public_id"]


def test_freshness_endpoint_exposes_timestamp_and_schedule_without_source_content() -> None:
    response = client.get("/api/v1/corpora/freshness")
    assert response.status_code == 200
    payload = response.json()
    assert "active_corpus_version" in payload
    assert payload["scheduler"]["implementation"] == "in_process_mvp"
    assert "answer" not in str(payload).lower()


def test_currency_records_are_human_submission_only_and_validate_source_requirements() -> None:
    invalid = client.post(
        "/api/v1/currency-records",
        json={
            "authority_citation": "[2024] SGHC 29",
            "record_type": "later_treatment",
            "treatment": "limits",
        },
    )
    assert invalid.status_code == 422

    created = client.post(
        "/api/v1/currency-records",
        json={
            "authority_citation": "[2024] SGHC 29",
            "record_type": "statutory_amendment",
            "treatment": "amends",
            "statute_reference": "Illustrative Amendment Act 2026",
        },
    )
    assert created.status_code == 201
    assert created.json()["review_status"] == "approved"
    assert client.get("/api/v1/currency-records").status_code == 200


def test_refresh_endpoint_is_bounded_and_exposes_progress() -> None:
    response = client.post("/api/v1/corpora/refresh", json={"limit": 1})
    assert response.status_code == 202
    payload = response.json()
    assert payload["requested_limit"] == 1
    assert payload["status"] in {"queued", "running"}
    latest = client.get("/api/v1/corpora/refreshes/latest")
    assert latest.status_code == 200
