import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.authority_search import AuthoritySearchMetadataError, AuthoritySearchMetadataRepository
from app.main import app


def write_metadata(path: Path, records: list[dict]) -> Path:
    path.write_text(json.dumps(records), encoding="utf-8")
    return path


def pending_record(**overrides) -> dict:
    record = {
        "citation_key": "2024SGHC94",
        "plain_language_summary": "A concise navigation summary.",
        "issue_tags": ["confidential_information"],
        "search_aliases": ["trade secrets"],
        "review_status": "pending",
        "reviewer": None,
        "reviewed_at": None,
    }
    record.update(overrides)
    return record


def test_metadata_rejects_duplicates_unknown_tags_and_false_approval(tmp_path: Path) -> None:
    duplicate = pending_record()
    with pytest.raises(AuthoritySearchMetadataError, match="Duplicate"):
        AuthoritySearchMetadataRepository(write_metadata(tmp_path / "duplicate.json", [duplicate, duplicate]))

    with pytest.raises(AuthoritySearchMetadataError, match="unknown issue tag"):
        AuthoritySearchMetadataRepository(
            write_metadata(tmp_path / "unknown.json", [pending_record(issue_tags=["invented_issue"])])
        )

    with pytest.raises(AuthoritySearchMetadataError, match="requires reviewer"):
        AuthoritySearchMetadataRepository(
            write_metadata(tmp_path / "approval.json", [pending_record(review_status="approved")])
        )


def test_authorities_response_adds_optional_presentation_metadata() -> None:
    response = TestClient(app).get("/api/v1/authorities")
    assert response.status_code == 200
    payload = response.json()
    assert payload
    assert payload[0]["search_metadata"]["review_status"] == "pending"
    assert payload[0]["search_metadata"]["plain_language_summary"]
    assert payload[0]["passages"]
