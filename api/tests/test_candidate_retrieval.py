from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

import app.candidate_retrieval as candidate_module
from app.candidate_retrieval import (
    BUILDER_VERSION,
    CANDIDATE_INDEX_VERSION,
    RANKING_CONFIG,
    RETRIEVAL_VERSION,
    CandidateAuthorityIndex,
    _file_hash,
    _fit_vectors,
    _json_bytes,
    _save_vectors,
)
from app.config import Settings
from app.corpus import ActiveCorpusRepository
from app.engine import AuditEngine
from app.main import app
from app.models import AuditedClaim, AuditSubmission


def _runtime_chunks() -> list[dict[str, object]]:
    chunks = []
    for authority in ActiveCorpusRepository().list_authorities():
        passage = authority.passages[0]
        proposition = next(iter(passage.supported_propositions), "activity_scope")
        chunks.append(
            {
                "chunk_id": f"{authority.citation_key}:reviewed",
                "citation": authority.citation,
                "citation_key": authority.citation_key,
                "case_name": authority.case_name,
                "court": authority.court,
                "official_url": authority.official_url,
                "proposition": proposition,
                "statement": passage.text,
                "paragraphs": [{"paragraph_label": passage.paragraph_label, "text": passage.text}],
                "limitations": passage.limitations,
                "applicability_factors": [],
                "source_role": "holding",
                "treatment_status": "not_verified",
                "case_map_version": 1,
            }
        )
    return chunks


def _index_from_chunks(chunks: list[dict[str, object]]) -> CandidateAuthorityIndex:
    vectorizer, lexical, components, dense = _fit_vectors(chunks)
    return CandidateAuthorityIndex(
        manifest={
            "catalogue_version": "test-approved-snapshot",
            "catalogue_hash": "a" * 64,
            "index_version": "proofmark-candidate-index.1",
            "content_hash": "b" * 64,
            "retrieval_version": "proofmark-hybrid-tfidf-svd.1",
            "authority_count": len(chunks),
            "chunk_count": len(chunks),
            "display_threshold": 0.0,
        },
        chunks=chunks,
        vectorizer=vectorizer,
        lexical=lexical,
        svd_components=components,
        dense=dense,
    )


def _ready_index() -> CandidateAuthorityIndex:
    return _index_from_chunks(_runtime_chunks())


def _claim(index: CandidateAuthorityIndex, position: int = 0, citation: str | None = None) -> AuditedClaim:
    chunk = index.chunks[position]
    return AuditedClaim(
        order=1,
        text=str(chunk["statement"]),
        citation=citation,
        proposition=str(chunk["proposition"]),
        parser_confidence=1,
        parser_used="local",
        verdict="unsupported",
        rationale="No cited support was supplied.",
        lawyer_review_required=True,
        evidence=[],
    )


def test_candidate_search_is_full_mode_only_and_excludes_cited_authority() -> None:
    index = _ready_index()
    claim = _claim(index)
    citation_only = index.search(audit_mode="citation_only", original_question=None, facts=None, claims=[claim])
    assert citation_only.status == "not_requested"

    result = index.search(
        audit_mode="full",
        original_question="Which restraint principles require review?",
        facts="The employee had customer contact and confidential information.",
        claims=[claim],
    )
    assert result.status == "complete"
    assert 1 <= result.result_count <= 5
    assert result.candidates[0].review_label == "Potentially relevant authority — requires source and treatment review"

    cited = _claim(index, citation=str(index.chunks[0]["citation"]))
    excluded = index.search(
        audit_mode="full",
        original_question="Which restraint principles require review?",
        facts="The employee had customer contact and confidential information.",
        claims=[cited],
    )
    assert str(index.chunks[0]["citation_key"]) not in {item.citation_key for item in excluded.candidates}


def test_candidate_results_do_not_change_verdicts_scores_or_flags() -> None:
    corpus = ActiveCorpusRepository()
    submission = AuditSubmission(
        answer="A legitimate proprietary interest is required [2007] SGCA 53 at [70].",
        audit_mode="full",
        original_question="Can the employer enforce this restraint?",
        facts="The former employee had customer contact and access to confidential information.",
        parser_mode="local",
    )
    unavailable = AuditEngine(Settings(GEMINI_API_KEY=""), corpus, CandidateAuthorityIndex.unavailable("not ready")).audit(submission)
    retrieved = AuditEngine(Settings(GEMINI_API_KEY=""), corpus, _ready_index()).audit(submission)
    assert [item.verdict for item in retrieved.claims] == [item.verdict for item in unavailable.claims]
    assert retrieved.metrics == unavailable.metrics
    assert retrieved.flags == unavailable.flags
    assert retrieved.score_gates == unavailable.score_gates
    assert retrieved.completeness_searches == unavailable.completeness_searches
    assert unavailable.candidate_search.status == "unavailable"
    assert retrieved.candidate_search.status == "complete"


def test_candidate_search_deduplicates_authorities_and_limits_results() -> None:
    chunks = _runtime_chunks()
    duplicate = {**chunks[0], "chunk_id": f"{chunks[0]['citation_key']}:second-reviewed-annotation"}
    index = _index_from_chunks([*chunks, duplicate])
    result = index.search(
        audit_mode="full",
        original_question="Which restraint principles require review?",
        facts="The employee had client contact and access to confidential information.",
        claims=[_claim(index)],
    )
    citations = [candidate.citation_key for candidate in result.candidates]
    assert len(citations) <= 5
    assert len(citations) == len(set(citations))


def test_cache_identity_includes_catalogue_index_and_ranking_configuration() -> None:
    identity = _ready_index().cache_identity("full")
    assert identity["candidate_catalogue_version"] == "test-approved-snapshot"
    assert identity["candidate_catalogue_hash"] == "a" * 64
    assert identity["candidate_index_hash"] == "b" * 64
    assert identity["candidate_ranking_config"] == RANKING_CONFIG
    assert _ready_index().cache_identity("citation_only") == {"candidate_search": "not_requested"}


def test_full_mode_requires_question_and_facts() -> None:
    with pytest.raises(ValidationError, match="original legal question"):
        AuditSubmission(answer="A legal claim.", audit_mode="full", facts="Some facts")
    with pytest.raises(ValidationError, match="factual context"):
        AuditSubmission(answer="A legal claim.", audit_mode="full", original_question="A question")


def test_default_index_fails_closed_without_approved_artifact(tmp_path: Path) -> None:
    index = CandidateAuthorityIndex.load_or_unavailable(tmp_path / "catalogue", tmp_path / "index")
    assert index.status().status == "unavailable"
    result = index.search(
        audit_mode="full",
        original_question="A question",
        facts="Some facts",
        claims=[_claim(_ready_index())],
    )
    assert result.status == "unavailable"
    assert result.candidates == []


def test_candidate_index_status_endpoint_is_explicit() -> None:
    response = TestClient(app).get("/api/v1/candidate-index/status")
    assert response.status_code == 200
    assert response.json()["status"] in {"ready", "unavailable"}


def test_full_audit_candidate_result_round_trips_through_result_payload() -> None:
    client = TestClient(app)
    created = client.post(
        "/api/v1/audits",
        json={
            "answer": "A legitimate proprietary interest is required [2007] SGCA 53.",
            "audit_mode": "full",
            "original_question": "Is this employment restraint enforceable?",
            "facts": "The employee had customer contact and access to confidential information.",
            "parser_mode": "local",
        },
    )
    assert created.status_code == 200
    fetched = client.get(f"/api/v1/audits/{created.json()['public_id']}")
    assert fetched.status_code == 200
    assert fetched.json()["candidate_search"] == created.json()["candidate_search"]


def test_index_loader_rejects_modified_artifacts(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    catalogue_dir = tmp_path / "catalogue"
    index_dir = tmp_path / "index"
    catalogue_dir.mkdir()
    index_dir.mkdir()
    in_memory = _ready_index()
    authority_records = [
        {"authority": authority.model_dump(mode="json")}
        for authority in ActiveCorpusRepository().list_authorities()
    ]
    records = [authority_records[index % len(authority_records)] for index in range(25)]
    catalogue_hash = "c" * 64
    (catalogue_dir / "catalogue_manifest.json").write_text(
        json.dumps({"catalogue_version": "test-approved-v1", "approved_authorities_sha256": catalogue_hash}),
        encoding="utf-8",
    )
    monkeypatch.setattr(candidate_module, "load_catalogue", lambda *_args, **_kwargs: records)
    monkeypatch.setattr(candidate_module, "_catalogue_chunks", lambda _records: in_memory.chunks)

    chunks_path = index_dir / "chunks.json"
    vectors_path = index_dir / "index.npz"
    chunks_path.write_bytes(_json_bytes(in_memory.chunks))
    assert in_memory.vectorizer is not None and in_memory.lexical is not None
    assert in_memory.svd_components is not None and in_memory.dense is not None
    _save_vectors(
        vectors_path,
        in_memory.vectorizer,
        in_memory.lexical,
        in_memory.svd_components,
        in_memory.dense,
    )
    content_material = {
        "index_version": CANDIDATE_INDEX_VERSION,
        "builder_version": BUILDER_VERSION,
        "catalogue_version": "test-approved-v1",
        "catalogue_hash": catalogue_hash,
        "chunks_sha256": _file_hash(chunks_path),
        "vectors_sha256": _file_hash(vectors_path),
        "retrieval_version": RETRIEVAL_VERSION,
        "display_threshold": 0.2,
        "ranking_config": RANKING_CONFIG,
        "dimensions": int(in_memory.svd_components.shape[0]),
        "build_dependencies": {"numpy": candidate_module.np.__version__, "scikit_learn": candidate_module.sklearn.__version__},
    }
    manifest = {
        "index_version": CANDIDATE_INDEX_VERSION,
        "retrieval_version": RETRIEVAL_VERSION,
        "builder_version": BUILDER_VERSION,
        "catalogue_version": "test-approved-v1",
        "catalogue_hash": catalogue_hash,
        "authority_count": 25,
        "chunk_count": len(in_memory.chunks),
        "dimensions": content_material["dimensions"],
        "ranking_config": RANKING_CONFIG,
        "build_dependencies": content_material["build_dependencies"],
        "display_threshold": 0.2,
        "chunks_sha256": content_material["chunks_sha256"],
        "vectors_sha256": content_material["vectors_sha256"],
        "content_hash": candidate_module.canonical_json_hash(content_material),
    }
    (index_dir / "manifest.json").write_bytes(_json_bytes(manifest))
    assert CandidateAuthorityIndex.load(catalogue_dir, index_dir).ready

    tampered = json.loads(chunks_path.read_text(encoding="utf-8"))
    tampered[0]["statement"] = "modified after index approval"
    chunks_path.write_bytes(_json_bytes(tampered))
    failed = CandidateAuthorityIndex.load_or_unavailable(catalogue_dir, index_dir)
    assert failed.status().status == "unavailable"
    assert "artifact hash mismatch" in (failed.status().reason or "")


def test_numeric_index_serialisation_is_deterministic(tmp_path: Path) -> None:
    index = _ready_index()
    assert index.vectorizer is not None and index.lexical is not None
    assert index.svd_components is not None and index.dense is not None
    first = tmp_path / "first.npz"
    second = tmp_path / "second.npz"
    _save_vectors(first, index.vectorizer, index.lexical, index.svd_components, index.dense)
    _save_vectors(second, index.vectorizer, index.lexical, index.svd_components, index.dense)
    assert first.read_bytes() == second.read_bytes()
