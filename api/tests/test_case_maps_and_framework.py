from datetime import date

import pytest
from fastapi.testclient import TestClient

from app.case_maps import PDF_MAX_BYTES, CaseMapService, CaseMapValidator, LocalCaseMapRepository
from app.config import Settings
from app.corpus import ActiveCorpusRepository, GoldFixtureCorpusRepository
from app.engine import AuditEngine
from app.main import app
from app.models import AnnotationRevision, AuditSubmission, Authority, CaseMapAnnotation, Passage

client = TestClient(app)


def _authority(document_hash: str = "a" * 64) -> Authority:
    return Authority(
        id="test-authority",
        citation="[2025] SGHC 1",
        citation_key="2025SGHC1",
        case_name="Employer Pte Ltd v Employee",
        court="High Court",
        decision_date=date(2025, 1, 1),
        official_url="https://www.elitigation.sg/gd/s/2025_SGHC_1",
        source_provenance="officially_sourced",
        assessment_status="ai_supported",
        document_hash=document_hash,
        passages=[
            Passage(
                id="test-10",
                paragraph_label="[10]",
                text="The employer must identify a legitimate proprietary interest, subject to the facts.",
                supported_propositions=["legitimate_proprietary_interest"],
                limitations=["Fact-sensitive."],
                source_provenance="officially_sourced",
                assessment_status="ai_supported",
            )
        ],
    )


def test_case_map_generation_is_anchored_and_approval_is_review_only(tmp_path) -> None:
    corpus = ActiveCorpusRepository(tmp_path / "snapshot.json")
    corpus.activate([_authority()], persist_snapshot=False)
    service = CaseMapService(Settings(PROOFMARK_DATA_MODE="demo", GEMINI_API_KEY=""), corpus)
    case_map = service.generate("[2025] SGHC 1")
    assert case_map.document_hash == "a" * 64
    assert case_map.annotations[0].paragraph_labels == ["[10]"]
    assert case_map.annotations[0].validation_status == "valid"
    approved = service.approve(case_map.public_id)
    assert approved.status == "approved"
    assert approved.annotations[0].review_status == "approved"


def test_case_map_validator_rejects_invented_quote_and_taxonomy() -> None:
    annotation = CaseMapAnnotation(
        id="bad",
        annotation_type="holding",
        proposition_code="invented_rule",
        statement="Invented",
        paragraph_labels=["[10]"],
        supporting_quote="Words that are not in the judgment",
        modality="mandatory",
        model_confidence=0.9,
    )
    validated, errors = CaseMapValidator().validate(_authority(), [annotation])
    assert validated[0].validation_status == "invalid"
    assert len(errors) == 2


def test_case_map_becomes_stale_when_official_hash_changes(tmp_path) -> None:
    corpus = ActiveCorpusRepository(tmp_path / "snapshot.json")
    corpus.activate([_authority()], persist_snapshot=False)
    repository = LocalCaseMapRepository()
    service = CaseMapService(Settings(PROOFMARK_DATA_MODE="demo", GEMINI_API_KEY=""), corpus, repository)
    case_map = service.generate("[2025] SGHC 1")
    corpus.activate([_authority("b" * 64)], persist_snapshot=False)
    assert service.get(case_map.public_id).status == "stale"
    with pytest.raises(ValueError, match="stale"):
        service.revise(case_map.public_id, case_map.annotations[0].id, AnnotationRevision(statement="Changed"))


def test_case_map_correction_creates_a_superseding_version(tmp_path) -> None:
    corpus = ActiveCorpusRepository(tmp_path / "snapshot.json")
    corpus.activate([_authority()], persist_snapshot=False)
    service = CaseMapService(Settings(PROOFMARK_DATA_MODE="demo", GEMINI_API_KEY=""), corpus)
    original = service.generate("[2025] SGHC 1")
    revised = service.revise(
        original.public_id,
        original.annotations[0].id,
        AnnotationRevision(statement="A reviewer-corrected structured statement."),
    )
    assert revised.public_id != original.public_id
    assert revised.version == original.version + 1
    assert service.get(original.public_id).status == "superseded"
    assert revised.revision_history[-1]["supersedes"] == str(original.public_id)


def test_pdf_intake_rejects_oversized_or_non_pdf() -> None:
    service = CaseMapService(Settings(PROOFMARK_DATA_MODE="demo"), GoldFixtureCorpusRepository())
    with pytest.raises(ValueError, match="15 MB"):
        service.import_pdf(b"%PDF" + b"x" * PDF_MAX_BYTES, "large.pdf", "[2024] SGHC 94")
    with pytest.raises(ValueError, match="valid PDF"):
        service.import_pdf(b"plain text", "fake.pdf", "[2024] SGHC 94")


def test_user_supplied_evidence_can_never_reach_verified(tmp_path) -> None:
    corpus = ActiveCorpusRepository(tmp_path / "snapshot.json")
    authority = _authority()
    authority.source_provenance = "user_supplied"
    authority.passages[0].source_provenance = "user_supplied"
    corpus.activate([authority], persist_snapshot=False)
    claim = (
        AuditEngine(Settings(PROOFMARK_DATA_MODE="demo"), corpus)
        .audit(AuditSubmission(answer="A legitimate interest is required [2025] SGHC 1.", parser_mode="local"))
        .claims[0]
    )
    assert claim.verdict == "context_review"


def test_wrong_and_missing_pinpoints_are_not_substituted() -> None:
    engine = AuditEngine(Settings(PROOFMARK_DATA_MODE="demo"), GoldFixtureCorpusRepository())
    missing = engine.audit(AuditSubmission(answer="A legitimate interest is required [2007] SGCA 53 at [999].", parser_mode="local"))
    wrong = engine.audit(AuditSubmission(answer="A legitimate interest is required [2024] SGHC 29 at [18].", parser_mode="local"))
    assert (missing.claims[0].verdict, missing.claims[0].pinpoint_status) == ("unsupported", "missing")
    assert (wrong.claims[0].verdict, wrong.claims[0].pinpoint_status) == ("unsupported", "wrong_proposition")


def test_court_code_and_case_name_identity_mismatches_are_detected() -> None:
    engine = AuditEngine(Settings(PROOFMARK_DATA_MODE="demo"), GoldFixtureCorpusRepository())
    wrong_court = engine.audit(AuditSubmission(answer="A legitimate interest is required [2007] SGHC 53.", parser_mode="local")).claims[0]
    wrong_name = engine.audit(
        AuditSubmission(
            answer="Fake Corporation v Nobody states that a legitimate interest is required [2007] SGCA 53.",
            parser_mode="local",
        )
    ).claims[0]
    assert (wrong_court.verdict, wrong_court.decision_rule_id) == ("unsupported", "PM-CIT-004")
    assert (wrong_name.verdict, wrong_name.decision_rule_id) == ("unsupported", "PM-CIT-005")


def test_full_mode_requires_question_and_adds_omission_review_prompts() -> None:
    assert client.post("/api/v1/audits", json={"answer": "A legal answer.", "audit_mode": "full"}).status_code == 422
    response = client.post(
        "/api/v1/audits",
        json={
            "answer": "A legitimate interest is required [2007] SGCA 53.",
            "audit_mode": "full",
            "original_question": "Is a one-year worldwide employment restraint enforceable?",
            "facts": "The employee had customer connections and confidential information.",
            "parser_mode": "local",
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["context_profile"]["duration"] == "one-year" or payload["context_profile"]["duration"] is None
    assert any(item["code"] == "potential_omission" for item in payload["flags"])


def test_feedback_marks_review_without_changing_verdict() -> None:
    audit = client.post(
        "/api/v1/audits",
        json={"answer": "A legitimate interest is required [2007] SGCA 53.", "parser_mode": "local"},
    ).json()
    original_verdict = audit["claims"][0]["verdict"]
    response = client.post(
        "/api/v1/feedback",
        json={
            "audit_public_id": audit["public_id"],
            "claim_order": 1,
            "category": "wrong_verdict",
            "explanation": "The mapped proposition needs review.",
        },
    )
    assert response.status_code == 200
    refreshed = client.get(f"/api/v1/audits/{audit['public_id']}").json()
    assert refreshed["claims"][0]["pending_feedback"] is True
    assert refreshed["claims"][0]["verdict"] == original_verdict
